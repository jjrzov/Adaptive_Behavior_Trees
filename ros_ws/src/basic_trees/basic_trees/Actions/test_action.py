import py_trees


class TestAction(py_trees.behaviour.Behaviour):
    def __init__(self, name, action_database=None):
        super().__init__(name=name)

        self.action_database = action_database

        # Set up blackboard client
        self.blackboard = self.attach_blackboard_client(name=name)

        # Read world state
        self.blackboard.register_key(
            key="world_state",
            access=py_trees.common.Access.WRITE
        )

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
        pass