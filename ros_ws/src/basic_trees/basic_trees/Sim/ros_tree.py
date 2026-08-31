import py_trees
import py_trees_ros
import rclpy

from basic_trees.Conditions.condition import Condition
from basic_trees.Actions import Load, Unload, MoveA, MoveB, MoveC
from basic_trees.Actions import MockMoveA, MockMoveB, MockMoveC
from basic_trees.traverse import BFS, DFS
from basic_trees.algorithms import prune, expand


MOCK = True    # Use mock actions or real actions

Action_Database = {
        "load"     : {"pre" : ["empty", "at_A"],            "add" : ["full"],                           "del" : ["empty", "package_at_A"]},
        "unload"   : {"pre" : ["full", "at_B"],             "add" : ["empty", "package_at_B"],          "del" : ["full"]},
        "move_A"   : {"pre" : [],                           "add" : ["at_A"],                           "del" : ["at_B", "at_C"]},
        "move_B"   : {"pre" : [],                           "add" : ["at_B"],                           "del" : ["at_A", "at_C"]},
        "move_C"   : {"pre" : [],                           "add" : ["at_C"],                           "del" : ["at_A", "at_B"]},
        } 


def createRoot(goal_state):
    # Create the root sequence
    root = Condition(f"goal\n{sorted(goal_state)}", goal_state)
    return root


def setupWorld(blackboard, init_state):
    # Dynamic world state
    if blackboard.is_registered(key="world_state", access=py_trees.common.Access.WRITE):
        # Key already exists, need to reset it
        blackboard.unset("world_state")
    else:
        blackboard.register_key(key="world_state", access=py_trees.common.Access.WRITE)
    
    blackboard.world_state = init_state # init_state should be a set


def getAction(action_str, action_database, mock=MOCK):
    # Converts action name as a string to action object
    action_map_real = {
        "load"   : lambda: Load(action_database=action_database),
        "unload" : lambda: Unload(action_database=action_database),
        "move_A" : lambda: MoveA(),
        "move_B" : lambda: MoveB(),
        "move_C" : lambda: MoveC(),
    }
    
    action_map_mock = {
        "load"   : lambda: Load(action_database=action_database),
        "unload" : lambda: Unload(action_database=action_database),
        "move_A" : lambda: MockMoveA(),
        "move_B" : lambda: MockMoveB(),
        "move_C" : lambda: MockMoveC(),
    }
    
    action_map = action_map_mock if mock else action_map_real
    return action_map[action_str]()


def runTree(init_state, goal_state, action_database, traverse=BFS()):
    # Create the tree
    root = createRoot(goal_state)
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
        return
    
    traverse = BFS()            # EDIT traversal function here
    scorer = None     # EDIT cost metric for adding actions in expand here
    
    expanded_literals = set()

    while root.status != py_trees.common.Status.SUCCESS:
        # Handle tree returning RUNNING or FAILURE
        rclpy.spin_once(tree.node, timeout_sec=0)
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
            
            root = expand(root, next_condition, Action_Database, getAction, scorer)
            prune(root, expanded_literals)  # Remove sequence structures that have already been expanded elsewhere
            tree.root = root

    py_trees.display.render_dot_tree(root, name="tree")


def main(args=None):
    rclpy.init(args=args)


    # Set enviroment
    init_state = {"empty", "at_C", "package_at_A"}
    goal_state = ["package_at_B"]

    try:
        rclpy.spin(ros_tree.node)
    except KeyboardInterrupt:
        pass
    finally:
        ros_tree.shutdown()
        rclpy.shutdown()


if __name__ == '__main__':
    main()