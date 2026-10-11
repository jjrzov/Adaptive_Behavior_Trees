import py_trees

from nav2_msgs.action import NavigateToPose
from action_msgs.msg import GoalStatus


OBSERVE_TIMEOUT = 5.0   # Seconds after Nav2 succeeds to wait for the room literal

class NavAction(py_trees.behaviour.Behaviour):
    '''
    Drive to a room's goal pose with Nav2.

    The room literal (e.g. at_A) is a perceived literal, written to the world
    state by the PoseObserver and never by this action. To keep the action
    model of Problem 1 (effects hold when the action succeeds), the action
    returns SUCCESS only once both hold
        1. Nav2 reports the goal reached
        2. the target room literal is in the world state
    It stays RUNNING while Nav2 has succeeded but the observer has not yet
    reported the room, and returns FAILURE if the literal does not appear
    within OBSERVE_TIMEOUT seconds.
    '''
        
    def __init__(self, name, nav_client, room_costs, room_info, room_key):
        super().__init__(name=name)
        self.nav_client = nav_client
        self.room_info = room_info
        self.room_costs = room_costs
        self.room_key = room_key

        # Set up blackboard client
        self.blackboard = self.attach_blackboard_client(name=name)

        # Read world state
        self.blackboard.register_key(
            key="world_state",
            access=py_trees.common.Access.WRITE
        )

        # Read current room
        self.blackboard.register_key(
            key="latest_room_reading",
            access=py_trees.common.Access.READ
        )

        self.goal_handle = None
        self.result = None
        self.result_future = None
        self.reached_at = None      # Clock time at which Nav2 reported success


    def setup(self, **kwargs):
        # Called ONCE when the tree starts up
        try:
            self.node = kwargs['node']
        except KeyError as e:
            raise KeyError("Missing ROS node") from e

        # Room Locations
        self.msg = NavigateToPose.Goal()
        self.msg.pose.header.frame_id = 'map'
        self.msg.pose.pose.position.x = self.room_info['goal'][0]
        self.msg.pose.pose.position.y = self.room_info['goal'][1]
        self.msg.pose.pose.orientation.w = self.room_info['goal'][2]


    def getCost(self):
        # Return the cost of the action which changes depending on current room
        return self.room_costs.getRoomCost(
            self.blackboard.latest_room_reading, 
            self.room_key
        )
        
    def initialise(self):
        # Called EACH TIME this action becomes active: send a new goal
        self.goal_handle = None
        self.result_future = None
        self.reached_at = None

        self.msg.pose.header.stamp = self.node.get_clock().now().to_msg()
        self.send_future = self.nav_client.send_goal_async(self.msg)


    def _elapsedSinceReached(self):
        return (self.node.get_clock().now() - self.reached_at).nanoseconds * 1e-9


    def update(self) -> py_trees.common.Status:
        # Called EVERY TICK while this behaviour is active

        # Waiting for Nav2 to accept the goal
        if not self.send_future.done():
            return py_trees.common.Status.RUNNING

        if self.goal_handle is None:
            self.goal_handle = self.send_future.result()

            if not self.goal_handle.accepted:
                return py_trees.common.Status.FAILURE

            self.result_future = self.goal_handle.get_result_async()

        # Still driving
        if not self.result_future.done():
            return py_trees.common.Status.RUNNING

        if self.result_future.result().status != GoalStatus.STATUS_SUCCEEDED:
            return py_trees.common.Status.FAILURE

        # Nav2 has reached the pose. The effect is the room literal, so success
        # waits until the observer has written it to the world state
        if self.room_info['literal'] in self.blackboard.world_state:
            return py_trees.common.Status.SUCCESS

        if self.reached_at is None:
            self.reached_at = self.node.get_clock().now()

        if self._elapsedSinceReached() > OBSERVE_TIMEOUT:
            self.node.get_logger().warn(
                f"{self.name}: reached goal pose but '{self.room_info['literal']}' "
                f"was not observed within {OBSERVE_TIMEOUT} s")
            return py_trees.common.Status.FAILURE

        return py_trees.common.Status.RUNNING


    def terminate(self, new_status: py_trees.common.Status):
        # Interrupted by a higher-priority branch: cancel the goal while Nav2 is
        # still driving. Once Nav2 has finished there is nothing to cancel.
        interrupted = new_status == py_trees.common.Status.INVALID
        driving = (self.goal_handle is not None and self.goal_handle.accepted
                   and self.result_future is not None and not self.result_future.done())

        if interrupted and driving:
            self.goal_handle.cancel_goal_async()