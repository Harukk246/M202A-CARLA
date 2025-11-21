#!/usr/bin/env python

import carla
import time
import argparse
from srunner.scenariomanager.carla_data_provider import CarlaDataProvider
from srunner.scenariomanager.scenario_manager import ScenarioManager

# Import our custom scenario
from pass_through_scenario import PassThroughScenario

def main():
    # 1. Setup CARLA Connection
    client = carla.Client('localhost', 2000)
    client.set_timeout(10.0)
    world = client.get_world()

    # 2. Setup Scenario Manager
    scenario_manager = ScenarioManager()
    
    # Important: Initialize CarlaDataProvider so the scenario can access the world/map
    CarlaDataProvider.set_client(client)
    CarlaDataProvider.set_world(world)
    CarlaDataProvider.set_traffic_manager_port(8000)

    # 3. Define a dummy config (ScenarioRunner usually parses this from XML, 
    # but for a minimal python-only test, we pass an object or None)
    config = None 

    try:
        print("Loading Scenario...")
        # Instantiate the scenario
        scenario = PassThroughScenario(world, [], config, debug_mode=False)
        
        # Load it into the manager
        scenario_manager.load_scenario(scenario)
        
        print("Running Scenario...")
        # This blocks until the behavior tree finishes (vehicle reaches goal)
        scenario_manager.run_scenario()

    except Exception as e:
        print(f"Scenario failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        print("Cleaning up...")
        if scenario is not None:
            scenario.remove_all_actors()
        
        CarlaDataProvider.cleanup()
        print("Done.")

if __name__ == '__main__':
    main()