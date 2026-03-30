import py_trees
import py_trees_ros
import rclpy


action_database = {
        "load_1"   : {"pre" : ["empty", "at_A"], "add" : ["has_package_1"], "del" : ["empty"]},
        "unload_1" : {"pre" : ["has_package_1", "at_B"], "add" : ["empty"], "del" : ["has_package_1"]},
        "move_A"   : {"pre" : [], "add" : ["at_A"], "del" : ["at_B", "at_C"]},
        "move_B"   : {"pre" : [], "add" : ["at_B"], "del" : ["at_A", "at_C"]},
        "move_C"   : {"pre" : [], "add" : ["at_C"], "del" : ["at_A", "at_B"]},
        } 

def create_tree():
    # Create the root sequence
    root = py_trees.composites.Sequence(name="Root", memory=True)

    # Add your behaviours here
    # root.add_children([...])

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

    blackboard.register_key(key="current_room", access=py_trees.common.Access.WRITE)
    blackboard.current_room = "A"

    blackboard.register_key(key="package_1_pickup_room", access=py_trees.common.Access.WRITE)
    blackboard.package_1_pickup_room = "A"

    blackboard.register_key(key="package_1_delivery_room", access=py_trees.common.Access.WRITE)
    blackboard.package_1_delivery_room = "B"

    blackboard.register_key(key="has_package_1", access=py_trees.common.Access.WRITE)
    blackboard.has_package_1 = False

    # Set up the tree
    try:
        tree.setup(node_name="my_tree", timeout=15.0)
    except py_trees_ros.exceptions.TimedOutError as e:
        rclpy.shutdown()
        return

    # Tick the tree once then stop
    tree.tick_once()

    try:
        rclpy.spin(tree.node)
    except KeyboardInterrupt:
        pass
    finally:
        tree.shutdown()
        rclpy.shutdown()

if __name__ == '__main__':
    main()