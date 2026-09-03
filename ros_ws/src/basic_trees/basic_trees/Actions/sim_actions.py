import py_trees

from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from basic_trees.Actions import Load, Unload, NavAction


class SimActionFactory:
    def __init__(self, node, action_database, pose_map):
        self.node = node
        self.action_database = action_database
        self.pose_map = pose_map

        self.nav_client = ActionClient(self.node, NavigateToPose, 'navigate_to_pose')
        if not self.nav_client.wait_for_server(timeout_sec=15.0):
            raise RuntimeError("FAILED TO START NAV2 ACTION CLIENT")

        self.action_registry = {
            "load"   : self._make_blackboard_action(Load),
            "unload" : self._make_blackboard_action(Unload),
            "move_A" : self._make_nav_action("move_A", "A"),
            "move_B" : self._make_nav_action("move_B", "B"),
            "move_C" : self._make_nav_action("move_C", "C"),
        }


    def _make_nav_action(self, action_str, map_key):
        def build():    # Need to return the function not an instance thus build()
            action = NavAction(
                        name=action_str,
                        nav_client=self.nav_client,
                        room_info=self.pose_map[map_key]
            )

            action.setup(node=self.node)
            return action
        return build()


    def _make_blackboard_action(self, action_class):
        def build():
            return action_class(action_database=self.action_database)
        return build()


    def __call__(self, action_str, action_database):
        # Legacy call to work with expand()
        return self.action_registry[action_str]()