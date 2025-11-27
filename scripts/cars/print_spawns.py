import carla
import time
import random
import sys
import argparse 
import os

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

      # -------------------------------------------
    # Plot the spawn points
    # -------------------------------------------
    import matplotlib.pyplot as plt

    # Extract XY coordinates
    xs_inside = [sp.location.x for sp in inside_spawns]
    ys_inside = [sp.location.y for sp in inside_spawns]

    xs_outside = [sp.location.x for sp in outside_spawns]
    ys_outside = [sp.location.y for sp in outside_spawns]

    plt.figure(figsize=(10, 8))

    # Outside spawns = red
    plt.scatter(xs_outside, ys_outside, c='red', label='Outside Highway')

    # Inside spawns = blue
    plt.scatter(xs_inside, ys_inside, c='blue', label='Inside Highway')

    # Add labels and formatting
    plt.title("CARLA Spawn Point Map")
    plt.xlabel("X coordinate (m)")
    plt.ylabel("Y coordinate (m)")
    plt.legend()
    plt.grid(True)
    plt.axis('equal')   # equal scaling of x/y

    # Show the plot
    plt.show()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled by user.")
        sys.exit(0)

