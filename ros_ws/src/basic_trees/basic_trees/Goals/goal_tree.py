# ROS2-less implementation for algorithm testing

import py_trees

from basic_trees.Conditions.condition import Condition
from basic_trees.Actions import TestAction
from basic_trees.traverse import *
from basic_trees.action_scorer import ConditionCompletionScorer, TimeScorer
from basic_trees.algorithms import prune, expand

from basic_trees.Goals.goal_types import *


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

    expanded_literals = set()
    expansion_count = 0

    while root.status != py_trees.common.Status.SUCCESS:
        # Handle tree returning RUNNING or FAILURE
        tree.tick()


        # print(f"--- tick ---")
        # print(f"status: {root.status}")
        # print(f"world_state: {blackboard.world_state}")


        if root.status == py_trees.common.Status.FAILURE:
            # Expand when tree returns failure
            next_condition = traverse.getNextCondition(root, expanded_literals)

            if next_condition == None:
                # print("No more conditions to expand - unsolvable")
                return False, expansion_count, set()
            
            # print(f"next_condition: {next_condition.name}")

            # Add condition literals to expanded set
            expanded_literals.add(frozenset(next_condition.preconditions))  # Needs to be frozen to keep literals grouped as conditions
            
            root = expand(root, next_condition, action_database, getAction, scorer)

            prune(root, expanded_literals)  # Remove sequence structures that have already been expanded elsewhere
            expansion_count += 1

            tree.root = root

    # py_trees.display.render_dot_tree(root, name=f"Paper_Test_w_DEAD_OR")
    return root, expansion_count, set(blackboard.world_state)


def runSharedTree(init_state, disjunct, action_database, traverse=BFS(), scorer=None):
    # Same as runTree but takes as input the set of expanded conditions so that
    # they can be shared across all of the separate disjunct trees
    
    # Create the tree
    root = createRoot(disjunct)
    tree = py_trees.trees.BehaviourTree(
        root=root,
    )

    # Initialise the blackboard BEFORE setting up the tree
    blackboard = py_trees.blackboard.Client(name="Init")

    setupWorld(blackboard, init_state) # Define world literals

    # Set up the tree
    tree.setup()

    expansion_count = 0
    expanded_literals = set()
    
    while root.status != py_trees.common.Status.SUCCESS:
        # Handle tree returning RUNNING or FAILURE
        tree.tick()


        # print(f"--- tick ---")
        # print(f"status: {root.status}")
        # print(f"world_state: {blackboard.world_state}")


        if root.status == py_trees.common.Status.FAILURE:
            # Expand when tree returns failure
            next_condition = traverse.getNextCondition(root, expanded_literals)

            if next_condition == None:
                # print("No more conditions to expand - unsolvable")
                return False, expansion_count, set()
            
            # print(f"next_condition: {next_condition.name}")

            # Add condition literals to expanded set
            expanded_literals.add(frozenset(next_condition.preconditions))  # Needs to be frozen to keep literals grouped as conditions

            root = expand(root, next_condition, action_database, getAction, scorer)

            prune(root, expanded_literals)
            expansion_count += 1

            tree.root = root

    # py_trees.display.render_dot_tree(root, name=f"test_tree {counter}")
    return root, expansion_count, set(blackboard.world_state)


def runDNF(init_state, disjuncts, action_db, traverse=BFS()):
    # Create all the trees for each disjunct and connect them
    subtrees = []
    expansions = 0

    for d in disjuncts:
        # Create tree for each disjunct
        root, exp, _ = runSharedTree(init_state.copy(), d, action_db, traverse) # Each tree needs the same init state

        if root is False:
            # Not solvable, try next disjunct
            print(f"Not Solvable\tPer Disjunct Expansions: {exp}\n")
            continue

        subtrees.append(root)
        expansions += exp

    if not subtrees:
        # None of the subtrees were solvable
        return False, expansions, set()

    selector_root = py_trees.composites.Selector(name="DNF JOIN", memory=False)
    selector_root.add_children(subtrees)

    return selector_root, expansions, set()


def main():
    # eq = OR(AND("L1", "L2"), "At(b, ab)")
    # tree = buildBaseTree(eq)
    # py_trees.display.render_dot_tree(tree, name=f"Goal_Base_Tree")

    goal = OR(AND("L1", "L2"), "At(b, ab)")
    init_state = {"At(b, pb)", "At(s, ps)", "Free(ab)", "Free(as)"}

    action_database = {
        "move(b, ab)" : {"pre" : ["Free(ab)", "WayClear"],    "add" : ["At(b, ab)"],               "del" : ["Free(ab)", "At(b, pb)"]},
        "move(s, ab)" : {"pre" : ["Free(ab)"],                "add" : ["At(s, ab)", "WayClear"],   "del" : ["Free(ab)", "At(s, ps)"]},
        "move(s, as)" : {"pre" : ["Free(as)"],                "add" : ["At(s, as)", "WayClear"],   "del" : ["Free(as)", "At(s, ps)"]},
        }


    action_database["Action_L1"] = {"pre": set(), "add": {"L1"}, "del": set()}
    action_database["Action_L2"] = {"pre": set(), "add": {"L2"}, "del": set()}

    root, _ = runTree(init_state, goal, action_database)

if __name__ == '__main__':
    main()