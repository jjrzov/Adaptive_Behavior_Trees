import py_trees
import py_trees_ros


class MockMove(py_trees.behaviour.Behaviour):
    def __init__(self, name, goal_room, remove_literals, add_literals):
        super().__init__(name=name)

        self.goal_room = goal_room
        self.add_literals = add_literals
        self.remove_literals = remove_literals

        # Set up blackboard client
        self.blackboard = self.attach_blackboard_client(name=name)

        # Read world state
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

        if (self.goal_room in self.blackboard.world_state):
            self.status = 'COMPLETED'
        else:
            self.status = 'RUNNING'
        
        self.counter = 0

        return

    def update(self) -> py_trees.common.Status:
        # Called EVERY TICK while this behaviour is active  
        if (self.status == 'COMPLETED') :
            return py_trees.common.Status.SUCCESS
        elif (self.counter == 0):
            
            for literal in self.add_literals:
                self.blackboard.world_state.add(literal) # add conditions

            for literal in self.remove_literals:
                self.blackboard.world_state.discard(literal) # delete conditions

            return py_trees.common.Status.SUCCESS
        else:
            self.counter += 1   # Fake running for a few ticks                
            return py_trees.common.Status.RUNNING

    def terminate(self, new_status: py_trees.common.Status):
        # Called when leaving this behaviour for ANY reason
        pass


class MockMoveA(MockMove):
    def __init__(self):
        super().__init__("MockMoveA", "at_A", {"at_B", "at_C"}, {"at_A"})

class MockMoveB(MockMove):
    def __init__(self):
        super().__init__("MockMoveB", "at_B", {"at_A", "at_C"}, {"at_B"})

class MockMoveC(MockMove):
    def __init__(self):
        super().__init__("MockMoveC", "at_C", {"at_A", "at_B"}, {"at_C"})