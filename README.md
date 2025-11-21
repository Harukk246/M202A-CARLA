# M202A-CARLA

## Basic Setup on Lab Computer

⚠️ Assumes that the Docker image exists already. 

1. Create / start the development container (assumes image exists already):

```bash
./create_dev_cont.sh autocommit
```

2. Setup environment for CADET and go to main scripts folder:

```bash
cd ~/workspace
. ./setup_env.sh
cd M202A-CARLA/scripts
```

Run the simulator
```bash
./start_carla.sh
```

Start the town
```bash
python minimal_town5.py
```

Run car scripts, camera scripts in the same way. 

## Notes

- `tmux` may be useful for opening multiple windows in the docker container. 