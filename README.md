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