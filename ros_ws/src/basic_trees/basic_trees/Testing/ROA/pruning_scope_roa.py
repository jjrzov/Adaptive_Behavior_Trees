'''
Pruning scope vs region of attraction.

prune_driver.py answers "how many nodes does each pruning policy remove", and
reports a solved column taken from one initial state per problem. That is too
coarse to see a completeness difference: sweeping every pooled state instead of
just states_db[0] finds one immediately.

This file asks the other question. For each problem it builds four unified arms
on the SAME action database and goal:

    scoped_off    scopedBFS + scopedPrune,  protect off     (current default)
    global_off    BFS + prune,              protect off     (cross-branch)
    scoped_left   scopedBFS + scopedPrune,  protect left
    global_left   BFS + prune,              protect left

and scores all four against a DNF reference built from the same disjuncts. DNF
is sound and complete by construction, so "states lost vs DNF" is the
completeness cost of each arm.

Both values of SUBSET_PRUNE are swept, since the two pruning regimes fire on
different conditions - exact match against subset match - and it is not obvious
in advance that they behave the same way.

PREREQUISITES - the script checks for these and warns:

  1. algorithms.scopedPrune must unpack the expansion key as
         fc, fc_protect = key_pair
     and not wrap it in frozenset(), which silently disables scoped pruning.
  2. goal_types.buildBaseTree must pass mode through its recursion:
         root.add_child(buildBaseTree(item, mode=mode))
  3. setup_tests.getRandomSubset must iterate sorted(state), not state.
     Set iteration order is randomised per process, so without this the
     generated problems differ between runs and the numbers do not reproduce.
  4. Testing/ROA/Util/membership.py must provide sweepArms.
'''
import csv
import inspect
import sys

import py_trees

import basic_trees.algorithms as alg
from basic_trees.algorithms import expand, prune, expansionKey
from basic_trees.traverse import BFS
from basic_trees.Goals.goal_types import AND, OR, GoalSelector, buildBaseTree
from basic_trees.Goals.goal_tree import fixpointBuilder, getAction
from basic_trees.Testing import setup_tests
from basic_trees.Testing.setup_tests import (generateLiterals, generateSolution,
                                             getDisjunctSetsWithCosts)
from basic_trees.Testing.ROA.Util.membership import (sweepArms, treeStats,
                                                     solvableDisjuncts)

import random


TARGET_RUNS = 500
CAP = 100
SEED = 0
CASE = {"literals": 10, "distance": 10, "iterations": 10}
SUBSET_MODES = (True, False)
OUT = "prune_scope_roa.csv"

ARMS = ["scoped_off", "global_off", "scoped_left", "global_left"]
REFERENCE = "dnf"

FIELDS = ["subset_prune", "problem_id", "pool_size", "arm", "nodes",
          "expansions", "solved", "both", "arm_only", "ref_only", "neither",
          "false_success", "violations"]


def checkPrerequisites():
    # Cheap source checks - each of these silently changes the numbers
    problems = []

    source = inspect.getsource(alg.scopedPrune)
    if "frozenset(key_pair)" in source:
        problems.append("algorithms.scopedPrune still wraps the key in "
                        "frozenset() - scoped pruning is disabled")

    source = inspect.getsource(buildBaseTree)
    if "buildBaseTree(item, mode=mode)" not in source:
        problems.append("goal_types.buildBaseTree does not pass mode through "
                        "its recursion")

    source = inspect.getsource(setup_tests.getRandomSubset)
    if "sorted(state)" not in source:
        problems.append("setup_tests.getRandomSubset iterates a set - problems "
                        "will differ between runs and these numbers will not "
                        "reproduce")

    for line in problems:
        print(f"  WARNING: {line}")

    return not problems


def globalFixpoint(goal_term, action_db, protect_mode, cap=400):
    # The cross-branch arm: one global record of expanded literals and prune()
    # instead of scopedPrune(), which is what PRUNE_MODE = "global" does in
    # runTree. Conditions are shared across GoalSelector branches rather than
    # kept per scope, so expanding one branch can sever another branch's route.
    root = buildBaseTree(goal_term, mode=protect_mode)

    expanded_literals = set()
    expansions = 0
    traverse = BFS()

    while (condition := traverse.getNextCondition(
            root, expanded_literals)) is not None:
        if expansions >= cap:
            raise RuntimeError("global fixpoint did not terminate")

        expanded_literals.add(expansionKey(condition))
        root = expand(root, condition, action_db, getAction)
        prune(root, expanded_literals)

        expansions += 1

    return root, expansions


def buildProblem():
    # Nested goal AND(shared, OR(r1, r2)) from the base paper's generator
    literals = generateLiterals(CASE["literals"])
    states_db, action_db, states_pool = generateSolution(
        literals, CASE["distance"], CASE["iterations"], return_pool=True)

    sample = getDisjunctSetsWithCosts(states_db, action_db)
    if sample is None:
        return None

    d1, d2, _, _ = sample
    shared = set(d1) & set(d2)
    r1, r2 = set(d1) - shared, set(d2) - shared

    if not shared or not r1 or not r2:
        return None         # nothing shared, or one disjunct subsumes the other

    goal_term = AND(*sorted(shared),
                    OR(AND(*sorted(r1)), AND(*sorted(r2))))
    pool = {frozenset(s) for s in states_pool}

    return goal_term, [d1, d2], action_db, pool


def buildArms(goal_term, disjuncts, action_db):
    roots, expansions = {}, {}

    for protect_mode in ("off", "left"):
        roots[f"scoped_{protect_mode}"], expansions[f"scoped_{protect_mode}"] = \
            fixpointBuilder(goal_term, action_db, protect_mode=protect_mode)
        roots[f"global_{protect_mode}"], expansions[f"global_{protect_mode}"] = \
            globalFixpoint(goal_term, action_db, protect_mode)

    reference, count = [], 0
    for disjunct in disjuncts:
        root, expanded = fixpointBuilder(AND(*sorted(disjunct)), action_db,
                                         protect_mode="off")
        reference.append(root)
        count += expanded

    join = GoalSelector(name="DNF", memory=False)
    join.add_children(reference)

    roots[REFERENCE], expansions[REFERENCE] = join, count

    return roots, expansions


def runSubsetMode(subset_prune, writer):
    alg.SUBSET_PRUNE = subset_prune
    alg.DEDUP_C_ATTR = False

    random.seed(SEED)        # reseed so both regimes see identical problems

    kept = tree_diff = roa_diff = 0
    pooled = 0
    lost = {arm: 0 for arm in ARMS}

    for problem_id in range(TARGET_RUNS):
        problem = buildProblem()
        if problem is None:
            continue

        goal_term, disjuncts, action_db, pool = problem

        solvable, total = solvableDisjuncts(disjuncts, pool, action_db)
        if solvable < total:
            continue         # FAILURE everywhere would be correct here

        kept += 1
        pooled += len(pool)

        roots, expansions = buildArms(goal_term, disjuncts, action_db)

        if (treeStats(roots["scoped_off"])["nodes"]
                != treeStats(roots["global_off"])["nodes"]):
            tree_diff += 1

        blackboard = py_trees.blackboard.Client(
            name=f"prune_{subset_prune}_{problem_id}")

        outcomes, false_success, solved, buckets = sweepArms(
            pool, roots, goal_term, blackboard, reference=REFERENCE, cap=CAP)

        if (solved["scoped_off"] != solved["global_off"]
                or solved["scoped_left"] != solved["global_left"]):
            roa_diff += 1

        for arm in ARMS:
            lost[arm] += buckets[arm]["ref_only"]

            writer.writerow({
                "subset_prune": subset_prune,
                "problem_id": problem_id,
                "pool_size": len(pool),
                "arm": arm,
                "nodes": treeStats(roots[arm])["nodes"],
                "expansions": expansions[arm],
                "solved": len(solved[arm]),
                "both": buckets[arm]["both"],
                "arm_only": buckets[arm]["arm_only"],
                "ref_only": buckets[arm]["ref_only"],
                "neither": buckets[arm]["neither"],
                "false_success": false_success[arm],
                "violations": outcomes[arm][4],      # MEM_VIOLATION
            })

    return kept, pooled, tree_diff, roa_diff, lost


def main():
    print("prune scope vs ROA\n")

    if not checkPrerequisites():
        print()

    with open(OUT, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()

        for subset_prune in SUBSET_MODES:
            kept, pooled, tree_diff, roa_diff, lost = runSubsetMode(
                subset_prune, writer)

            print(f"SUBSET_PRUNE={subset_prune}: {kept} problems, "
                  f"{pooled} pooled states")
            print(f"   trees differ (scoped vs global) : {tree_diff}/{kept}")
            print(f"   ROA differs (scoped vs global)  : {roa_diff}/{kept}")
            print("   states lost vs DNF: "
                  + "  ".join(f"{arm}={lost[arm]}" for arm in ARMS))
            print()

    print(f"wrote {OUT}")


if __name__ == '__main__':
    main()