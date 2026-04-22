import py_trees
import py_trees_ros


class PaperMove(py_trees.behaviour.Behaviour):
    def __init__(self, name, remove_literals, add_literals):
        super().__init__(name=name)

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

        return

    def update(self) -> py_trees.common.Status:
        # Called EVERY TICK while this behaviour is active  
        for literal in self.add_literals:
            self.blackboard.world_state.add(literal) # add conditions

        for literal in self.remove_literals:
            self.blackboard.world_state.discard(literal) # delete conditions

        return py_trees.common.Status.SUCCESS

    def terminate(self, new_status: py_trees.common.Status):
        # Called when leaving this behaviour for ANY reason
        pass


class PaperMove_b_ab(PaperMove):
    def __init__(self):
        super().__init__("move(b, ab)", {"Free(ab)", "At(b, pb)"}, {"At(b, ab)"})

class PaperMove_s_ab(PaperMove):
    def __init__(self):
        super().__init__("move(s, ab)", {"Free(ab)", "At(s, ps)"}, {"At(s, ab)", "WayClear"})

class PaperMove_s_as(PaperMove):
    def __init__(self):
        super().__init__("move(s, as)", {"Free(as)", "At(s, ps)"}, {"At(s, as)", "WayClear"})