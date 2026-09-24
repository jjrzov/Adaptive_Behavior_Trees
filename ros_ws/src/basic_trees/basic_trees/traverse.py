import py_trees
import math

from basic_trees.Conditions.condition import Condition
from basic_trees.algorithms import goalScope, expansionKey


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
                if expansionKey(node) not in expanded_literals:
                    return node # Unexpanded condition node
            
            if isinstance(node, py_trees.composites.Composite):
                q.extend(node.children)
        
        return None # All condition nodes have been expanded


class scopedBFS(Traversal):
    def getNextCondition(self, root, expanded_scoped):
        q = []  # Initialize queue
        q.append(root)  # Add start node to queue

        while len(q) != 0:
            # Keep searching while queue is not empty
            node = q.pop(0)
            if isinstance(node, Condition):
                fc = expansionKey(node)
                node_scope = goalScope(node)    # Get scope of the condition

                if node_scope not in expanded_scoped.get(fc, ()):
                    return node

                # if frozenset(node.preconditions) not in expanded_scoped:
                    # return node # Unexpanded condition node
            
            if isinstance(node, py_trees.composites.Composite):
                q.extend(node.children)
        
        return None # All condition nodes have been expanded


class DFS(Traversal):
    def getNextCondition(self, root, expanded_literals):
        if isinstance(root, Condition):
            if expansionKey(root) not in expanded_literals:
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

        # print(f"Selected condition: {best_leaf.name}\t Its Cost: {best_cost}\n")

        return best_leaf    # Condition to be expanded


    def cost(self, node, expanded_literals):
        # Dont care whether Goal or normal Sequence/Selector
        if isinstance(node, Condition):
            if expansionKey(node) in expanded_literals:
                return None, 0
            elif len(node.preconditions - node.blackboard.world_state) == 0:
                return None, 0   # Don't expand conditions that are already true
            return node, 0
      
        elif isinstance(node, (py_trees.composites.Sequence, py_trees.composites.Selector)):
            # Get a list of all the children results
            children_res = [self.cost(child, expanded_literals) for child in node.children]

            if isinstance(node, py_trees.composites.Sequence):
                # Cost for sequence to return true is the cost for each child to return true                
                total_cost = sum(child[1] for child in children_res)

                for child_candidate, _ in children_res:
                    if child_candidate is not None:
                        return child_candidate, total_cost    # Return any valid candidate

                return None, total_cost
            
            elif isinstance(node, py_trees.composites.Selector):
                # Cost for selector is equal to the cheapest cost of any of its children
                
                # print(f"SELECTOR\n")
                # for child, score in children_res:
                #     print(f"\tChild: {child}\t\tScore: {score}\n")
                
                
                best_candidate, best_cost = None, math.inf
                for candidate, child_cost in children_res:
                    if candidate is None:
                        continue
                    if child_cost < best_cost:
                        best_candidate, best_cost = candidate, child_cost

                if best_candidate is None:
                    # Nothing expandable below - report the true cost of satisfying this selector
                    return None, min(child_cost for _, child_cost in children_res)

                return best_candidate, best_cost
        
        else:
            # Ignore action nodes
            return None, node.getCost()