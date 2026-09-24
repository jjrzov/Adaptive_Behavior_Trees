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


# How much sibling protection buildBaseTree has
'''
    "off":          no protection

    "left":         protect against LEFT SIBLINGS ONLY. A sequence child that already
                    returned success this tick is not rechecked, thus an action in a
                    later sibling must not delete its literals
    
    "symmetric":    protect against ALL SIBLINGS. Removes mutual destruction that
                    leaves a sequence oscillating and never returning SUCCESS,
                    violating finite time success
'''

PROTECT_MODE = "off"


def goalLiterals(node):
    # Return every goal literal a base tree subtree is meant to make true
    if isinstance(node, Condition):
        return set(node.preconditions)

    if isinstance(node, py_trees.composites.Composite):
        literals = set()

        for child in node.children:
            literals |= goalLiterals(child)

        return literals
    return set()


def applyProtect(node, literals):
    # Adds literals to every condition's protect set in this subtree
    # A condition under multiple nested GoalSequences accumulates all of them
    if not literals:
        return

    if isinstance(node, Condition):
        node.protect |= set(literals)

    if isinstance(node, py_trees.composites.Composite):
        for child in node.children:
            applyProtect(child, literals)


def seedProtect(root, mode):
    # Setup sibling protection on a GoalSequence
    if mode == "off" or not isinstance(root, GoalSequence):
        return

    children = list(root.children)
    literals = [goalLiterals(child) for child in children]

    for index, child in enumerate(children):
        if mode == "left":
            protect_literals = set().union(*literals[:index])
        else:
            protect_literals = set().union(*[lits for other, lits in enumerate(literals) 
                                             if other != index])

        applyProtect(child, protect_literals)


def buildBaseTree(term, mode=None):
    # Build the initial tree shape based on the goal
    mode = PROTECT_MODE if mode is None else mode

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

            strings = [i for i in res if isinstance(i, str)]
            others = [i for i in res if not isinstance(i, str)]

            if isinstance(term, AND) and strings:
                # Merge the literals of an AND into one condition so expansion
                # regresses them jointly
                name = " & ".join(sorted(strings))
                root.add_child(Condition(name=name, preconditions=set(strings)))
            else:
                for s in strings:
                    root.add_child(Condition(name=s, preconditions={s}))

            for item in others:
                root.add_child(buildBaseTree(item, mode=mode))

            # A child's protect set is defined by its siblings so after building
            seedProtect(root, mode)

            return root # Return root of tree



def main():
    root= buildBaseTree(AND('a','b', OR(AND('c'), AND('d'))))
    py_trees.display.render_dot_tree(root, name=f"test_tree")



if __name__ == '__main__':
    main()
    
