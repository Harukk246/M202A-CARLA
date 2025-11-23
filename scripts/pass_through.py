import carla
import time
import random
import sys
import argparse 

def main():

    # -----------------------------
    # Parse command-line arguments
    # -----------------------------
    parser = argparse.ArgumentParser(description="CARLA Agent Selector")
    parser.add_argument(
        "--agent",
        choices=["basic", "behavior"],
        default="behavior",
        help="Which agent to use: 'basic' for BasicAgent, 'behavior' for BehaviorAgent"
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=20.0,
        help="Target speed for BasicAgent in km/h (only used if --agent basic)"
    )
    parser.add_argument(
        "--waypoints_file",
        type=str,
        required=True,
        help="Path to file containing waypoints (x y z ...)"
    )
    args = parser.parse_args()

    # -------------------------------------------
    # 1. Connect to CARLA
    # -------------------------------------------
    client = carla.Client("localhost", 2000)
    client.set_timeout(5.0)

    world = client.get_world()
    map = world.get_map()

    # -------------------------------------------
    # 2. Spawn a vehicle
    # -------------------------------------------
    blueprint_library = world.get_blueprint_library()
    vehicle_bp = blueprint_library.find("vehicle.toyota.prius")

    spawn_points = map.get_spawn_points()
    spawn_point = random.choice(spawn_points)

    print("Spawning hero vehicle...")
    vehicle = world.try_spawn_actor(vehicle_bp, spawn_point)

    if vehicle is None:
        print("Failed to spawn vehicle.")
        return

    world.player = vehicle 

    vehicle.set_autopilot(False)  # important! BehaviorAgent controls it manually

    # -----------------------------
    # 3. Initialize the agent
    # -----------------------------
    if args.agent == "behavior":
        from behavior_agent import BehaviorAgent
        agent = BehaviorAgent(vehicle, ignore_traffic_light=False, behavior="normal")
    elif args.agent == "basic":
        from basic_agent import BasicAgent
        agent = BasicAgent(vehicle, target_speed=args.speed)

   # -------------------------------------------
    # 4. Create a start and end waypoint from spawn points
    # -------------------------------------------
    # spawn_points = map.get_spawn_points()  # list of carla.Transform

    # # Randomly pick start and end transforms (ensure they are not the same)
    # start_transform = random.choice(spawn_points)
    # end_transform = random.choice(spawn_points)
    # while end_transform == start_transform:
    #     end_transform = random.choice(spawn_points)

    # # Convert transforms to waypoints on the road
    # start_wp = map.get_waypoint(start_transform.location)
    # end_wp = map.get_waypoint(end_transform.location)

    # print(f"Start waypoint: x={start_wp.transform.location.x:.2f}, "
    #     f"y={start_wp.transform.location.y:.2f}, "
    #     f"z={start_wp.transform.location.z:.2f}")

    # print(f"End waypoint: x={end_wp.transform.location.x:.2f}, "
    #     f"y={end_wp.transform.location.y:.2f}, "
    #     f"z={end_wp.transform.location.z:.2f}")

    # # Store them as a simple route
    # route_waypoints = [start_wp, end_wp]


    # # Or you could manually define:
    # # route_waypoints = [
    # #     carla.Location(x=10, y=20, z=0),
    # #     carla.Location(x=30, y=40, z=0)
    # # ]

    # -----------------------------
    # Load waypoints from file
    # -----------------------------
    route_waypoints = []

    with open(args.waypoints_file, "r") as f:
        for line in f:
            line = line.split("#")[0].strip()  # remove comments
            if not line:
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            x, y, z = map(float, parts[:3])
            loc = carla.Location(x=x, y=y, z=z)
            route_waypoints.append(loc)

    print(f"Loaded {len(route_waypoints)} waypoints from {args.waypoints_file}")
    print("Driving along route...")

    # -------------------------------------------
    # 6. Simulation loop
    # -------------------------------------------
    try:
        for wp in route_waypoints[1:]:
            wp_loc = wp.transform.location
            print(f"Next waypoint: x={wp_loc.x:.2f}, y={wp_loc.y:.2f}, z={wp_loc.z:.2f}")

            # Set the current waypoint as the destination
            if(args.agent == "basic"):
                agent.set_destination([wp_loc.x, wp_loc.y, wp_loc.z])
            else: 
                agent.set_destination(vehicle.get_location(), wp_loc, clean=True)

            tick_counter = 0
            print_interval = 20  # print every 20 ticks (~1 second if tick = 0.05s)

            # Loop until we reach this waypoint
            while True:
                world.tick()
                if args.agent == "behavior":
                    agent.update_information(world)
                control = agent.run_step()
                vehicle.apply_control(control)

                # Compute distance to waypoint
                dist = vehicle.get_location().distance(wp_loc)

                # Only print every print_interval ticks
                if tick_counter % print_interval == 0:
                    print(f"Distance to waypoint: {dist:.2f} meters")

                tick_counter += 1

                # Check if we are close enough to the current waypoint
                if dist < 2.0:  # 2-meter tolerance
                    break

                time.sleep(0.05)

        print("Reached destination.")


    finally:
        print("Destroying actors...")
        vehicle.destroy()

    print("Done.")

# Entry point --------------------------
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled by user.")
        sys.exit(0)
