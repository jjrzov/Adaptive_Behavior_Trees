import py_trees
import py_trees_ros
import rclpy

from basic_trees.Conditions.condition import Condition
from basic_trees.Actions import Load, Unload, MoveA, MoveB, MoveC
from basic_trees.Actions import MockMoveA, MockMoveB, MockMoveC
from basic_trees.traverse import BFS, DFS
from basic_trees.action_scorer import ConditionCompletionScorer, TimeScorer

MOCK = True    # Use mock actions or real actions

expansion_counter = 0

Action_Database = {
        "load_1"   : {"pre" : ["empty", "at_A"], "add" : ["has_package_1"], "del" : ["empty"]},
        "unload_1" : {"pre" : ["has_package_1", "at_B"], "add" : ["empty"], "del" : ["has_package_1"]},
        "move_A"   : {"pre" : [], "add" : ["at_A"], "del" : ["at_B", "at_C"]},
        "move_B"   : {"pre" : [], "add" : ["at_B"], "del" : ["at_A", "at_C"]},
        "move_C"   : {"pre" : [], "add" : ["at_C"], "del" : ["at_A", "at_B"]},
        } 

def create_tree():
    # Create the root sequence
    root = Condition("goal", ["has_package_1"])

    return root

def setup_world(blackboard):
    # Static parameters for setting up tasks
    blackboard.register_key(key="package_1_pickup_room", access=py_trees.common.Access.WRITE)
    blackboard.package_1_pickup_room = "at_A"

    blackboard.register_key(key="package_1_delivery_room", access=py_trees.common.Access.WRITE)
    blackboard.package_1_delivery_room = "at_B"

    # Dynamic world state
    blackboard.register_key(key="world_state", access=py_trees.common.Access.WRITE)
    blackboard.world_state = {"empty", "at_C"}

def getAction(action_str, mock=MOCK):
    # Converts action name as a string to action object
    action_map_real = {
        "load_1"   : Load,
        "unload_1" : Unload,
        "move_A"   : MoveA,
        "move_B"   : MoveB,
        "move_C"   : MoveC,
    }
    
    action_map_mock = {
        "load_1"   : Load,
        "unload_1" : Unload,
        "move_A"   : MockMoveA,
        "move_B"   : MockMoveB,
        "move_C"   : MockMoveC,
    }
    
    action_map = action_map_mock if mock else action_map_real
    return action_map[action_str]()
    
def expand(root, c, scorer=None):
    global expansion_counter

    # Check to see if goal condition is root
    is_root = c.parent is None
    c_old_parent = c.parent # Need to store old parent because condition can't have 2 parents at once

    c_set = set(c.preconditions)
    subtree_tau = py_trees.composites.Selector(name="fallback", memory=False)

    if not is_root:
        c_old_parent.remove_child(c)    # Remove condition from old parent before assigning new parent
    
    subtree_tau.add_children([c])   # Assign new parent for condition

    valid_actions = []
    for action in Action_Database:
        # Get action literals
        a_pre = set(Action_Database[action]["pre"])
        a_add = set(Action_Database[action]["add"])
        a_del = set(Action_Database[action]["del"])
        
        check1 = c_set.intersection(a_pre.union(a_add - a_del))
        check2 = (c_set - a_del) == c_set
    
        if check1 and check2:
            c_attr = a_pre.union(c_set - a_add)
            
            valid_actions.append((action, c_attr))    # Only want to sort actions that help solve the condition

    if scorer == None:
        sorted_actions = valid_actions
    else:
        sorted_actions = scorer.sort(c_set, valid_actions) # Sort actions by passed in cost metric

    for action, c_attr in sorted_actions:
        action_sequence = py_trees.composites.Sequence(name=f"a_seq_{expansion_counter}", memory=False)
        cond_i = Condition(f"c_attr_{expansion_counter}", c_attr)
        action_i = getAction(action)
        action_sequence.add_children([cond_i, action_i])

        subtree_tau.add_children([action_sequence])
        expansion_counter += 1

    # Check if condition was root
    if is_root:
        return subtree_tau
    else:
        c_old_parent.prepend_child(subtree_tau)
        return root    

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

    while root.status != py_trees.common.Status.SUCCESS:
        # Handle tree returning RUNNING or FAILURE
        rclpy.spin_once(tree.node, timeout_sec=0)
        tree.tick()


        print(f"--- tick ---")
        print(f"status: {root.status}")
        print(f"world_state: {blackboard.world_state}")


        if root.status == py_trees.common.Status.FAILURE:
            # Expand when tree returns failure
            next_condition = traverse.getNextCondition(root)

            print(f"next_condition: {next_condition.name}")

            if next_condition == None:

                print("No more conditions to expand - unsolvable")

                return False
            next_condition.expanded = True
            
            root = expand(root, next_condition, scorer)

            # TODO: Prune
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