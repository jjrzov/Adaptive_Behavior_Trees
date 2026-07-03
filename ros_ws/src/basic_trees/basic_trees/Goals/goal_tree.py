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


def runTree(init_state, goal_state, action_database, traverse=BFS(), scorer=None):
    # Create the goal tree
    goal_root = buildGoalTree(goal_state)
    goal_tree = py_trees.trees.BehaviourTree(
        goal_root=goal_root,
    )

    # Create the tree to perform expand on
    expansion_root = createRoot(goal_state)
    expansion_tree = py_trees.trees.BehaviourTree(
        expansion_root=expansion_root,
    )


    # Initialise the blackboard BEFORE setting up the tree
    blackboard = py_trees.blackboard.Client(name="Init")

    setupWorld(blackboard, init_state) # Define world literals

    # Set up the tree
    goal_tree.setup()
    expansion_tree.setup()

    py_trees.display.render_dot_tree(goal_root, name=f"goal_tree")

    
    # traverse = DFS()            # EDIT traversal function here
    # scorer = ConditionCompletionScorer(Action_Database)     # EDIT cost metric for adding actions in expand here

    expanded_literals = set()

    while goal_root.status != py_trees.common.Status.SUCCESS:
        # Handle tree returning RUNNING or FAILURE
        goal_tree.tick()
        expansion_tree.tick()


        print(f"--- tick ---")
        print(f"status: {goal_root.status}")
        print(f"world_state: {blackboard.world_state}")


        if goal_root.status == py_trees.common.Status.FAILURE:
            # Expand when tree returns failure
            next_condition = traverse.getNextCondition(expansion_root, expanded_literals)

            if next_condition == None:
                print("No more conditions to expand - unsolvable")
                return False
            
            print(f"next_condition: {next_condition.name}")

            # Add condition literals to expanded set
            expanded_literals.add(frozenset(next_condition.preconditions))  # Needs to be frozen to keep literals grouped as conditions
            
            expansion_root = expand(expansion_root, next_condition, action_database, getAction, scorer)
            prune(expansion_root, expanded_literals)  # Remove sequence structures that have already been expanded elsewhere
            expansion_tree.root = expansion_root

    py_trees.display.render_dot_tree(expansion_root, name=f"test_tree {counter}")
    return expansion_root


# def main():
#     root = runTree(states_database[0].copy(), states_database[-1], action_database, 
#                    DFS(), ConditionCompletionScorer(action_database))

#     counter += 1
    
#     # Record Metrics for solved trees
#     if paper_root: 
#         getNodeCount(paper_root)
#     if root:
#         getNodeCount(root)

# if __name__ == '__main__':
#     main()