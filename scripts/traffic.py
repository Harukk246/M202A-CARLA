#!/usr/bin/env python3
# minimal_spawn_traffic.py
# Minimal, noisy spawner: vehicles (and optional walkers) with Traffic Manager.

import argparse, random, time, signal, sys
import carla

def p(s): print(f"[spawn] {s}", flush=True)

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2000)
    ap.add_argument("--tm-port", type=int, default=8000)
    ap.add_argument("--vehicles", type=int, default=50)
    ap.add_argument("--walkers", type=int, default=0)
    ap.add_argument("--sync", action="store_true")
    ap.add_argument("--delta-seconds", type=float, default=0.05)
    ap.add_argument("--town", default=None, help="e.g. Town03 (optional: load map)")
    ap.add_argument("--seed", type=int, default=None)
    return ap.parse_args()

def main():
    args = parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    p(f"Connecting to CARLA at {args.host}:{args.port} …")
    client = carla.Client(args.host, args.port)
    client.set_timeout(10.0)

    try:
        world = client.get_world()
    except Exception as e:
        p(f"ERROR: cannot connect to server: {e}")
        sys.exit(1)

    if args.town:
        p(f"Loading map {args.town} …")
        world = client.load_world(args.town)

    m = world.get_map()
    spawns = m.get_spawn_points()
    p(f"Connected. Map: {m.name}. Spawn points available: {len(spawns)}")

    original = world.get_settings()
    settings = world.get_settings()
    settings.synchronous_mode = args.sync
    if args.sync:
        settings.fixed_delta_seconds = args.delta_seconds
    world.apply_settings(settings)
    p(f"Synchronous mode: {world.get_settings().synchronous_mode}  Δt={world.get_settings().fixed_delta_seconds}")

    tm = client.get_trafficmanager(args.tm_port)
    tm.set_synchronous_mode(world.get_settings().synchronous_mode)
    tm.set_global_distance_to_leading_vehicle(2.5)
    tm.global_percentage_speed_difference(0)

    bp_lib = world.get_blueprint_library()
    car_bps = [bp for bp in bp_lib.filter("vehicle.*")
               if not bp.has_attribute("number_of_wheels") or bp.get_attribute("number_of_wheels").as_int() == 4]
    if not car_bps:
        p("ERROR: no vehicle blueprints found.")
        world.apply_settings(original)
        return

    random.shuffle(spawns)
    want = min(args.vehicles, len(spawns))
    p(f"Attempting to spawn {want} vehicles …")

    batch = []
    for i in range(want):
        bp = random.choice(car_bps)
        if bp.has_attribute("color"):
            colors = bp.get_attribute("color").recommended_values
            if colors: bp.set_attribute("color", random.choice(colors))
        batch.append(carla.command.SpawnActor(bp, spawns[i]))

    results = client.apply_batch_sync(batch, True)  # True = do it synchronously so we get results
    vehicle_ids = []
    for i, r in enumerate(results):
        if r.error:
            p(f"spawn[{i}] FAILED: {r.error}")
        else:
            p(f"spawn[{i}] OK -> id={r.actor_id}")
            vehicle_ids.append(r.actor_id)

    if not vehicle_ids:
        p("No vehicles spawned. Check the errors above (map not loaded? collisions? permissions?).")
        world.apply_settings(original)
        return

    vehicles = world.get_actors(vehicle_ids)
    for v in vehicles:
        v.set_autopilot(True, tm.get_port())

    p(f"Vehicles on autopilot: {len(vehicles)}")

    # Optional walkers (kept minimal)
    walker_ids = []
    controller_ids = []
    if args.walkers > 0:
        p(f"Attempting to spawn {args.walkers} walkers …")
        walker_bps = bp_lib.filter("walker.pedestrian.*")
        walker_spawns = []
        for _ in range(args.walkers):
            loc = world.get_random_location_from_navigation()
            if loc: walker_spawns.append(carla.Transform(loc))

        w_batch = []
        for sp in walker_spawns:
            w_bp = random.choice(walker_bps)
            w_batch.append(carla.command.SpawnActor(w_bp, sp))
        w_res = client.apply_batch_sync(w_batch, True)
        walker_ids = [r.actor_id for r in w_res if not r.error]
        for r in w_res:
            if r.error: p(f"walker FAIL: {r.error}")
        p(f"Walkers spawned: {len(walker_ids)}")

        if walker_ids:
            ctrl_bp = bp_lib.find("controller.ai.walker")
            c_batch = [carla.command.SpawnActor(ctrl_bp, carla.Transform(), wid) for wid in walker_ids]
            c_res = client.apply_batch_sync(c_batch, True)
            controller_ids = [r.actor_id for r in c_res if not r.error]
            for r in c_res:
                if r.error: p(f"walker controller FAIL: {r.error}")

            controllers = world.get_actors(controller_ids)
            for c in controllers:
                c.start()
                dest = world.get_random_location_from_navigation()
                if dest: c.go_to_location(dest)
                c.set_max_speed(random.uniform(1.0, 1.6))
            p(f"Walker controllers started: {len(controller_ids)}")

    def cleanup():
        p("Cleaning up spawned actors …")
        try:
            client.apply_batch([carla.command.DestroyActor(aid) for aid in controller_ids + walker_ids + vehicle_ids])
        except Exception as e:
            p(f"cleanup error: {e}")
        world.apply_settings(original)
        p("Done. Bye!")

    def sigint(_sig, _frm):
        cleanup(); sys.exit(0)

    signal.signal(signal.SIGINT, sigint)

    # Prime TM / physics
    if args.sync:
        p("Priming sync ticks …")
        for _ in range(10):
            world.tick()
    p("Traffic running. Press Ctrl+C to stop.")

    while True:
        if args.sync:
            world.tick()
        else:
            time.sleep(0.5)

if __name__ == "__main__":
    main()