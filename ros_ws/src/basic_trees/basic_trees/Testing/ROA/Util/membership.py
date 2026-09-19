'''
Empirically tests the ROA of a tree based off the amount of states
in the states_pool that return SUCCESS from fully expanded trees
'''
import py_trees
from collections import Counter
from basic_trees.Goals.goal_types import OR, AND, GoalSelector
from basic_trees.Goals.goal_tree import setupWorld
from basic_trees.Conditions.condition import Condition
from basic_trees.Actions.test_action import TestAction

MEM_SUCCESS = 0
MEM_FAILURE = 1
MEM_CYCLE = 2
MEM_CAP = 3
MEM_VIOLATION = 4


def goalSatisfied(term, state):
    # Recursively evaluate state of the tree
    # Works for nested or flat AND/OR terms
    if isinstance(term, str):
        return term in state
    elif isinstance(term, AND):
        return all(goalSatisfied(child, state) for child in term.children)
    else:
        # term is an OR
        return any(goalSatisfied(child, state) for child in term.children)


def assertMemoryless(root):
    # Walk through the tree and set all Composite nodes to memoryless
    for node in root.iterate():
        if isinstance(node, py_trees.composites.Composite) and node.memory:
            raise AssertionError(f"{node.name} has memory=True")


def membership(root, state, blackboard, goal_term, cap):
    # Define world state
    setupWorld(blackboard, set(state)) # Needs to be a copy b/c TestAction mutates world_state 

    # Reset all node outputs
    for node in root.iterate():
        node.stop(py_trees.common.Status.INVALID)

    prev_state = frozenset(blackboard.world_state)
    seen = {prev_state}

    false_success = 0   # Ticks where root said SUCCESS but the goal did not hold
    counter = 0

    while counter < cap:
        # Tick the root
        root.tick_once()    # Ticks the tree directly even if through root

        # Classify root status
        current_state = frozenset(blackboard.world_state)

        status = root.status
        assert status in (py_trees.common.Status.SUCCESS,
                          py_trees.common.Status.FAILURE)

        satisfied = goalSatisfied(goal_term, current_state)

        if status == py_trees.common.Status.SUCCESS and satisfied:
            return MEM_SUCCESS, false_success        # In the ROA

        if status == py_trees.common.Status.SUCCESS:
            # Root claims success on an unsatisfied goal; keep ticking, a real
            # tree would too. Only count it.
            false_success += 1

        if current_state == prev_state:
            # Nothing changed this tick, so nothing will change on the next one
            return (MEM_FAILURE if status == py_trees.common.Status.FAILURE
                    else MEM_VIOLATION), false_success

        if current_state in seen:
            return MEM_CYCLE, false_success          # Livelock, not in the ROA

        prev_state = current_state
        seen.add(current_state)
        counter += 1

    return MEM_CAP, false_success


def treeStats(root):
    # Size metrics; nodes - unique_conditions shows duplicated expansion
    nodes = 0
    condition_sets = []

    for node in root.iterate():
        nodes += 1
        if isinstance(node, Condition):
            condition_sets.append(frozenset(node.preconditions))

    return {
        "nodes": nodes,
        "condition_nodes": len(condition_sets),
        "unique_conditions": len(set(condition_sets)),
        "condition_sets": set(condition_sets),   # for the coverage comparison later
    }

 
def sweep(pool, unified_root, dnf_root, goal_term, blackboard, cap=100):
    assertMemoryless(unified_root)
    assertMemoryless(dnf_root)

    buckets = Counter()
    outcomes = {"unified": Counter(), "dnf": Counter()}
    false_success = {"unified": 0, "dnf": 0}
    disagreements = []

    for state in pool:
        u, u_false = membership(unified_root, state, blackboard, goal_term, cap)
        d, d_false = membership(dnf_root, state, blackboard, goal_term, cap)

        outcomes["unified"][u] += 1
        outcomes["dnf"][d] += 1
        false_success["unified"] += u_false
        false_success["dnf"] += d_false

        u_ok = (u == MEM_SUCCESS)
        d_ok = (d == MEM_SUCCESS)

        if u_ok and d_ok:
            buckets["both"] += 1
        elif u_ok:
            buckets["unified_only"] += 1
            disagreements.append((state, u, d))
        elif d_ok:
            buckets["dnf_only"] += 1
            disagreements.append((state, u, d))
        else:
            buckets["neither"] += 1

    return buckets, outcomes, false_success, disagreements


def diagnoseViolation(root, state, blackboard, goal_term, shared, action_db):
    setupWorld(blackboard, set(state))
    for node in root.iterate():
        node.stop(py_trees.common.Status.INVALID)

    before = frozenset(blackboard.world_state)
    root.tick_once()
    after = frozenset(blackboard.world_state)

    print("=" * 60)
    print(f"root status : {root.status}")
    print(f"goal holds  : {goalSatisfied(goal_term, after)}")
    print(f"shared      : {sorted(shared)}")
    print(f"before      : {sorted(before)}")
    print(f"after       : {sorted(after)}")

    lost = before - after
    gained = after - before
    print(f"deleted     : {sorted(lost)}")
    print(f"added       : {sorted(gained)}")
    print(f"shared lost : {sorted(lost & set(shared))}")

    # Which actions in the tree could have deleted a shared literal
    names = {n.name for n in root.iterate() if isinstance(n, TestAction)}
    for name in sorted(names):
        dels = set(action_db[name]["del"])
        if dels & lost & set(shared):
            print(f"  culprit {name}: pre={sorted(action_db[name]['pre'])} "
                  f"add={sorted(action_db[name]['add'])} del={sorted(dels)}")

    print(py_trees.display.unicode_tree(root, show_status=True))


def subtreeActions(node):
    # Distinct action names appearing in this subtree
    return {n.name for n in node.iterate() if isinstance(n, TestAction)}


def branchActions(root):
    names = set()
    for n in root.iterate():
        if isinstance(n, GoalSelector):
            names |= subtreeActions(n)
    return names


def conflictStats(u_root, shared, action_db):
    # How often can an action in the OR branch break a shared literal
    shared = set(shared)

    # Domain level: independent of any tree
    db_conflict = sum(1 for a in action_db.values() if set(a["del"]) & shared)
    del_sizes = [len(a["del"]) for a in action_db.values()]

    # Tree level: only actions actually admitted into the OR branch    
    names = branchActions(u_root)
    if not names:
        return {"db_actions": len(action_db), "db_conflict": db_conflict,
                "mean_del": sum(del_sizes) / len(del_sizes) if del_sizes else 0,
                "branch_actions": 0, "branch_conflict": 0}

    branch_conflict = sum(1 for n in names if set(action_db[n]["del"]) & shared)

    return {
        "db_actions": len(action_db),
        "db_conflict": db_conflict,
        "mean_del": sum(del_sizes) / len(del_sizes) if del_sizes else 0,
        "branch_actions": len(names),
        "branch_conflict": branch_conflict,
    }


def disjunctSolvable(disjunct, pool, action_db, cap=200):
    # Forward BFS from each pooled state; intermediate states may leave the pool
    target = set(disjunct)
    actions = [(set(a["pre"]), set(a["add"]), set(a["del"])) for a in action_db.values()]

    for start in pool:
        if target <= start:
            return True

        seen = {start}
        frontier = [start]
        expanded = 0

        while frontier and expanded < cap:
            state = frontier.pop(0)
            expanded += 1

            for pre, add, dele in actions:
                if not pre <= state:
                    continue
                nxt = frozenset((state - dele) | add)
                if nxt in seen:
                    continue
                if target <= nxt:
                    return True
                seen.add(nxt)
                frontier.append(nxt)

    return False


def solvableDisjuncts(disjuncts, pool, action_db):
    # How many of the DNF arm's disjuncts are reachable at all
    flags = [disjunctSolvable(d, pool, action_db) for d in disjuncts]
    return sum(flags), len(flags)