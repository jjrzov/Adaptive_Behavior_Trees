"""
Recovery experiment.

Question: pruning removes cross-branch sequence structures. Does that cost the
tree the ability to fall back to the other disjunct when the one it committed
to is invalidated?

Procedure, per problem:
  1. Solve OR(d1, d2). Record which disjunct was reached.
  2. Disturb: clear the literals unique to the reached disjunct, and disable
     every action that could restore them, so the tree cannot simply redo what
     it just did. A disabled action FAILS when ticked - it does not quietly
     succeed while doing nothing.
  3. Keep ticking the SAME tree - no rebuilding, no new expansions. Recovery
     means reaching the other disjunct by ticking alone.

Run with prune on and prune off; the difference is what pruning costs.

REQUIRES a small change to TestAction.update():

    def update(self):
        if self.action_database[self.name].get("disabled"):
            return py_trees.common.Status.FAILURE
        ...

Without it a disabled action returns SUCCESS while adding nothing, the parent
sequence structure succeeds, and the selector never reaches the other branch.
"""

import copy
import py_trees

import basic_trees.algorithms as alg
import basic_trees.Goals.goal_tree as gt

from basic_trees.Testing.setup_tests import (
    generateLiterals, generateSolution, getDisjunctSetsWithCosts)
from basic_trees.Goals.goal_tree import runTree
from basic_trees.Goals.goal_types import OR, AND
from basic_trees.traverse import BFS


HAND_CASE = True        # True: the has_key domain. False: generated problems.
TARGET_RUNS = 1 if HAND_CASE else 200
MAX_RECOVERY_TICKS = 50
VERBOSE = HAND_CASE


def whichDisjunct(state, d1, d2):
    s = set(state)
    in1 = set(d1).issubset(s)
    in2 = set(d2).issubset(s)
    if in1 and in2:
        return "both"
    if in1:
        return "d1"
    if in2:
        return "d2"
    return "neither"


def buildHandCase():
    d1 = {"has_key", "at_A"}
    d2 = {"has_key", "at_C"}
    db = {
        "get_key": {"pre": ["at_start"], "add": ["has_key"], "del": [],
                    "cost": 1.0},
        "go_A":    {"pre": [], "add": ["at_A"], "del": ["at_C", "at_start"],
                    "cost": 5.0},
        "go_C":    {"pre": [], "add": ["at_C"], "del": ["at_A", "at_start"],
                    "cost": 3.0},
    }
    return d1, d2, db, {"at_start"}


def buildGeneratedCase(case):
    all_literals = generateLiterals(case["literals"])
    states_db, action_db = generateSolution(
        all_literals, case["distance"], case["iterations"])

    sample = getDisjunctSetsWithCosts(states_db, action_db)
    if sample is None:
        return None

    d1, d2, _, _ = sample
    return set(d1), set(d2), copy.deepcopy(action_db), states_db[0].copy()


def disturb(action_database, blocked_literals):
    # Disable any action that could restore the blocked literals. A disabled
    # action fails rather than succeeding as a no-op.
    disabled = 0
    for ops in action_database.values():
        if set(ops["add"]) & set(blocked_literals):
            ops["disabled"] = True
            disabled += 1
    return disabled


def tickToRecover(root, blackboard, target):
    # Tick the existing tree only - no expansion.
    for _ in range(MAX_RECOVERY_TICKS):
        root.tick_once()
        if set(target).issubset(blackboard.world_state):
            return True
    return False


def runOne(case, prune_on):
    alg.SUBSET_PRUNE = False
    alg.DEDUP_C_ATTR = False
    gt.PRUNE_ENABLED = prune_on

    built = buildHandCase() if HAND_CASE else buildGeneratedCase(case)
    if built is None:
        return None
    d1, d2, db, init_state = built

    goal = OR(AND(*d1), AND(*d2))
    root, _, final_state = runTree(init_state, goal, db, traverse=BFS())
    if root is False:
        return None                     # unsolvable - not what we're measuring

    reached = whichDisjunct(final_state, d1, d2)
    if reached not in ("d1", "d2"):
        return None                     # ambiguous or nothing reached

    committed = d1 if reached == "d1" else d2
    other = d2 if reached == "d1" else d1

    blocked = set(committed) - set(other)
    if not blocked:
        return None                     # disjuncts identical; nothing to block

    disabled = disturb(db, blocked)
    if disabled == 0:
        return None                     # nothing restores them; test is vacuous

    # The blackboard is process-global; write the post-disturbance state directly
    bb = py_trees.blackboard.Client(name="Disturb")
    bb.register_key(key="world_state", access=py_trees.common.Access.WRITE)
    for lit in blocked:
        bb.world_state.discard(lit)

    if VERBOSE:
        print(f"\nreached {reached}, blocking {blocked}, "
              f"disabled {disabled} action(s)")
        print(f"state after disturbance: {bb.world_state}")

    goal_cond = root.children[0].children[0]   # C branch's goal condition
    print("condition sees:", goal_cond.blackboard.world_state)
    print("same object:", goal_cond.blackboard.world_state is bb.world_state)

    # root.stop(py_trees.common.Status.INVALID)
    for node in root.iterate():
        node.stop(py_trees.common.Status.INVALID)

    for node in root.iterate():
        print(f"  {node.name}: {node.status}")

    recovered = tickToRecover(root, bb, other)

    if VERBOSE:
        print(f"target {other} -> recovered: {recovered}")
        print(py_trees.display.unicode_tree(root, show_status=True))

    return {"recovered": recovered, "reached": reached, "disabled": disabled}


def main():
    case = {"case": 1, "literals": 100, "distance": 10, "iterations": 100}
    print(f"hand_case = {HAND_CASE}")
    if not HAND_CASE:
        print(f"literals = {case['literals']}, distance = {case['distance']}, "
              f"iterations = {case['iterations']}")

    for prune_on in (True, False):
        print(f"\n{'='*60}\nPRUNE {'ON' if prune_on else 'OFF'}\n{'='*60}")

        results = []
        attempts = 0
        while len(results) < TARGET_RUNS and attempts < TARGET_RUNS * 20:
            attempts += 1
            r = runOne(case, prune_on)
            if r is not None:
                results.append(r)

        if not results:
            print(f"no usable problems in {attempts} attempts")
            continue

        rec = sum(1 for r in results if r["recovered"])
        print(f"\nrecovered {rec}/{len(results)} ({100*rec/len(results):.1f}%)  "
              f"[{attempts} attempts]")


if __name__ == "__main__":
    main()