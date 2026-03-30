import py_trees
import py_trees_ros

class Load(py_trees.behaviour.Behaviour):
    def __init__(self, name="Load"):
        super().__init__(name=name)
        
        # Set up blackboard client
        self.blackboard = self.attach_blackboard_client(name=name)

        # Read which room robot is currently in
        self.blackboard.register_key(
            key="current_room",
            access=py_trees.common.Access.READ
        )
        # Read which room package is in
        self.blackboard.register_key(
            key="package_1_pickup_room",
            access=py_trees.common.Access.READ
        )
        # Read/Write if robot has package
        self.blackboard.register_key(
            key="has_package_1",
            access=py_trees.common.Access.WRITE
        )

    def setup(self, **kwargs):
        # Called ONCE when the tree starts up
        try:
            self.node = kwargs['node']
        except KeyError as e:
            raise KeyError("Missing ROS node") from e

    def initialise(self):
        # Called EACH TIME this behaviour becomes active
        # Use this to reset state and kick off any requests
        pass

    def update(self) -> py_trees.common.Status:
        # Called EVERY TICK while this behaviour is active
        if (self.blackboard.package_1_pickup_room == self.blackboard.current_room) and (self.blackboard.has_package_1 == False):
                self.blackboard.has_package_1 = True
                return py_trees.common.Status.SUCCESS
        
        return py_trees.common.Status.FAILURE

    def terminate(self, new_status: py_trees.common.Status):
        # Called when leaving this behaviour for ANY reason
        # Use this for cleanup - cancel goals, stop motors etc.
        pass