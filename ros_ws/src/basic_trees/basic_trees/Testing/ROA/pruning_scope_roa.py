'''
Expansion scope vs region of attraction.

The unified construction scopes its expansion record and its pruning to the
GoalSelector branch a condition sits in. The algorithm of Cai et al. (2021)
keeps one global record and prunes across the whole tree, which is the same
thing for a single-condition goal but not for a goal with branches. This file
measures what that choice costs and buys, on the same problems as the
soundness sweep:

    scoped_off    scopedBFS + scopedPrune, protect off
    global_off    BFS + prune (one shared record), protect off
    scoped_left   scopedBFS + scopedPrune, protect left   (the construction)
    global_left   BFS + prune (one shared record), protect left
    blind_left    global_left with a record key that ignores the protect set
    dnf_shared    DNF with one record shared across its sub-goal trees
    dnf           DNF with the record reset per sub-goal  (the reference)

blind_left tests why protection makes the global rule safe. A condition's
record key is its literals together with its protect set, so under left
protection conditions in different GoalSequence siblings never share a key.
Dropping the protect set from the key, while protection still filters actions,
shows whether the key or the filtering is what keeps the global rule complete.

dnf_shared answers whether the saving a shared record gives is specific to
the unified construction. It is built as the flat goal OR(d1, ..., dk), which
for a flat goal is the DNF tree itself, expanded with the global loop.

Problems are drawn through soundness_roa.syntheticProblem with the same seed
and the same skip rules, so for nested and deep goals they are the problems of
the soundness sweep, and scoped_off and scoped_left reproduce its unified and
protect_l arms exactly. --mode flat replaces each nested goal by the
disjunction of its two disjuncts, where protection has nothing to act on.

Usage:
    python pruning_scope_roa.py --mode nested --checks minimal --target 1000
'''
import argparse
import csv
import math
import random
import statistics

import py_trees

import basic_trees.algorithms as alg
from basic_trees.algorithms import expand, expansionKey
from basic_trees.Conditions.condition import Condition
from basic_trees.Goals.goal_types import AND, OR, buildBaseTree
from basic_trees.Goals.goal_tree import fixpointBuilder, getAction
import basic_trees.Testing.ROA.soundness_roa as sr
from basic_trees.Testing.ROA.Util.membership import (
    sweepArms, treeStats, solvableDisjuncts, solvableStates,
    MEM_FAILURE, MEM_CYCLE, MEM_CAP, MEM_VIOLATION)


MODE = "nested"             # "nested" | "deep" | "flat"
CHECK_PRESET = "minimal"    # A preset of soundness_roa.CHECK_PRESETS
TARGET_PROBLEMS = 1000
MAX_ATTEMPTS = 50           # Per kept problem
CAP = 100
SEED = 0
GLOBAL_EXPANSION_CAP = 2000 # Guard on the global loop, which has no scoped record

ARMS = ["scoped_off", "global_off", "scoped_left", "global_left", "blind_left", "dnf_shared"]
REFERENCE = "dnf"

FIELDS = ["problem_id", "arm", "pool_size", "solvable",
          "nodes", "ref_nodes", "node_ratio", "expansions",
          "solved", "both", "arm_only", "ref_only", "neither",
          "failure", "cycle", "cap", "violations", "false_success"]


def keyIgnoringProtect(node):
    # Record key with the protect set dropped, for the blind_left arm
    return (frozenset(node.preconditions), frozenset())


def nextUnexpanded(root, expanded, key):
    # Breadth-first search for a condition whose key is not yet recorded.
    # Matches traverse.BFS, with the key as a parameter.
    queue = [root]

    while queue:
        node = queue.pop(0)

        if isinstance(node, Condition) and key(node) not in expanded:
            return node

        if isinstance(node, py_trees.composites.Composite):
            queue.extend(node.children)

    return None


def pruneGlobal(root, expanded, key):
    # Remove sequence structures whose condition is already covered by a
    # recorded condition anywhere in the tree. Matches algorithms.prune, with
    # the key as a parameter.
    prune_nodes = []
    queue = [root]

    while queue:
        node = queue.pop(0)

        # Exact type, since GoalSequence subclasses Sequence and is never pruned
        if type(node) is py_trees.composites.Sequence:
            first_child = node.children[0]

            if type(first_child) is Condition:
                literals, protect = key(first_child)

                if alg.SUBSET_PRUNE:
                    pruned = any(e <= literals and e_protect == protect
                                 for e, e_protect in expanded)
                else:
                    pruned = (literals, protect) in expanded

                if pruned:
                    prune_nodes.append(node)

        if isinstance(node, py_trees.composites.Composite):
            queue.extend(node.children)

    for node in prune_nodes:
        node.parent.remove_child(node)


def globalFixpoint(goal_term, action_db, protect_mode, key=expansionKey):
    # The inherited rule: one global record of expanded conditions and pruning
    # across the whole tree. A condition expanded in one GoalSelector branch is
    # treated as expanded in every branch, and its copies elsewhere stay leaves.
    root = buildBaseTree(goal_term, mode=protect_mode)

    expanded = set()
    expansions = 0

    while (condition := nextUnexpanded(root, expanded, key)) is not None:
        if expansions >= GLOBAL_EXPANSION_CAP:
            raise RuntimeError("global fixpoint did not terminate")

        expanded.add(key(condition))
        root = expand(root, condition, action_db, getAction)
        pruneGlobal(root, expanded, key)

        expansions += 1

    return root, expansions


def buildArms(goal_term, disjuncts, action_db):
    roots, expansions = {}, {}

    for protect_mode in ("off", "left"):
        roots[f"scoped_{protect_mode}"], expansions[f"scoped_{protect_mode}"] = \
            fixpointBuilder(goal_term, action_db, protect_mode=protect_mode)
        roots[f"global_{protect_mode}"], expansions[f"global_{protect_mode}"] = \
            globalFixpoint(goal_term, action_db, protect_mode)

    roots["blind_left"], expansions["blind_left"] =         globalFixpoint(goal_term, action_db, "left", key=keyIgnoringProtect)

    flat = OR(*[AND(*sorted(d)) for d in disjuncts])
    roots["dnf_shared"], expansions["dnf_shared"] = globalFixpoint(flat, action_db, "off")

    roots[REFERENCE], expansions[REFERENCE] = sr.buildReference(disjuncts, action_db)

    return roots, expansions


def runProblem(p_index, blackboard, checks):
    problem = sr.syntheticProblem(checks)

    if problem is None:
        return None, "no_admissible_goal"

    goal_term, shared, r1, r2, disjuncts, action_db, pool = problem

    n_solvable, n_disjuncts = solvableDisjuncts(disjuncts, pool, action_db)
    if n_solvable < n_disjuncts:
        return None, "unsatisfiable"

    if MODE == "flat":
        # Same disjuncts, with nothing factored out, so no GoalSequence exists
        goal_term = OR(*[AND(*sorted(d)) for d in disjuncts])

    roots, expansions = buildArms(goal_term, disjuncts, action_db)

    outcomes, false_success, solved, buckets = sweepArms(
        pool, roots, goal_term, blackboard, reference=REFERENCE, cap=CAP)

    solvable = solvableStates(pool, goal_term, action_db)
    for name, members in solved.items():
        if members - solvable:
            raise AssertionError(f"{name} is a member on {len(members - solvable)} "
                                 f"states from which the goal is unreachable")

    ref_nodes = treeStats(roots[REFERENCE])["nodes"]
    rows = []

    for name in ARMS:
        nodes = treeStats(roots[name])["nodes"]
        bucket = buckets[name]

        rows.append({
            "problem_id": p_index,
            "arm": name,
            "pool_size": len(pool),
            "solvable": len(solvable),
            "nodes": nodes,
            "ref_nodes": ref_nodes,
            "node_ratio": round(ref_nodes / nodes, 4),
            "expansions": expansions[name],
            "solved": len(solved[name]),
            "both": bucket["both"],
            "arm_only": bucket["arm_only"],
            "ref_only": bucket["ref_only"],
            "neither": bucket["neither"],
            "failure": outcomes[name][MEM_FAILURE],
            "cycle": outcomes[name][MEM_CYCLE],
            "cap": outcomes[name][MEM_CAP],
            "violations": outcomes[name][MEM_VIOLATION],
            "false_success": false_success[name],
        })

    return rows, None


def summarise(rows):
    print(f"\n{'arm':>12} {'solvable solved':>16} {'node ratio':>11} "
          f"{'viol':>6} {'false_s':>8} {'arm_only':>9}")

    for name in ARMS:
        arm_rows = [r for r in rows if r["arm"] == name]

        solved = sum(r["solved"] for r in arm_rows)
        solvable = sum(r["solvable"] for r in arm_rows)
        geo_mean = math.exp(statistics.mean(math.log(r["node_ratio"]) for r in arm_rows))

        print(f"{name:>12} {solved / solvable:>15.1%} {geo_mean:>11.2f} "
              f"{sum(r['violations'] for r in arm_rows):>6} "
              f"{sum(r['false_success'] for r in arm_rows):>8} "
              f"{sum(r['arm_only'] for r in arm_rows):>9}")

    print("\n  node ratio = geometric mean of DNF / arm, so above 1 means the arm is smaller")

    # Where scoping changes the region, per protection mode
    by_problem = {}
    for r in rows:
        by_problem.setdefault(r["problem_id"], {})[r["arm"]] = r

    for mode in ("off", "left"):
        differ = sum(1 for p in by_problem.values()
                     if p[f"scoped_{mode}"]["ref_only"] != p[f"global_{mode}"]["ref_only"]
                     or p[f"scoped_{mode}"]["solved"] != p[f"global_{mode}"]["solved"])
        print(f"  protect {mode:>4}: scoped and global solve different state counts "
              f"on {differ}/{len(by_problem)} problems")


def main():
    global MODE, CHECK_PRESET, TARGET_PROBLEMS, SEED

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default=MODE, choices=["nested", "deep", "flat"])
    parser.add_argument("--checks", default=CHECK_PRESET, choices=list(sr.CHECK_PRESETS))
    parser.add_argument("--target", type=int, default=TARGET_PROBLEMS)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--exact", action="store_true",
                        help="prune on exact match only, as published, instead of subset")
    args = parser.parse_args()

    MODE, CHECK_PRESET = args.mode, args.checks
    TARGET_PROBLEMS, SEED = args.target, args.seed

    # Flat goals are drawn as nested goals and then flattened, so they share
    # the nested problems and the nested checks
    sr.MODE = "deep" if MODE == "deep" else "nested"
    checks = sr.CHECK_PRESETS[CHECK_PRESET][sr.MODE]

    random.seed(SEED)

    alg.SUBSET_PRUNE = not args.exact
    alg.DEDUP_C_ATTR = False

    blackboard = py_trees.blackboard.Client(name="PRUNE")
    suffix = "_exact" if args.exact else ""
    out_path = f"pruning_{MODE}_{CHECK_PRESET}{suffix}.csv"

    rows = []
    kept = attempts = 0
    skipped = {"no_admissible_goal": 0, "unsatisfiable": 0}

    # Same loop and skip rules as the soundness sweep, so the problems match
    while kept < TARGET_PROBLEMS and attempts < MAX_ATTEMPTS * TARGET_PROBLEMS:
        problem_rows, reason = runProblem(attempts, blackboard, checks)
        attempts += 1

        if problem_rows is None:
            skipped[reason] += 1
            continue

        rows.extend(problem_rows)
        kept += 1

    print(f"mode {MODE}  checks {CHECK_PRESET} {sorted(checks)}  seed {SEED}  "
          f"pruning {'exact' if args.exact else 'subset'}")
    print(f"problems  : {kept} kept of {attempts} attempts "
          f"({skipped['no_admissible_goal']} no admissible goal, "
          f"{skipped['unsatisfiable']} unsatisfiable)")

    if rows:
        summarise(rows)

    with open(out_path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nwrote {len(rows)} rows to {out_path}")


if __name__ == '__main__':
    main()
