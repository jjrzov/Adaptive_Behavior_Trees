import py_trees
import math

from basic_trees.Conditions.condition import Condition


class Traversal:
    def getNextCondition(self, root, expanded_literals):
        pass

class BFS(Traversal):
    def getNextCondition(self, root, expanded_literals):
        q = []  # Initialize queue
        q.append(root)  # Add start node to queue

        while len(q) != 0:
            # Keep searching while queue is not empty
            node = q.pop(0)
            if isinstance(node, Condition):
                if frozenset(node.preconditions) not in expanded_literals:
                    return node # Unexpanded condition node
            
            if isinstance(node, py_trees.composites.Composite):
                q.extend(node.children)
        
        return None # All condition nodes have been expanded

class DFS(Traversal):
    def getNextCondition(self, root, expanded_literals):
        if isinstance(root, Condition):
            if frozenset(root.preconditions) not in expanded_literals:
                return root # Unexpanded condition node
            
        if isinstance(root, py_trees.composites.Composite):
            for child in root.children:
                result = self.getNextCondition(child, expanded_literals)

                if result != None:
                    return result
        
        return None # All condition nodes have been expanded
    
class CheapestFirst(Traversal):
    def getNextCondition(self, root, expanded_literals):
        best_leaf, best_cost = self.cost(root, expanded_literals)
        
        if best_leaf == None or best_cost == math.inf:
            # All condition nodes have been expanded
            return None
        
        return best_leaf    # Condition to be expanded
    
    def findCheapestChild(self, children_scores):
        # return the child with the cheapest cost from list of tuples (child, cost)
        cheapest_child, cheapest_score = None, math.inf
        
        for child, score in children_scores:
            if child is not None and score < cheapest_score:
                cheapest_child, cheapest_score = child, score

        return cheapest_child

    def cost(self, node, expanded_literals):
        # Dont care whether Goal or normal Sequence/Selector
        if isinstance(node, Condition):
            unsolved_literals = len(node.preconditions - node.blackboard.world_state)
            
            if unsolved_literals == 0:
                return None, 0  # Do not want to expand on already satisfied condition
            
            elif frozenset(node.preconditions) in expanded_literals:
                if len(node.parent.children) == 1:
                    # Already expanded and a dead node meaning no valid actions
                    return None, math.inf
                
                # Already expanded node should contribute its cost but not be valid to be expanded
                return None, unsolved_literals

            else:
                return node, unsolved_literals
      
        elif isinstance(node, (py_trees.composites.Sequence, py_trees.composites.Selector)):
            # Get a list of all the children results
            children_res = [self.cost(child, expanded_literals) for child in node.children]

            if isinstance(node, py_trees.composites.Sequence):
                # Cost for sequence to return true is the cost for each child to return true
                if any(math.isinf(res[1]) for res in children_res):
                    return None, math.inf   # One of the children has a cost of inf
                
                total_cost = sum(child[1] for child in children_res)
                return self.findCheapestChild(children_res), total_cost
            
            elif isinstance(node, py_trees.composites.Selector):
                # Cost for selector is equal to the cheapest cost of any of its children
                total_cost = min(child[1] for child in children_res)
                if total_cost == 0:
                    return None, 0  # Do not want to expand already satisfied conditions
                return self.findCheapestChild(children_res), total_cost
        
        else:
            # Ignore action nodes
            return None, 0