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
        
        # --- CONFIGURATION: Set Start and End ---
        # We simply pick the first spawn point as start, and the 10th as the goal.
        # You can change these indices to any valid spawn points on the map.
        start_transform = spawn_points[0]
        destination_transform = spawn_points[10] if len(spawn_points) > 10 else spawn_points[-1]

        # 1. Spawn Ego Vehicle
        self.ego_vehicle = CarlaDataProvider.request_new_actor(
            'vehicle.tesla.model3', 
            start_transform
        )
        self.other_actors.append(self.ego_vehicle)

        # 2. Calculate Route using CARLA's GlobalRoutePlanner
        # This generates the list of waypoints the WaypointFollower will use.
        grp = GlobalRoutePlanner(self.map, 2.0) # 2.0 is the resolution between waypoints
        self.route_plan = grp.trace_route(
            start_transform.location, 
            destination_transform.location
        )
        
        print(f"[Scenario] Route calculated: {len(self.route_plan)} waypoints.")
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
        # WaypointFollower takes the pre-calculated plan and handles steering/throttle
        follow_route = WaypointFollower(
            self.ego_vehicle, 
            self.target_speed, 
            plan=self.route_plan,
            avoid_collision=True # Standard autopilot collision avoidance
        )

        # 3. Cleanup
        end_condition = ActorDestroy(self.ego_vehicle)

        behavior.add_child(start_condition)
        behavior.add_child(follow_route)
        behavior.add_child(end_condition)

        return behavior

    def _create_test_criteria(self):
        """
        Empty criteria for a simple pass-through. 
        Add CollisionTest here if you want the scenario to fail on crash.
        """
        return []

    def __del__(self):
        """
        Cleanup actors if the object is deleted
        """
        self.remove_all_actors()