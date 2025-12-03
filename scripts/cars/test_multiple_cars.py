#!/usr/bin/env python3
# minimal_spawn_traffic.py
# Minimal, noisy spawner: vehicles (and optional walkers) with Traffic Manager.

import argparse, random, time, signal, sys
import carla

'''
spawns cars around the beltway of town 5. cars enter at the two entry points on the sides. 
'''

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
    ap.add_argument("--town", default="Town05", help="e.g. Town03 (optional: load map)")
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

    # start with a bird's eye view
    spectator = world.get_spectator()
    spec_loc = carla.Location(x=-50,y=0,z=450) # right is +y, up is +x
    spec_rot = carla.Rotation(pitch=-90)
    spectator.set_transform(carla.Transform(spec_loc, spec_rot))

    m = world.get_map()
    spawns = m.get_spawn_points()
    filtered_spawns = [
    sp for sp in spawns
        if not (-300 <= sp.location.x <= 180 and -180 <= sp.location.y <= 180)
    ]
    for sp in filtered_spawns: print(sp.location)
    p(f"Connected. Map: {m.name}. Spawn points available: {len(filtered_spawns)}")

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
    car_bp = bp_lib.find("vehicle.toyota.prius")
    # car_bp.set_attribute("color", "255,0,0")
    # spawn_point = carla.Transform(
    #     carla.Location(x=0.0, y=200.0, z=1.0),
    #     carla.Rotation(pitch=0.0, yaw=180.0, roll=0.0)
    # )
    # p(f"Spawning red prius at: {spawn_point.location} yaw={spawn_point.rotation.yaw}")

    random.shuffle(filtered_spawns)
    want = min(args.vehicles, len(filtered_spawns))
    p(f"Attempting to spawn {want} vehicles …")

    batch = []
    for i in range(want):
        bp = car_bp
        if bp.has_attribute("color"):
            colors = bp.get_attribute("color").recommended_values
            if colors: bp.set_attribute("color", random.choice(colors))
        batch.append(carla.command.SpawnActor(bp, filtered_spawns[i]))

    # batch = [carla.command.SpawnActor(car_bp, spawn_point)]
    results = client.apply_batch_sync(batch, True)  # True = do it synchronously so we get results
    vehicle_ids = []
    for i, r in enumerate(results):
        if r.error:
            p(f"spawn FAILED: {r.error}")
        else:
            p(f"spawn OK -> id={r.actor_id}")
            vehicle_ids.append(r.actor_id)

    if not vehicle_ids:
        p("No vehicles spawned. Check the errors above (map not loaded? collisions? permissions?).")
        world.apply_settings(original)
        return

    vehicles = world.get_actors(vehicle_ids)
    for v in vehicles:
        v.set_autopilot(True, tm.get_port())

    p(f"Vehicles on autopilot: {len(vehicles)}")

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
