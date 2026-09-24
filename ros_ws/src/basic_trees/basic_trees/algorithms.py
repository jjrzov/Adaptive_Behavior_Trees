import py_trees

from basic_trees.Conditions.condition import Condition
from basic_trees.Goals.goal_types import GoalSelector


expansion_counter = 0

DEDUP_C_ATTR = False     # If TRUE, don't add an action if its c_attr has already been added
SUBSET_PRUNE = True     # If TRUE, prune based off condition being a subset or an exact match of an already expanded condition

PRUNE_STATS = {"no_progress": 0, "cross_branch": 0}
PROTECT_STATS = {"filtered": 0}


def expansionKey(node):
    # Literals alone are not enough with protect implemented, 2 conditions with the
    # same literals but different protect sets admit different actions

    # If PROTECT_MODE off, then every protect set is empty, thus goes back to old behavior
    return (frozenset(node.preconditions), frozenset(getattr(node, "protect", ())))


def expand(root, c, action_database, get_action_fn, scorer=None):
    global expansion_counter

    # Check to see if goal condition is root
    is_root = c.parent is None
    c_old_parent = c.parent # Need to store old parent because condition can't have 2 parents at once

    c_set = set(c.preconditions)
    c_protect = set(getattr(c, "protect", ()))
    subtree_tau = py_trees.composites.Selector(name="fallback", memory=False)

    if not is_root:
        c_old_parent.remove_child(c)    # Remove condition from old parent before assigning new parent
    
    subtree_tau.add_children([c])   # Assign new parent for condition

    valid_actions = []

    superset_count = 0

    for action in action_database:
        # Get action literals
        a_pre = set(action_database[action]["pre"])
        a_add = set(action_database[action]["add"])
        a_del = set(action_database[action]["del"])
        
        check1 = c_set.intersection(a_pre.union(a_add - a_del))
        check2 = (c_set - a_del) == c_set

        # Do not admit actions that delete a sibling's goal literals
        # An empty protect makes this always true
        check3 = not(c_protect & a_del)

        if check1 and check2 and not check3:
            PROTECT_STATS["filtered"] += 1  # For analysis
    
        if check1 and check2 and check3:
            c_attr = a_pre.union(c_set - a_add)

            if c_set <= c_attr:
                superset_count += 1
            
            valid_actions.append((action, c_attr))    # Only want to sort actions that help solve the condition

    if scorer == None:
        sorted_actions = valid_actions
    else:
        sorted_actions = scorer.sort(c_set, valid_actions) # Sort actions by passed in cost metric

    # print(f"Expanding: {c.name}")
    # print(f"Valid actions: {[a for a, _ in valid_actions]}")
    # print(f"Sorted actions: {[a for a, _ in sorted_actions]}")

    # unique_c_attrs = set(frozenset(c_attr) for _, c_attr in sorted_actions)
    # duplicate_count = len(sorted_actions) - len(unique_c_attrs)

    seen_c_attrs = set()

    for action, c_attr in sorted_actions:
        if DEDUP_C_ATTR:
            key = frozenset(c_attr)
            if key in seen_c_attrs:
                continue        # An identical region of attraction already present
            seen_c_attrs.add(key)

        action_sequence = py_trees.composites.Sequence(name=f"a_seq_{expansion_counter}", memory=False)
        cond_i = Condition(f"{sorted(c_attr)}", c_attr, protect=c_protect)  # Protect never changes during expansion
        action_i = get_action_fn(action, action_database)
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
    # Do not want to prune conditions apart of the initial Goal Tree
    prune_nodes = []    # Store nodes to be removed

    q = [root]  # Initialize queue with start node

    while q:
        # Keep searching while queue is not empty
        node = q.pop(0)
        if type(node) is py_trees.composites.Sequence:  # Need exact type comparison because GoalSequence is a subclass of Sequence
            # if node is a sequence check that first child is a condition
            first_child = node.children[0]
            if type(first_child) is Condition:
                fc, fc_protect = expansionKey(first_child)

                if SUBSET_PRUNE:
                    # Prune if an already expanded condition is an exact match or subset
                    pruned = any(e <= fc and e_protect == fc_protect for e, e_protect in expanded_literals)
                else:
                    # Only prune if exact match has already been expanded
                    pruned = (fc, fc_protect) in expanded_literals

                if pruned:
                    prune_nodes.append(node)

        if isinstance(node, py_trees.composites.Composite):
            q.extend(node.children)

    for node in prune_nodes:
        node.parent.remove_child(node)

    return len(prune_nodes)


def goalScope(node):
    # Walk up the tree until a goal selector is found to declare the nodes scope
    # If no selector return None
    while node.parent is not None:
        # print(f"  at {node.name}, parent {node.parent.name} type {type(node.parent)}")

        if type(node.parent) is GoalSelector:
            return node
        
        node = node.parent
    return None


def scopedPrune(root, expanded_scoped):
    # Same funcitonality as prune(), but will go through the tree and only remove nodes
    # if the expanded sequence structure is of the same scope (same branch of a selector/OR)
    prune_nodes = []    # Store nodes to be removed

    q = [root]  # Initialize queue with start node

    while q:
        # Keep searching while queue is not empty
        node = q.pop(0)
        if type(node) is py_trees.composites.Sequence:  # Need exact type comparison because GoalSequence is a subclass of Sequence
            # if node is a sequence check that first child is a condition
            first_child = node.children[0]
            if type(first_child) is Condition:
                key_pair = expansionKey(first_child)
                fc, fc_protect = key_pair
                node_scope = goalScope(node)

                if SUBSET_PRUNE:
                    # Prune if an already expanded condition is an exact match or subset
                    pruned = any(e <= fc and e_protect == fc_protect and node_scope in scopes
                                 for (e, e_protect), scopes in expanded_scoped.items())
                else:
                    # Only prune if exact match has already been expanded
                    pruned = node_scope in expanded_scoped.get(key_pair, set())

                if pruned:
                    # print(f"prune {node.name} cond={sorted(fc)} "
                    #       f"scope={id(node_scope)}, {node_scope} "
                    #       f"expanded_in={[id(s) for s in expanded_scoped.get(fc, set())]}")

                    prune_nodes.append(node)

        if isinstance(node, py_trees.composites.Composite):
            q.extend(node.children)

    for node in prune_nodes:
        node.parent.remove_child(node)

    return len(prune_nodes)