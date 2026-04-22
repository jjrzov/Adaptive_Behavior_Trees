import py_trees

from basic_trees.Conditions.condition import Condition


expansion_counter = 0

def expand(root, c, action_database, get_action_fn, scorer=None):
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

    for action, c_attr in sorted_actions:
        action_sequence = py_trees.composites.Sequence(name=f"a_seq_{expansion_counter}", memory=False)
        cond_i = Condition(f"{sorted(c_attr)}", c_attr)
        action_i = get_action_fn(action)
        action_sequence.add_children([cond_i, action_i])

        subtree_tau.add_children([action_sequence])
        expansion_counter += 1

    # Check if condition was root
    if is_root:
        return subtree_tau
    else:
        c_old_parent.prepend_child(subtree_tau)
        return root    
    
def prune(root, expanded_literals):
    # Go through the tree and remove and conditions that have already been expanded elsewhere
    prune_nodes = []    # Store nodes to be removed
    q = []  # Initialize queue
    q.append(root)  # Add start node to queue

    while len(q) != 0:
        # Keep searching while queue is not empty
        node = q.pop(0)
        if isinstance(node, py_trees.composites.Sequence):
            # if node is a sequence check that first child is a condition
            first_child = node.children[0]
            if isinstance(first_child, Condition):
                # if its a condition check that if it has already been expanded
                if frozenset(first_child.preconditions) in expanded_literals:
                    # Already expanded condition node
                    prune_nodes.append(node)  # Remove sequence from tree
        
        if isinstance(node, py_trees.composites.Composite):
            q.extend(node.children)

    # Remove nodes in prune nodes
    for node in prune_nodes:
        node.parent.remove_child(node)
    
    return