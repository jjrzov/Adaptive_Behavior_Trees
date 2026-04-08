import py_trees

from basic_trees.Conditions.condition import Condition


class Traversal:
    def getNextCondition(self, root):
        pass

class BFS(Traversal):
    def getNextCondition(self, root):
        q = []  # Initialize queue
        q.append(root)  # Add start node to queue

        while len(q) != 0:
            # Keep searching while queue is not empty
            node = q.pop(0)
            if isinstance(node, Condition):
                if node.expanded == False:
                    return node # Unexpanded condition node
            
            if isinstance(node, py_trees.composites.Composite):
                q.extend(node.children)
        
        return None # All condition nodes have been expanded

class DFS(Traversal):
    def getNextCondition(self, root):
        if isinstance(root, Condition):
            if root.expanded == False:
                return root # Unexpanded condition node
            
        if isinstance(root, py_trees.composites.Composite):
            for child in root.children:
                result = self.getNextCondition(child)

                if result != None:
                    return result
        
        return None # All condition nodes have been expanded