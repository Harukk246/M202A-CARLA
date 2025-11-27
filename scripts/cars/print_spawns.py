import carla
import sys

def main():

    # -------------------------------------------
    # Connect to CARLA
    # -------------------------------------------
    client = carla.Client("localhost", 2000)
    client.set_timeout(5.0)

    world = client.get_world()
    w_map = world.get_map()

    # three point route generation 
    spawns = w_map.get_spawn_points()
    print("Total spawn points:", len(spawns))
    for sp in spawns:
        print(sp.location, sp.rotation)
    # sort spawns into inside/outside highway
    inside_spawns = []
    outside_spawns = []
    for sp in spawns:
        if -300 <= sp.location.x <= 180 and -180 <= sp.location.y <= 180:
            inside_spawns.append(sp)
        else:
            outside_spawns.append(sp)
    
    print("Outside Spawns:")
    for sp in outside_spawns:
        print(sp.location, sp.rotation)
    print("Inside Spawns:")
    for sp in outside_spawns:
        print(sp.location, sp.rotation)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled by user.")
        sys.exit(0)

