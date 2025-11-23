import carla
import time
import random
import sys

from carla.agents.navigation.behavior_agent import BehaviorAgent  

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
    if len(route_waypoints) > 1:
        agent.set_destination(route_waypoints[0], route_waypoints[-1], clean=True)
    else:
        print("Route is too short.")
        return

    print("Driving along route...")

    # -------------------------------------------
    # 6. Simulation loop
    # -------------------------------------------
    try:
        while True:
            world.tick()

            # BehaviorAgent requires update_information() each tick
            agent.update_information(world)

            # Compute next control command
            control = agent.run_step()
            vehicle.apply_control(control)

            # If close to destination, re-route or stop
            remaining = agent._local_planner.done()
            if remaining:
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
