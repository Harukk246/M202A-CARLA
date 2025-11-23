import carla
import py_trees
from agents.navigation.global_route_planner import GlobalRoutePlanner

from srunner.scenarios.basic_scenario import BasicScenario
from srunner.scenariomanager.carla_data_provider import CarlaDataProvider
from srunner.scenariomanager.scenarioatomics.atomic_behaviors import (
    ActorTransformSetter, 
    ActorDestroy, 
    WaypointFollower
)

class PassThroughScenario(BasicScenario):
    """
    A minimal scenario where the ego vehicle autopilots (follows a route) 
    from a start point to a destination point.
    """

    def __init__(self, world, ego_vehicles, config, debug_mode=False, criteria_enable=True, timeout=600):
        self.world = world
        self.map = CarlaDataProvider.get_map()
        self.timeout = timeout
        
        # Route configuration
        self.target_speed = 10.0  # m/s (approx 36 km/h)
        self.route_plan = []
        
        super(PassThroughScenario, self).__init__(
            "PassThroughScenario",
            ego_vehicles,
            config,
            world,
            debug_mode,
            criteria_enable=criteria_enable
        )

    def _initialize_actors(self, config):
        """
        Selects start and end points and spawns the ego vehicle.
        """
        spawn_points = self.map.get_spawn_points()
        
        # Default configuration
        model = 'vehicle.tesla.model3' 
        color = None
        start_transform = spawn_points[0]

        # 1. Parse XML Configuration
        # We check 'if config' first because run_scenario.py passes None
        if config and hasattr(config, 'ego_vehicles') and config.ego_vehicles and len(config.ego_vehicles) > 0:
            ego_config = config.ego_vehicles[0]
            
            # Use model and color from XML
            model = ego_config.model
            color = ego_config.color
            
            # Check if XML has specific coordinates. 
            if abs(ego_config.transform.location.x) > 0.1 or abs(ego_config.transform.location.y) > 0.1:
                start_transform = ego_config.transform
                print(f"[Scenario] Using XML coordinates: {start_transform.location}")
            else:
                print(f"[Scenario] XML coordinates empty/zero. Overwriting with map spawn point.")
        else:
            print("[Scenario] No XML config present (or running standalone). Using default spawn.")

        # 2. Set Destination (Arbitrary for this demo)
        destination_transform = spawn_points[10] if len(spawn_points) > 10 else spawn_points[-1]

        # 3. Spawn Ego Vehicle
        self.ego_vehicle = CarlaDataProvider.request_new_actor(
            model, 
            start_transform,
            color=color
        )
        self.other_actors.append(self.ego_vehicle)

        # 4. Calculate Route
        # Using CARLA 0.9.10 API explicitly (GlobalRoutePlannerDAO)
        print("[Scenario] Using CARLA 0.9.10 GlobalRoutePlannerDAO.")
        from agents.navigation.global_route_planner_dao import GlobalRoutePlannerDAO
        dao = GlobalRoutePlannerDAO(self.map, 2.0)
        grp = GlobalRoutePlanner(dao)
        grp.setup()
        
        self.route_plan = grp.trace_route(
            start_transform.location, 
            destination_transform.location
        )
        
        print(f"[Scenario] Model: {model}, Color: {color}")
        print(f"[Scenario] Start: {start_transform.location}")
        print(f"[Scenario] End:   {destination_transform.location}")

    def _create_behavior(self):
        """
        The Behavior Tree:
        1. Set Initial Pose
        2. Follow the calculated route (Autopilot)
        3. Destroy vehicle upon completion
        """
        behavior = py_trees.composites.Sequence("PassThroughBehavior")

        # 1. Ensure vehicle is exactly at start
        start_condition = ActorTransformSetter(self.ego_vehicle, self.ego_vehicle.get_transform())
        
        # 2. Drive the route
        follow_route = WaypointFollower(
            self.ego_vehicle, 
            self.target_speed, 
            plan=self.route_plan,
            avoid_collision=True
        )

        # 3. Cleanup
        end_condition = ActorDestroy(self.ego_vehicle)

        behavior.add_child(start_condition)
        behavior.add_child(follow_route)
        behavior.add_child(end_condition)

        return behavior

    def _create_test_criteria(self):
        return []

    def __del__(self):
        self.remove_all_actors()