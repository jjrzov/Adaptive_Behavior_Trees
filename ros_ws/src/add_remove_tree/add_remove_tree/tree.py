import py_trees
import py_trees_ros
import rclpy

from rclpy.node import Node


class EditBehaviorTree(Node):
    def __init__(self):
        super().__init__("edit_behavior_tree")
        self.root = self.create_root()
        self.tree = py_trees_ros.trees.BehaviourTree(self.root, unicode_tree_debug=True)
        self.tree.setup(timeout=15.0, node=self)

    def Condition(self):
        return py_trees.behaviours.Failure(name='Condition')

    def Action(self):
        return py_trees.behaviours.Running(name='Action')

    def create_root(self):
        '''
        Creates a basic tree to showcase add / remove node functionality

        Returns: the root of the tree
        '''
        root = py_trees.composites.Selector(name='Fallback', memory=False)
        preCon_1 = self.Condition()
        action_1 = self.Action()
        fallback_1 = py_trees.composites.Selector(name='Fallback', memory=False)


        root.add_children([preCon_1, action_1, fallback_1])

        return root

    def execute(self):
        '''
        Ticks the BT
        '''
        self.tree.tick()

    def add(self):
        '''
        Add a node to the BT once already created and ran
        '''
        preCon_2 = self.Condition()
        self.root.children[2].add_child(preCon_2)

def main(args=None):
    rclpy.init()
    behavior = EditBehaviorTree()
    behavior.execute()
    behavior.add()
    behavior.tree.tick_tock(period_ms=100)
    rclpy.spin(behavior.tree.node)
    rclpy.shutdown()

if __name__ == "__main__":
    main()
