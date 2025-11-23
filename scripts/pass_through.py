import carla
import time
import random
import sys

from behavior_agent import BehaviorAgent  

def main():
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

    # -------------------------------------------
    # 3. Create the BehaviorAgent
    # -------------------------------------------
    agent = BehaviorAgent(
        vehicle,
        ignore_traffic_light=False,
        behavior="normal"  # options: cautious, normal, aggressive
    )

    # -------------------------------------------
    # 4. Create a list of waypoint locations
    # -------------------------------------------
    # You can create waypoints from the map, for example:
    route_waypoints = []
    start_wp = map.get_waypoint(vehicle.get_location())

    # Generate a simple forward route of N waypoints
    NEXT = 60     # number of waypoints to follow
    DIST = 4.0    # meters between waypoints

    current_wp = start_wp
    for _ in range(NEXT):
        next_wps = current_wp.next(DIST)
        if next_wps:
            current_wp = next_wps[0]
            route_waypoints.append(current_wp.transform.location)

    # Or you could manually define:
    # route_waypoints = [
    #     carla.Location(x=10, y=20, z=0),
    #     carla.Location(x=30, y=40, z=0)
    # ]
    
    # -------------------------------------------
    # 5. Give the route to the BehaviorAgent
    # -------------------------------------------
    # if len(route_waypoints) > 1:
    #     agent.set_destination(route_waypoints[0], route_waypoints[-1], clean=True)
    # else:
    #     print("Route is too short.")
    #     return
    destination = route_waypoints[-1]
    print("Driving along route...")

    # -------------------------------------------
    # 6. Simulation loop
    # -------------------------------------------
    try:
        for wp in route_waypoints:
            print(f"Next waypoint: x={wp.x:.2f}, y={wp.y:.2f}, z={wp.z:.2f}")
            # Set the current waypoint as the destination
            agent.set_destination(vehicle.get_location(), wp, clean=True)
            
            # Loop until we reach this waypoint
            while True:
                world.tick()
                agent.update_information(world)
                control = agent.run_step()
                vehicle.apply_control(control)

                # Check if we are close enough to the current waypoint
                if vehicle.get_location().distance(wp) < 2.0:  # 2-meter tolerance
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
