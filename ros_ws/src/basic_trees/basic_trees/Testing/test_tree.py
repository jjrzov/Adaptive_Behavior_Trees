# ROS2-less implementation for algorithm testing

import py_trees

from basic_trees.Conditions.condition import Condition
from basic_trees.Actions import TestAction
from basic_trees.traverse import *
from basic_trees.action_scorer import ConditionCompletionScorer, TimeScorer
from basic_trees.algorithms import prune, expand

from basic_trees.Testing.setup_tests import generateLiterals, generateSolution, printTestSet

counter = 0


def createRoot(goal_state):
    # Create the root sequence
    goal_condition = list(goal_state)
    root = Condition(f"goal\n{sorted(goal_condition)}", goal_condition)

    return root


def setupWorld(blackboard, init_state):
    # Dynamic world state
    if blackboard.is_registered(key="world_state", access=py_trees.common.Access.WRITE):
        # Key already exists, need to reset it
        blackboard.unset("world_state")
    else:
        blackboard.register_key(key="world_state", access=py_trees.common.Access.WRITE)
    
    blackboard.world_state = init_state # init_state should be a set


def getAction(action_str, action_database):
    # Converts action name as a string to action object
    return TestAction(name=action_str, action_database=action_database)


def runTree(init_state, goal_state, action_database, traverse=BFS(), scorer=None):
    # Create the tree
    root = createRoot(goal_state)
    tree = py_trees.trees.BehaviourTree(
        root=root,
    )

    # Initialise the blackboard BEFORE setting up the tree
    blackboard = py_trees.blackboard.Client(name="Init")

    setupWorld(blackboard, init_state) # Define world literals
    init_state_snapshot = set(blackboard.world_state)   # copy, not alias

    # Set up the tree
    tree.setup()

    traverse = DFS()            # EDIT traversal function here

    
    expanded_literals = set()
    total_prunes = 0
    total_duplicates = 0
    condition_size_trace = []  # len(c.preconditions) for each condition expanded, in order
    branching_trace = []  # len(sorted_actions) for each corresponding expand() call
    superset_trace = []
    expansion_count = 0
    tick_count = 0
    drift_first_expansion = None   # expansion index where state first differs from s0
    drift_ticks = 0                # ticks after which state != s0
    fired_before_final = 0         # ticks that mutated state but did not end the loop

    while root.status != py_trees.common.Status.SUCCESS:
        # Handle tree returning RUNNING or FAILURE
        tree.tick()

        tick_count += 1

        drifted = (blackboard.world_state != init_state_snapshot)

        if drifted:
            drift_ticks += 1
            if drift_first_expansion is None:
                drift_first_expansion = expansion_count
            if root.status == py_trees.common.Status.FAILURE:
                # State changed but tree still failing -> next expand() runs
                # against a mutated world, which Algorithm 2 never does.
                fired_before_final += 1


        # print(f"--- tick ---")
        # print(f"status: {root.status}")
        # print(f"world_state: {blackboard.world_state}")


        if root.status == py_trees.common.Status.FAILURE:
            # Expand when tree returns failure
            next_condition = traverse.getNextCondition(root, expanded_literals)

            if next_condition == None:
                # print("No more conditions to expand - unsolvable")
                return False
            
            # print(f"next_condition: {next_condition.name}")

            # Add condition literals to expanded set
            expanded_literals.add(frozenset(next_condition.preconditions))  # Needs to be frozen to keep literals grouped as conditions
            
            condition_size_trace.append(len(next_condition.preconditions))

            root, dup_count, branching_factor, superset_count = expand(root, next_condition, action_database, getAction, scorer)

            branching_trace.append(branching_factor)
            superset_trace.append(superset_count)
            total_duplicates += dup_count
            total_prunes += prune(root, expanded_literals)
            expansion_count += 1

            # prune(root, expanded_literals)  # Remove sequence structures that have already been expanded elsewhere
            tree.root = root

    # py_trees.display.render_dot_tree(root, name=f"test_tree {counter}")
    root.total_prunes = total_prunes
    root.total_duplicates = total_duplicates
    root.condition_size_trace = condition_size_trace
    root.branching_trace = branching_trace
    root.superset_trace = superset_trace
    root.expansion_count = expansion_count
    root.tick_count = tick_count
    root.drift_first_expansion = (
        drift_first_expansion if drift_first_expansion is not None else -1
    )
    root.drift_ticks = drift_ticks
    root.fired_before_final = fired_before_final
    return root


def getNodeCount(root):
    # Traverse the entire tree and count the total amount of nodes
    q = []  # Initialize queue
    q.append(root)  # Add start node to queue
    
    count = 0

    while len(q) != 0:
        # Keep searching while queue is not empty
        node = q.pop(0)
        count += 1

        if isinstance(node, py_trees.composites.Composite):
            # Only composite types (actions) have children
            q.extend(node.children)

    # print("Total Number of Nodes: ", count, "\n")
    return count

def main():
    # Generate Dataset
    all_literals = generateLiterals(10)
    states_database, action_database = generateSolution(all_literals, 50, 10)
    printTestSet(all_literals, states_database, action_database)

    # Run the Tree
    root = runTree(states_database[0].copy(), states_database[-1], action_database)

    # Gather Data
    getNodeCount(root)


if __name__ == '__main__':
    main()