# M202A-CARLA

## Basic Setup on Lab Computer

⚠️ Assumes that the Docker image exists already. 

1. Create / start the development container (assumes image exists already):

```bash
./create_dev_cont.sh autocommit
```

# WARNING
Do not run the above command (in step 1) on Vamsi's desktop. Instead use `./run_cont.sh`.

2. Setup and run the CARLA simulator:

```bash
cd scripts/dev
. ./start_carla.sh
```
This script also sets the python path (solves behaviorAgent not found error) and loads the town 5 map. 
Safe to re-run in order to reload town 5. 

2. Run a one-car scenario
```bash
cd scripts/cars
python one_car_route.py
```
Run with the `--help` flag for more options. 

OR, Run a multi-car scenario
```bash
cd scripts/cars
./multi_car_route.sh <route id 1> <route id 2>
```
Parameters are route ids, separated by spaces. Colors are randomly assigned. 

3. Run the cleanup script to stop CARLA: 
```bash
cd scripts/dev
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
1 = Position: x=25.000, y=-167.500, z=2.500 | Rotation: pitch=-28.00°, yaw=0.00°, roll=0.00°
2 = Position: x=65.000, y=-75.000, z=5.000 | Rotation: pitch=-20.00°, yaw=292.00°, roll=0.00°
3 = Position: x=67.500, y=-10.000, z=2.500 | Rotation: pitch=-10.00°, yaw=90.00°, roll=0.00°

6 = Position: x=20.000, y=-40.000, z=5.000 | Rotation: pitch=-28.00°, yaw=0.00°, roll=0.00°
7 = Position: x=20.000, y=35.000, z=5.000 | Rotation: pitch=-28.00°, yaw=0.00°, roll=0.00°
8 = Position: x=-17.500, y=-77.500, z=7.500 | Rotation: pitch=-38.00°, yaw=276.00°, roll=0.00°

9 = Position: x=-7.500, y=77.500, z=7.500 | Rotation: pitch=-34.00°, yaw=90.00°, roll=0.00°

10 = Position: x=-12.500, y=-10.000, z=2.500 | Rotation: pitch=-14.00°, yaw=90.00°, roll=0.00°
11 = Position: x=-35.000, y=-40.000, z=7.500 | Rotation: pitch=-26.00°, yaw=180.00°, roll=0.00°
12 = Position: x=-35.000, y=42.500, z=5.000 | Rotation: pitch=-24.00°, yaw=180.00°, roll=0.00°

13 = Position: x=-65.000, y=125.000, z=5.000 | Rotation: pitch=-26.00°, yaw=38.00°, roll=0.00°
14 = Position: x=-87.500, y=-130.000, z=7.500 | Rotation: pitch=-28.00°, yaw=316.00°, roll=0.00°
15 = Position: x=-92.500, y=-77.500, z=7.500 | Rotation: pitch=-38.00°, yaw=276.00°, roll=0.00°

16 = Position: x=-82.500, y=-12.500, z=7.500 | Rotation: pitch=-36.00°, yaw=90.00°, roll=0.00°
17 = Position: x=-85.000, y=77.500, z=7.500 | Rotation: pitch=-44.00°, yaw=90.00°, roll=0.00°
18 = Position: x=-157.500, y=-10.000, z=7.500 | Rotation: pitch=-46.00°, yaw=90.00°, roll=0.00°

19 = Position: x=-115.000, y=-40.000, z=15.000 | Rotation: pitch=-50.00°, yaw=182.00°, roll=0.00°
20 = Position: x=-115.000, y=50.000, z=15.000 | Rotation: pitch=-54.00°, yaw=180.00°, roll=0.00°
21 = Position: x=-157.500, y=-100.000, z=15.000 | Rotation: pitch=-58.00°, yaw=90.00°, roll=0.00°
22 = Position: x=-157.500, y=77.500, z=12.500 | Rotation: pitch=-52.00°, yaw=90.00°, roll=0.00°
23 = Position: x=75.000, y=70.000, z=2.500 | Rotation: pitch=-8.00°, yaw=54.00°, roll=0.00°
24 = Position: x=130.000, y=-7.500, z=2.500 | Rotation: pitch=-26.00°, yaw=90.00°, roll=0.00°
25 = Position: x=42.500, y=140.000, z=7.500 | Rotation: pitch=-30.00°, yaw=180.00°, roll=0.00°

```

## Start the CALRA simulator (on Vamsi's desktop)

```bash
cd ~/M202A-CARLA/scripts
./run_cont.sh
# At this point you should be on a shell within the docker container.
./scripts/run_simulator.sh
```

## Load World

```bash
# This command is run on the host.
python load_town5.py
```

## Start Cameras

```bash
# This command is run on the host.
python spawn_world5_cameras.py
```

This script will start the cameras at the hardocded locations above and start recording to mp4 (with ffmpeg). This script is responsible for advancing the world tick when Carla is running in sync mode.

The videos are output to `scripts/videos`.

### Warning

Do not advance the world tick with `world.tick()` in any other file.

## Sync Videos _to_ the Mininet VM

```bash
# This command is run on the host.
./scripts/mininet/push_video_to_mininet.sh
```

This will take the videos from `scripts/videos` and put it on `~/videos` on the Mininet VM.

## Run the wifi simulator and packet capture

```bash
# These commands are run inside the mininet vm.
cd ~/M202A-CARLA
sudo ./clean_mininet.sh
sudo python two_stations_wifi.py
```

The pcap files will be output to `~/M202A-CARLA/scripts/mininet/pcaps`.

## Copy PCAP files out of the Mininet VM

```bash
# This command is run on the host.
./scripts/mininet/sync_mininet_files.sh
```

The pcap files will be in `scripts/mininet/pcaps`.
