import py_trees

from action_msgs.msg import GoalStatus
from builtin_interfaces.msg import Duration
from nav2_msgs.action import Spin, Wait


def spinGoal(target_yaw, allowance_s):
    # Rotate in place by target_yaw radians, giving up after allowance_s seconds
    goal = Spin.Goal()
    goal.target_yaw = float(target_yaw)
    goal.time_allowance = Duration(sec=int(allowance_s))
    return goal


def waitGoal(seconds):
    # Hold position for the given time
    goal = Wait.Goal()
    whole = int(seconds)
    goal.time = Duration(sec=whole, nanosec=int((seconds - whole) * 1e9))
    return goal


class BehaviorAction(py_trees.behaviour.Behaviour):
    '''
    An action carried out by a Nav2 behavior server (spin, wait, backup).

    The behavior runs over many ticks, so the action returns RUNNING until the
    server reports a result. Its STRIPS effects are written to the world state
    in the same update that returns SUCCESS, and never while it is running.
    That is the action model of Problem 1 (effects take place when the action
    succeeds), so the soundness proposition's assumption holds by construction.
    '''

    def __init__(self, name, client, goal_builder, action_database):
        super().__init__(name=name)
        self.client = client                # Shared ActionClient for this behavior type
        self.goal_builder = goal_builder    # Callable returning a fresh goal message
        self.action_database = action_database

        self.blackboard = self.attach_blackboard_client(name=name)
        self.blackboard.register_key(
            key="world_state",
            access=py_trees.common.Access.WRITE
        )

        self.send_future = None
        self.goal_handle = None
        self.result_future = None


    def setup(self, **kwargs):
        # Called ONCE when the tree starts up
        try:
            self.node = kwargs['node']
        except KeyError as e:
            raise KeyError("Missing ROS node") from e


    def getCost(self):
        return self.action_database[self.name]['cost']


    def initialise(self):
        # Called EACH TIME this action becomes active: send a new goal
        self.goal_handle = None
        self.result_future = None
        self.send_future = self.client.send_goal_async(self.goal_builder())


    def update(self) -> py_trees.common.Status:
        # Waiting for the server to accept the goal
        if not self.send_future.done():
            return py_trees.common.Status.RUNNING

        if self.goal_handle is None:
            self.goal_handle = self.send_future.result()

            if not self.goal_handle.accepted:
                return py_trees.common.Status.FAILURE

            self.result_future = self.goal_handle.get_result_async()

        # Behavior still executing
        if not self.result_future.done():
            return py_trees.common.Status.RUNNING

        if self.result_future.result().status != GoalStatus.STATUS_SUCCEEDED:
            return py_trees.common.Status.FAILURE

        # Effects take place at the moment of success, in the update that reports it
        entry = self.action_database[self.name]

        for literal in entry['add']:
            self.blackboard.world_state.add(literal)

        for literal in entry['del']:
            self.blackboard.world_state.discard(literal)

        return py_trees.common.Status.SUCCESS


    def terminate(self, new_status: py_trees.common.Status):
        # Interrupted by a higher-priority branch: cancel the behavior on the server
        interrupted = new_status == py_trees.common.Status.INVALID
        running = (self.goal_handle is not None and self.goal_handle.accepted
                   and self.result_future is not None and not self.result_future.done())

        if interrupted and running:
            self.goal_handle.cancel_goal_async()