import py_trees

from basic_trees.Conditions.condition import Condition

class AND:
    def __init__(self, *args):
        self.children = list(args)

class OR:
    def __init__(self, *args):
        self.children = list(args)

class GoalCondition(Condition):
    def __init__(self, preconditions={}):
        super().__init__(preconditions=preconditions)


# Alternate named classes to allow for goal branch policies when expand() is called
class GoalSequence(py_trees.composites.Sequence):
    pass

class GoalSelector(py_trees.composites.Selector):
    pass


def buildGoalTree(term):
    # Build the goal tree from the input interface
    children = []
    for child in term.children:
        if isinstance(child, (AND, OR)):
            children.append(buildGoalTree(child))
        else:
            # String as input
            children.append(Condition(name=child, preconditions={child}))

    if isinstance(term, AND):
        root = py_trees.composites.Sequence(name="Seq", memory=False)
    elif isinstance(term, OR):
        root = py_trees.composites.Selector(name="FB", memory=False)

    root.add_children(children)
    return root


def flatten(root):
    # Flatten multiple operations of the same type into a list of literals
    literals = []

    for child in root.children:
        if isinstance(child, str):
            literals.append(child)  # String type means direct literal
        elif isinstance(child, type(root)):
            # Child is same type as parent, recurseviely expand
            literals.extend(flatten(child))
        else:
            # Child and term have opposite types (one AND the other OR)
            literals.append(child)
    
    return literals


def buildBaseTree(term):
    # Build the initial tree shape based on the goal                            TODO: Iterative ANDs are still separate conditions not one big condition
    if isinstance(term, str):
        return Condition(name=term, preconditions={term})
    else:
        # Instance of AND or OR
        res = flatten(term)
        if all(isinstance(item, str) for item in res) and isinstance(term, AND):
            # All the items are literals for an AND operation
            name = " & ".join(sorted(res))
            return Condition(name=name, preconditions=res)  # One condition with all literals
        else:
            if isinstance(term, AND):
                root = GoalSequence(name="Seq", memory=False)
            else:
                root = GoalSelector(name="FB", memory=False)

            for item in res:                                                      # TODO: NO ORDER IN HOW LITERALS ARE PLACED, COULD MATTER FOR SEQUENCE OF AND TERMS like: AND(1st, 2nd)
                if isinstance(item, str):
                    child = Condition(name=item, preconditions={item})
                else:
                    # Flatten will return a list of strings and any opposite operations
                    child = buildBaseTree(item) # Recurse to handle opposite type and branching        
                
                root.add_child(child)
            return root # Return root of tree


    
