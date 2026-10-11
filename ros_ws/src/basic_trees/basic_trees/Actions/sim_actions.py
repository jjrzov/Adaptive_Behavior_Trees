import py_trees
import math

from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose, Spin, Wait
from basic_trees.Actions import Load, Unload, NavAction
from basic_trees.Actions.behavior_actions import BehaviorAction, spinGoal, waitGoal


SCAN_YAW = 2 * math.pi      # One full rotation in place
SCAN_ALLOWANCE = 30         # Seconds before the spin is abandoned
LOAD_SECONDS = 5.0          # Dwell time for loading
UNLOAD_SECONDS = 5.0


class SimActionFactory:
    def __init__(self, node, action_database, pose_map, room_costs):
        self.node = node
        self.action_database = action_database
        self.pose_map = pose_map
        self.room_costs = room_costs

        # One client per server, shared by every action instance that uses it
        self.nav_client = self._client(NavigateToPose, 'navigate_to_pose')
        self.spin_client = self._client(Spin, 'spin')
        self.wait_client = self._client(Wait, 'wait')


        self.action_registry = {
            "scan"   : self._make_behavior_action("scan", self.spin_client,
                                                    lambda: spinGoal(SCAN_YAW, SCAN_ALLOWANCE)),
            "load"   : self._make_behavior_action("load", self.wait_client,
                                                    lambda: waitGoal(LOAD_SECONDS)),
            "unload_A" : self._make_behavior_action("unload_A", self.wait_client,
                                                    lambda: waitGoal(UNLOAD_SECONDS)),
            "unload_C" : self._make_behavior_action("unload_C", self.wait_client,
                                                    lambda: waitGoal(UNLOAD_SECONDS)),
            "move_A" : self._make_nav_action("move_A", "A"),
            "move_B" : self._make_nav_action("move_B", "B"),
            "move_C" : self._make_nav_action("move_C", "C"),
        }


    def _client(self, action_type, server_name):
        client = ActionClient(self.node, action_type, server_name)
        if not client.wait_for_server(timeout_sec=15.0):
            raise RuntimeError(f"FAILED TO START NAV2 ACTION CLIENT FOR '{server_name}'")
        return client
    

    def _make_nav_action(self, action_str, map_key):
        def build():    # Need to return the function not an instance thus build()
            action = NavAction(
                        name=action_str,
                        nav_client=self.nav_client,
                        room_costs=self.room_costs,
                        room_info=self.pose_map[map_key],
                        room_key=map_key,
            )

            action.setup(node=self.node)
            return action
        return build


    def _make_behavior_action(self, action_str, client, goal_builder):
        def build():
            action = BehaviorAction(
                        name=action_str,
                        client=client,
                        goal_builder=goal_builder,
                        action_database=self.action_database,
            )

            action.setup(node=self.node)
            return action
        return build


    def _make_blackboard_action(self, action_class):
        def build():
            return action_class(action_database=self.action_database)
        return build


    def __call__(self, action_str, action_database):
        # Legacy call to work with expand()
        return self.action_registry[action_str]()