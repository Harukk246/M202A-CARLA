# M202A-CARLA

## Basic Setup on Lab Computer

⚠️ Assumes that the Docker image exists already. 

1. Create / start the development container (assumes image exists already):

```bash
./create_dev_cont.sh autocommit
```

2. Setup and run the CARLA simulator:

```bash
cd /home/erdos/workspace/M202A-CARLA
. ./start_carla.sh
```

2. Load map
```bash
python load_town5.py
```

Run a one-car scenario
```bash
python one_car_route.py
```
Run with the `--help` flag for more options. 

3. Run the cleanup script to stop CARLA: 
```bash
./cleanup.sh
```
## Notes
- `tmux` may be useful for opening multiple windows in the docker container. 

# Camera Locations

![map](./map.png)

```
Visible:
4 = Position: x=35.000, y=-210.000, z=7.500 | Rotation: pitch=-28.00°, yaw=86.00°, roll=0.00°
5 = Position: x=27.500, y=212.500, z=7.500 | Rotation: pitch=-28.00°, yaw=268.00°, roll=0.00°

Encrypted:
1 = Position: x=20.000, y=2.500, z=7.500 | Rotation: pitch=-28.00°, yaw=0.00°, roll=0.00°
2 = Position: x=20.000, y=-90.000, z=7.500 | Rotation: pitch=-28.00°, yaw=0.00°, roll=0.00°
3 = Position: x=20.000, y=87.500, z=7.500 | Rotation: pitch=-28.00°, yaw=0.00°, roll=0.00°

6 = Position: x=-67.500, y=0.000, z=7.500 | Rotation: pitch=-28.00°, yaw=0.00°, roll=0.00°
7 = Position: x=-70.000, y=-90.000, z=7.500 | Rotation: pitch=-28.00°, yaw=0.00°, roll=0.00°
8 = Position: x=-70.000, y=87.500, z=7.500 | Rotation: pitch=-28.00°, yaw=0.00°, roll=0.00°

9 = Position: x=82.500, y=0.000, z=7.500 | Rotation: pitch=-28.00°, yaw=358.00°, roll=0.00°

10 = Position: x=-147.500, y=0.000, z=7.500 | Rotation: pitch=-28.00°, yaw=0.00°, roll=0.00°
11 = Position: x=-147.500, y=-90.000, z=7.500 | Rotation: pitch=-28.00°, yaw=0.00°, roll=0.00°
12 = Position: x=-147.500, y=90.000, z=7.500 | Rotation: pitch=-28.00°, yaw=0.00°, roll=0.00°

13 = Position: x=-210.000, y=0.000, z=7.500 | Rotation: pitch=-28.00°, yaw=0.00°, roll=0.00°
14 = Position: x=-210.000, y=-90.000, z=7.500 | Rotation: pitch=-28.00°, yaw=0.00°, roll=0.00°
15 = Position: x=-210.000, y=87.500, z=7.500 | Rotation: pitch=-28.00°, yaw=0.00°, roll=0.00°

16 = Position: x=137.500, y=0.000, z=7.500 | Rotation: pitch=-28.00°, yaw=358.00°, roll=0.00°
17 = Position: x=35.000, y=-150.000, z=7.500 | Rotation: pitch=-28.00°, yaw=2.00°, roll=0.00°
18 = Position: x=35.000, y=142.500, z=7.500 | Rotation: pitch=-28.00°, yaw=0.00°, roll=0.00°

```