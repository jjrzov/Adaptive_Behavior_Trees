import py_trees
import py_trees_ros
import rclpy

from basic_trees.Conditions.condition import Condition
from basic_trees.Actions.load import Load
from basic_trees.Actions.unload import Unload
from basic_trees.Actions.moveA import MoveA
from basic_trees.Actions.moveB import MoveB
from basic_trees.Actions.moveC import MoveC
from basic_trees.traverse import Traversal, BFS
from basic_trees.action_scorer import ActionScorer, ConditionCompletionScorer, TimeScorer



action_database = {
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
    blackboard.world_state = {"empty", "at_A"}

def getAction(action_str):
    # Converts action name as a string to action object
    if action_str == "load_1":
        return Load()
    elif action_str == "unload_1":
        return Unload()
    elif action_str == "move_A":
        return MoveA()
    elif action_str == "move_B":
        return MoveB()
    elif action_str == "move_C":
        return MoveC()
    
def expand(root, c, scorer=None):
    # Check to see if goal condition is root
    is_root = c.parent is None

    c_set = set(c.preconditions)

    subtree_tau = py_trees.composites.Selector(name="fallback", memory=False)
    subtree_tau.add_children([c])

    i = 0
    valid_actions = []
    for action in action_database:
        # Get action literals
        a_pre = set(action_database[action]["pre"])
        a_add = set(action_database[action]["add"])
        a_del = set(action_database[action]["del"])
        
        check1 = c_set.intersection(a_pre.union(a_add - a_del))
        check2 = (c_set - a_del) == c_set
    
        if check1 and check2:
            c_attr = a_pre.union(c_set - a_add)
            
            valid_actions.append((action, c_attr))    # Only want to sort actions that help solve the condition

    if scorer == None:
        sorted_actions = valid_actions
    else:
        sorted_actions = scorer.sort(c_set, valid_actions) # Sort actions by passed in cost metric

    for i, (action, c_attr) in enumerate(sorted_actions):
        action_sequence = py_trees.composites.Sequence(name=f"a_seq_{i}", memory=False)
        cond_i = Condition(f"c_attr_{i}", c_attr)
        action_i = getAction(action)
        action_sequence.add_children([cond_i, action_i])

        subtree_tau.add_children([action_sequence])

    # Check if condition was root
    if is_root:
        return subtree_tau
    else:
        c.parent.replace_child(c, subtree_tau)
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
    scorer = ConditionCompletionScorer()     # EDIT cost metric for adding actions in expand here

    while root.status != py_trees.common.Status.SUCCESS:
        # Handle tree returning RUNNING or FAILURE
        rclpy.spin_once(tree.node)
        tree.tick_once()

        if root.status == py_trees.common.Status.FAILURE:
            # Expand when tree returns failure
            next_condition = traverse.getNextCondition(root)
            if next_condition == None:
                return False
            next_condition.expanded = True
            
            root = expand(root, next_condition, scorer)

            # TODO: Prune
            tree.root = root

    try:
        rclpy.spin(tree.node)
    except KeyboardInterrupt:
        pass
    finally:
        tree.shutdown()
        rclpy.shutdown()

if __name__ == '__main__':
    main()