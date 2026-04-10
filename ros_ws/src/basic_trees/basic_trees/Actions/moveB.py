import py_trees
import py_trees_ros
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from action_msgs.msg import GoalStatus

class MoveB(py_trees.behaviour.Behaviour):
    def __init__(self, name="MoveB"):
        super().__init__(name=name)

        # Set up blackboard client
        self.blackboard = self.attach_blackboard_client(name=name)

        # Read which room robot is currently in
        self.blackboard.register_key(
            key="current_room",
            access=py_trees.common.Access.WRITE
        )

    def setup(self, **kwargs):
        # Called ONCE when the tree starts up
        try:
            self.node = kwargs['node']

            # Room Locations
            self.goal_msg = NavigateToPose.Goal()
            self.goal_msg.pose.header.frame_id = 'map'
            self.goal_msg.pose.header.stamp = None
            self.goal_msg.pose.pose.position.x = -2.0
            self.goal_msg.pose.pose.position.y = 5.0
            self.goal_msg.pose.pose.orientation.w = 1.0

            self.goal_room = 'at_B'
            self.status = False
            self.future = None
            
            # Set up action client
            self.action_client = ActionClient(self.node, NavigateToPose, 'navigate_to_pose')

            self.action_client.wait_for_server()    # Wait for action server to be ready (BLOCKING)

        except KeyError as e:
            raise KeyError("Missing ROS node") from e

    def initialise(self):
        # Called EACH TIME this behaviour becomes active

        if (self.goal_room in self.blackboard.world_state):
            self.status = 'COMPLETED'
        else:
            self.goal_msg.pose.header.stamp = self.node.get_clock().now().to_msg()
            self.future = self.action_client.send_goal_async(self.goal_msg)

            self.status = 'RUNNING'
        
        self.result = None
        self.goal_handle = None

        return

    def update(self) -> py_trees.common.Status:
        # Called EVERY TICK while this behaviour is active  
        if (self.status == 'COMPLETED'):
            return py_trees.common.Status.SUCCESS
        elif (self.status == 'FAILED'):
            return py_trees.common.Status.FAILURE
        else:
            if (self.future.done()):
                self.goal_handle = self.future.result()
                if self.goal_handle.accepted:
                    if (self.result == None):
                        self.result = self.goal_handle.get_result_async()

                    if (self.result.done()):
                        if (self.result.result().status == GoalStatus.STATUS_SUCCEEDED):
                            self.blackboard.world_state.add("at_B") # add conditions

                            self.blackboard.world_state.discard("at_A") # delete conditions
                            self.blackboard.world_state.discard("at_C")
                            return py_trees.common.Status.SUCCESS
                        elif (self.result.result().status == GoalStatus.STATUS_ABORTED or self.result.result().status == GoalStatus.STATUS_CANCELLED):
                            return py_trees.common.Status.FAILURE
                    else:
                        return py_trees.common.Status.RUNNING
                        
                else:
                    return py_trees.common.Status.FAILURE
                
            return py_trees.common.Status.RUNNING

    def terminate(self, new_status: py_trees.common.Status):
        # Called when leaving this behaviour for ANY reason
        # Use this for cleanup - cancel goals, stop motors etc.
        if self.goal_handle != None:
            if self.goal_handle.accepted:
                self.goal_handle.cancel_goal_async()