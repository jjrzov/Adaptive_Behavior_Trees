import py_trees
import py_trees_ros

class Load(py_trees.behaviour.Behaviour):
    def __init__(self, name="load", action_database=None):
        super().__init__(name=name)
        self.name = name
        self.action_database = action_database
        
        # Set up blackboard client
        self.blackboard = self.attach_blackboard_client(name=name)

        # Read current world state
        self.blackboard.register_key(
            key="world_state",
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
        adding = self.action_database[self.name]['add']
        deleting = self.action_database[self.name]['del']

        for literal in adding:
            self.blackboard.world_state.add(literal)    # add conditions

        for literal in deleting:
            self.blackboard.world_state.discard(literal)    # delete conditions
                
        return py_trees.common.Status.SUCCESS
        

    def terminate(self, new_status: py_trees.common.Status):
        # Called when leaving this behaviour for ANY reason
        # Use this for cleanup - cancel goals, stop motors etc.
        pass