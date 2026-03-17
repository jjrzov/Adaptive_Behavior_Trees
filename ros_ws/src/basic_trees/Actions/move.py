import py_trees
import py_trees_ros
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from action_msgs.msg import GoalStatus

class Move(py_trees.behaviour.Behaviour):
    def __init__(self, name="Move", goal_room=None):
        super().__init__(name=name)
        self.goal_room = goal_room

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
            self.room_A = NavigateToPose.Goal()
            self.room_A.pose.header.frame_id = 'map'
            self.room_A.pose.header.stamp = None
            self.room_A.pose.pose.position.x = 2.0
            self.room_A.pose.pose.position.y = 1.0
            self.room_A.pose.pose.orientation.w = 1.0

            self.room_B = NavigateToPose.Goal()
            self.room_B.pose.header.frame_id = 'map'
            self.room_B.pose.header.stamp = None
            self.room_B.pose.pose.position.x = -2.0
            self.room_B.pose.pose.position.y = 5.0
            self.room_B.pose.pose.orientation.w = 1.0

            self.room_C = NavigateToPose.Goal()
            self.room_C.pose.header.frame_id = 'map'
            self.room_C.pose.header.stamp = None
            self.room_C.pose.pose.position.x = 4.0
            self.room_C.pose.pose.position.y = -3.0
            self.room_C.pose.pose.orientation.w = 1.0

            self.status = False
            self.future = None
            
            # Set up action client
            self.action_client = ActionClient(self.node, NavigateToPose, 'navigate_to_pose')

            self.action_client.wait_for_server()    # Wait for action server to be ready (BLOCKING)

        except KeyError as e:
            raise KeyError("Missing ROS node") from e

    def initialise(self):
        # Called EACH TIME this behaviour becomes active

        # Check if valid input was given
        if self.goal_room == None:
            self.status = 'FAILED'

        if (self.blackboard.current_room == self.goal_room):
            self.status = 'COMPLETED'
        else:
            if self.goal_room == 'A':
                goal_msg = self.room_A
            elif self.goal_room == 'B':
                goal_msg = self.room_B
            else:
                goal_msg = self.room_C

            goal_msg.pose.header.stamp = self.node.get_clock().now().to_msg()
            self.future = self.action_client.send_goal_async(goal_msg)

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
                            self.blackboard.current_room = self.goal_room
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