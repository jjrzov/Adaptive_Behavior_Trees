import py_trees

from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from action_msgs.msg import GoalStatus


class NavAction(py_trees.behaviour.Behaviour):
    def __init__(self, name, nav_client, room_info):
        super().__init__(name=name)
        self.nav_client = nav_client
        self.room_info = room_info

        # Set up blackboard client
        self.blackboard = self.attach_blackboard_client(name=name)

        # Read world state
        self.blackboard.register_key(
            key="world_state",
            access=py_trees.common.Access.WRITE
        )

        self.goal_handle = None
        self.result = None


    def setup(self, **kwargs):
        # Called ONCE when the tree starts up
        try:
            self.node = kwargs['node']

            # Room Locations
            self.goal_msg = NavigateToPose.Goal()
            self.goal_msg.pose.header.frame_id = 'map'
            self.goal_msg.pose.header.stamp = None
            self.goal_msg.pose.pose.position.x = self.room_info['goal'][0]
            self.goal_msg.pose.pose.position.y = self.room_info['goal'][1]
            self.goal_msg.pose.pose.orientation.w = self.room_info['goal'][2]

            self.room_literal = self.room_info['literal']
            self.nav_state = False
            self.future = None

        except KeyError as e:
            raise KeyError("Missing ROS node") from e


    def initialise(self):
        # Called EACH TIME this action becomes active
   
        # Reset parameters for other nav actions goals
        self.goal_handle = None
        self.result = None

        self.goal_msg.pose.header.stamp = self.node.get_clock().now().to_msg()
        self.future = self.nav_client.send_goal_async(self.goal_msg)

        self.nav_state = 'RUNNING'
        return


    def update(self) -> py_trees.common.Status:
        # Called EVERY TICK while this behaviour is active  
        if (self.nav_state == 'COMPLETED'):
            return py_trees.common.Status.SUCCESS
        elif (self.nav_state == 'FAILED'):
            return py_trees.common.Status.FAILURE
        else:
            if (self.future.done()):
                self.goal_handle = self.future.result()
                if self.goal_handle.accepted:
                    if (self.result == None):
                        self.result = self.goal_handle.get_result_async()

                    if (self.result.done()):
                        if (self.result.result().status == GoalStatus.STATUS_SUCCEEDED):
                            # Observed literals so don't edit the worldstate in here, but in background process
                            return py_trees.common.Status.SUCCESS
                        else:
                            return py_trees.common.Status.FAILURE
                    
                    return py_trees.common.Status.RUNNING
                        
                else:
                    return py_trees.common.Status.FAILURE
                
            return py_trees.common.Status.RUNNING


    def terminate(self, new_status: py_trees.common.Status):
        # Called when leaving this behaviour for ANY reason
        # Use this for cleanup
        if self.goal_handle != None:
            if self.goal_handle.accepted and new_status == py_trees.common.Status.INVALID:
                self.goal_handle.cancel_goal_async()