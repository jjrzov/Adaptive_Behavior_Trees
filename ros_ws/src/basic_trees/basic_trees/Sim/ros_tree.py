import py_trees
import py_trees_ros
import rclpy

from basic_trees.Conditions.condition import Condition
from basic_trees.Actions import Load, Unload, SimActionFactory
from basic_trees.Actions import MockMoveA, MockMoveB, MockMoveC
from basic_trees.traverse import BFS, DFS
from basic_trees.algorithms import prune, expand
from basic_trees.Goals.goal_tree import buildBaseTree
from basic_trees.Goals.goal_types import AND, OR
from basic_trees.Sim.observer import PoseObserver


MOCK = False    # Use mock actions or real actions


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
    # Now only used for MOCK trials, SimFactory handles real actions    
    action_map_mock = {
        "load"   : lambda: Load(action_database=action_database),
        "unload" : lambda: Unload(action_database=action_database),
        "move_A" : lambda: MockMoveA(),
        "move_B" : lambda: MockMoveB(),
        "move_C" : lambda: MockMoveC(),
    }
    
    return action_map_mock[action_str]()


def runTree(init_state, goal_state, action_database, pose_map, traverse=BFS()):
    # Create the tree
    root = buildBaseTree(goal_state)
    tree = py_trees_ros.trees.BehaviourTree(
        root=root,
        unicode_tree_debug=True
    )

    # Initialise the blackboard BEFORE setting up the tree
    blackboard = py_trees.blackboard.Client(name="Init")
    setupWorld(blackboard, init_state) # Define world literals

    # Set up the tree
    try:
        tree.setup(node_name="my_tree", timeout=15.0)
    except py_trees_ros.exceptions.TimedOutError as e:
        print("ERROR: TREE SETUP TIMED OUT\n")
        return False
    
    expanded_literals = set()
    curr_world_state = blackboard.world_state   # For printing world state as tree running

    if not MOCK:
        PoseObserver(tree.node, blackboard, pose_map)   # Start pose observer
        action_factory = SimActionFactory(tree.node, action_database, pose_map)

    while root.status != py_trees.common.Status.SUCCESS:    # TODO: Eventually should tick forever in case of disturbances
        # Handle tree returning RUNNING or FAILURE
        rclpy.spin_once(tree.node, timeout_sec=0)   # Need to spin for updates
        tree.tick()

        if blackboard.world_state != curr_world_state:
            print(f"--- tick ---")
            print(f"status: {root.status}")
            print(f"world_state: {blackboard.world_state}")
            curr_world_state = blackboard.world_state


        if root.status == py_trees.common.Status.FAILURE:
            # Expand when tree returns failure
            next_condition = traverse.getNextCondition(root, expanded_literals)

            if next_condition == None:
                print("No more conditions to expand - unsolvable")
                tree.shutdown() # Delete tree
                return False
            
            print(f"next_condition: {next_condition.name}")

            # Add condition literals to expanded set
            expanded_literals.add(frozenset(next_condition.preconditions))  # Needs to be frozen to keep literals grouped as conditions

            if MOCK:
                root = expand(root, next_condition, action_database, getAction)
            else:
                root = expand(root, next_condition, action_database, action_factory)

            prune(root, expanded_literals)  # Remove sequence structures that have already been expanded elsewhere

            tree.root = root

    py_trees.display.render_dot_tree(root, name="ROS_TREEs")
    tree.shutdown() # Delete tree
    return True


def main(args=None):
    rclpy.init(args=args)

    # Set enviroment
    init_state = {"empty", "at_B"}
    goal_state = AND("at_A")

    
    action_database = {
            "load"     : {"pre" : ["empty", "at_A"],            "add" : ["full"],                           "del" : ["empty"]},
            "unload"   : {"pre" : ["full", "at_B"],             "add" : ["empty", "package_delivered"],     "del" : ["full"]},
            "move_A"   : {"pre" : [],                           "add" : ["at_A"],                           "del" : ["at_B", "at_C"]},
            "move_B"   : {"pre" : [],                           "add" : ["at_B"],                           "del" : ["at_A", "at_C"]},
            "move_C"   : {"pre" : [],                           "add" : ["at_C"],                           "del" : ["at_A", "at_B"]},
            } 

    pose_map = {
        "A": {"goal": (0.0, 4.5, 1.0),  "bounds": ((-3.25, 3.25), (0.75, 8.25)),    "literal": "at_A"}, # Red object
        "B": {"goal": (0.0, -4.5, 1.0), "bounds": ((-3.25, 3.25), (-8.25, -0.75)),  "literal": "at_B"}, # Big Room
        "C": {"goal": (9.0, 0.0, 1.0),  "bounds": ((4.75, 13.25), (-8.25, 8.25)),   "literal": "at_C"},
    }

    try:
        runTree(init_state, goal_state, action_database, pose_map)
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()