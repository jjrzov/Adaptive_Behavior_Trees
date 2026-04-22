import py_trees
import py_trees_ros
import rclpy

from basic_trees.Conditions.condition import Condition
from basic_trees.Actions import PaperMove_b_ab, PaperMove_s_as, PaperMove_s_ab
from basic_trees.traverse import BFS, DFS
from basic_trees.action_scorer import ConditionCompletionScorer, TimeScorer
from basic_trees.algorithms import prune, expand

MOCK = True    # Use mock actions or real actions

expansion_counter = 0

Action_Database = {
        "move(b, ab)" : {"pre" : ["Free(ab)", "WayClear"],    "add" : ["At(b, ab)"],               "del" : ["Free(ab)", "At(b, pb)"]},
        "move(s, ab)" : {"pre" : ["Free(ab)"],                "add" : ["At(s, ab)", "WayClear"],   "del" : ["Free(ab)", "At(s, ps)"]},
        "move(s, as)" : {"pre" : ["Free(as)"],                "add" : ["At(s, as)", "WayClear"],   "del" : ["Free(as)", "At(s, ps)"]},
        }

def create_tree():
    # Create the root sequence
    goal_condition = ["At(b, ab)"]
    root = Condition(f"goal\n{sorted(goal_condition)}", goal_condition)

    return root

def setup_world(blackboard):
    # Dynamic world state
    blackboard.register_key(key="world_state", access=py_trees.common.Access.WRITE)
    blackboard.world_state = {"At(b, pb)", "At(s, ps)", "Free(ab)", "Free(as)"}

def getAction(action_str):
    # Converts action name as a string to action object
    action_map = {
        "move(b, ab)"   : PaperMove_b_ab,
        "move(s, ab)"   : PaperMove_s_ab,
        "move(s, as)"   : PaperMove_s_as,
    }
    
    return action_map[action_str]()

def main():
    rclpy.init()

    # Create the tree
    root = create_tree()
    tree = py_trees_ros.trees.BehaviourTree(
        root=root,
        unicode_tree_debug=True
    )

    # Initialise the blackboard BEFORE setting up the tree
    blackboard = py_trees.blackboard.Client(name="Init")

    setup_world(blackboard) # Define world literals

    # Set up the tree
    try:
        tree.setup(node_name="my_tree", timeout=15.0)
    except py_trees_ros.exceptions.TimedOutError as e:
        rclpy.shutdown()
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

    try:
        rclpy.spin(tree.node)
    except KeyboardInterrupt:
        pass
    finally:
        tree.shutdown()
        rclpy.shutdown()

if __name__ == '__main__':
    main()