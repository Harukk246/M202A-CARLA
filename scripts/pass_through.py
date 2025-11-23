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
        "--route",
        type=str,
        required=False,
        help="Path to file containing waypoints (x y z ...)"
    )
    args = parser.parse_args()

    # -------------------------------------------
    # Connect to CARLA
    # -------------------------------------------
    client = carla.Client("localhost", 2000)
    client.set_timeout(5.0)

    world = client.get_world()
    w_map = world.get_map()

    # -----------------------------
    # Load route from file
    # -----------------------------
    # route_waypoints = []

    # with open(args.route, "r") as f:
    #     lines = [line.split("#")[0].strip() for line in f if line.strip()]

    # # Spawn transform from first line
    # x, y, z, pitch, yaw, roll = map(float, lines[0].split())
    # z += 1.0  # slightly above ground to avoid collision issues
    # spawn_transform = carla.Transform(
    #     location=carla.Location(x=x, y=y, z=z),
    #     rotation=carla.Rotation(pitch=pitch, yaw=yaw, roll=roll)
    # )

    # # Remaining lines are route waypoints
    # for line in lines[1:]:
    #     x, y, z = map(float, line.split()[:3])
    #     route_waypoints.append(carla.Location(x=x, y=y, z=z))

    # print(f"Spawn transform: {spawn_transform}")
    # print(f"Loaded {len(route_waypoints)} waypoints")


    # get random spawn and destination point
    spawns = w_map.get_spawn_points()
    filtered_spawns = [
    sp for sp in spawns
        if not (-300 <= sp.location.x <= 180 and -180 <= sp.location.y <= 180)
    ]
    spawn_point = random.choice(filtered_spawns)
    destination = random.choice(filtered_spawns)
    
    print(f"Spawn point: {spawn_point.location}, Destination: {destination.location}")
    destination_wp = w_map.get_waypoint(
        destination.location,
        project_to_road=True,                 # snap to nearest drivable lane
        lane_type=carla.LaneType.Driving      # only consider driving lanes
    )

    # -------------------------------------------
    # Spawn the vehicle
    # -------------------------------------------
    blueprint_library = world.get_blueprint_library()
    vehicle_bp = blueprint_library.find("vehicle.toyota.prius")

    print("Spawning hero vehicle...")
    vehicle = world.try_spawn_actor(vehicle_bp, spawn_point)

    if vehicle is None:
        print("Failed to spawn vehicle.")
        return

    world.player = vehicle 

    vehicle.set_autopilot(False)  # important! BehaviorAgent controls it manually

    # -----------------------------
    # Initialize the agent
    # -----------------------------
    if args.agent == "behavior":
        from behavior_agent import BehaviorAgent
        agent = BehaviorAgent(vehicle, ignore_traffic_light=False, behavior="normal")
    elif args.agent == "basic":
        from basic_agent import BasicAgent
        agent = BasicAgent(vehicle, target_speed=args.speed)
   
    print("Driving along route...")

    # -------------------------------------------
    # Simulation loop
    # -------------------------------------------
    # try:
    #     for wp in route_waypoints[1:]:
    #         wp_loc = wp
    #         print(f"Next waypoint: x={wp_loc.x:.2f}, y={wp_loc.y:.2f}, z={wp_loc.z:.2f}")

    #         # Set the current waypoint as the destination
    #         if(args.agent == "basic"):
    #             agent.set_destination([wp_loc.x, wp_loc.y, wp_loc.z])
    #         else: 
    #             agent.set_destination(vehicle.get_location(), wp_loc, clean=True)

    #         tick_counter = 0
    #         print_interval = 20  # print every 20 ticks (~1 second if tick = 0.05s)

    #         # Loop until we reach this waypoint
    #         while True:
    #             world.tick()
    #             if args.agent == "behavior":
    #                 agent.update_information(world)
    #             control = agent.run_step()
    #             vehicle.apply_control(control)

    #             # Compute distance to waypoint
    #             dist = vehicle.get_location().distance(wp_loc)

    #             # Only print every print_interval ticks
    #             if tick_counter % print_interval == 0:
    #                 print(f"Distance to waypoint: {dist:.2f} meters")

    #             tick_counter += 1

    #             # Check if we are close enough to the current waypoint
    #             if dist < 2.0:  # 2-meter tolerance
    #                 break

    #             time.sleep(0.05)

    #     print("Reached destination.")

    # Assume wp_dest is a carla.Location for the destination
    try:
        print(f"Driving to destination: x={destination_wp.x:.2f}, y={destination_wp.y:.2f}, z={destination_wp.z:.2f}")

        tick_counter = 0
        print_interval = 20  # print every 20 ticks (~1 second if tick=0.05s)

        while True:
            world.tick()

            if args.agent == "behavior":
                agent.update_information(world)

            control = agent.run_step()
            vehicle.apply_control(control)

            # Compute distance to destination
            dist = vehicle.get_location().distance(destination_wp)

            # Print distance periodically
            if tick_counter % print_interval == 0:
                print(f"Distance to destination: {dist:.2f} meters")

            tick_counter += 1

            # Stop when close enough
            if dist < 2.0:  # 2-meter tolerance
                print("Reached destination.")
                break

            time.sleep(0.05)

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
