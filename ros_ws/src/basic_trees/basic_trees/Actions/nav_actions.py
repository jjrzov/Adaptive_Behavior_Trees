import py_trees

from nav2_msgs.action import NavigateToPose
from action_msgs.msg import GoalStatus


class NavAction(py_trees.behaviour.Behaviour):
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


    def setup(self, **kwargs):
        # Called ONCE when the tree starts up
        try:
            self.node = kwargs['node']

            # Room Locations
            self.msg = NavigateToPose.Goal()
            self.msg.pose.header.frame_id = 'map'
            self.msg.pose.pose.position.x = self.room_info['goal'][0]
            self.msg.pose.pose.position.y = self.room_info['goal'][1]
            self.msg.pose.pose.orientation.w = self.room_info['goal'][2]

            self.nav_state = False
            self.future = None

        except KeyError as e:
            raise KeyError("Missing ROS node") from e


    def getCost(self):
        # Return the cost of the action which changes depending on current room
        return self.room_costs.getRoomCost(
            self.blackboard.latest_room_reading, 
            self.room_key
        )
        
    def initialise(self):
        # Called EACH TIME this action becomes active
   
        # Reset parameters for other nav actions goals
        self.goal_handle = None
        self.result = None

        self.msg.pose.header.stamp = self.node.get_clock().now().to_msg()
        self.future = self.nav_client.send_goal_async(self.msg)

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
                    if (self.result is None):
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
        if self.goal_handle is not None:    # Has to be is not instead of != to bypass None blow up
            if self.goal_handle.accepted and new_status == py_trees.common.Status.INVALID:
                self.goal_handle.cancel_goal_async()