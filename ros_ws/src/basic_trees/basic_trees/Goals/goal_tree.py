# ROS2-less implementation for algorithm testing

import py_trees

from basic_trees.Conditions.condition import Condition
from basic_trees.Actions import TestAction
from basic_trees.traverse import BFS, DFS
from basic_trees.action_scorer import ConditionCompletionScorer, TimeScorer
from basic_trees.algorithms import prune, expand

from basic_trees.Goals.goal_types import *

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


def runTree(init_state, goal_term, action_database, traverse=BFS(), scorer=None):
    # Create the base tree from the goal
    root = buildBaseTree(goal_term)
    tree = py_trees.trees.BehaviourTree(
        root=root,
    )

    # Initialise the blackboard BEFORE setting up the tree
    blackboard = py_trees.blackboard.Client(name="Init")

    setupWorld(blackboard, init_state) # Define world literals

    # Set up the tree
    tree.setup()

    # traverse = DFS()            # EDIT traversal function here
    # scorer = ConditionCompletionScorer(Action_Database)     # EDIT cost metric for adding actions in expand here

    expanded_literals = set()

    while root.status != py_trees.common.Status.SUCCESS:
        # Handle tree returning RUNNING or FAILURE
        tree.tick()


        print(f"--- tick ---")
        print(f"status: {root.status}")
        print(f"world_state: {blackboard.world_state}")


        if root.status == py_trees.common.Status.FAILURE:
            # Expand when tree returns failure
            next_condition = traverse.getNextCondition(root, expanded_literals)

            if next_condition == None:
                print("No more conditions to expand - unsolvable")
                return False
            
            print(f"next_condition: {next_condition.name}")

            # Add condition literals to expanded set
            expanded_literals.add(frozenset(next_condition.preconditions))  # Needs to be frozen to keep literals grouped as conditions
            
            root = expand(root, next_condition, action_database, getAction, scorer)
            prune(root, expanded_literals)  # Remove sequence structures that have already been expanded elsewhere
            tree.root = root

    py_trees.display.render_dot_tree(root, name=f"test_tree {counter}")
    return root


def main():
    eq = AND('a', AND('b', AND('c', AND('d', OR('e', 'f')))))

    tree = buildBaseTree(eq)
    py_trees.display.render_dot_tree(tree, name=f"Goal_Base_Tree")


if __name__ == '__main__':
    main()