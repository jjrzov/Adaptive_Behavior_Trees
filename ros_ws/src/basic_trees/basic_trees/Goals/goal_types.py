import py_trees

from basic_trees.Conditions.condition import Condition

class AND:
    def __init__(self, *args):
        self.children = list(args)

class OR:
    def __init__(self, *args):
        self.children = list(args)


def buildGoalTree(terms):
    # Build the goal tree from the input interface
    children = []
    for child in terms.children:
        if isinstance(child, (AND, OR)):
            children.append(buildGoalTree(child))
        else:
            # String as input
            children.append(Condition(name=child, preconditions={child}))

    if isinstance(terms, AND):
        root = py_trees.composites.Sequence(name="Seq", memory=False)
    elif isinstance(terms, OR):
        root = py_trees.composites.Selector(name="FB", memory=False)

    root.add_children([children])
    return root