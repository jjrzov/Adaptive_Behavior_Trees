"""
Pruning mode comparison.

Question: cross-disjunct pruning removes the fallback route to the other
disjunct. Scoped pruning restricts removal to within a disjunct. How much of
the size saving does scoping give up, and where does it land relative to DNF?

Every mode runs on the SAME generated problem, so node-count differences are
attributable to the pruning policy rather than to problem variation. DNF is a
fixed baseline - each of its trees holds a single disjunct, so pruning within
one is already scoped by construction.

Traversal is held at BFS throughout: pruning and traversal are independent.
"""

import basic_trees.algorithms as alg
import basic_trees.Goals.goal_tree as gt

from basic_trees.Testing.setup_tests import (
    generateLiterals, generateSolution, getDisjunctSetsWithCosts)
from basic_trees.Goals.goal_tree import runTree, runDNF
from basic_trees.Goals.goal_types import OR, AND
from basic_trees.Testing.test_tree import getNodeCount
from basic_trees.traverse import BFS


TARGET_RUNS = 500
MODES = ("none", "scoped", "global")


def blankStats():
    return {"nodes": [], "expansions": [], "solved": 0, "attempted": 0}


def record(stats, root, expansions):
    stats["attempted"] += 1
    stats["expansions"].append(expansions)
    if root is not False:
        stats["solved"] += 1
        stats["nodes"].append(getNodeCount(root))


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def runCase(case):
    alg.SUBSET_PRUNE = False
    alg.DEDUP_C_ATTR = False

    stats = {m: blankStats() for m in MODES}
    stats["DNF"] = blankStats()

    # Per-problem node counts, kept aligned so modes can be compared pairwise
    paired = []

    problems = 0
    for p_index in range(TARGET_RUNS):
        all_literals = generateLiterals(case["literals"])
        states_db, action_db = generateSolution(
            all_literals, case["distance"], case["iterations"])

        sample = getDisjunctSetsWithCosts(states_db, action_db)
        if sample is None:
            continue
        d1, d2, _, _ = sample
        goal = OR(AND(*d1), AND(*d2))

        problems += 1
        row = {}

        for mode in MODES:
            gt.PRUNE_MODE = mode
            root, exp, _ = runTree(
                states_db[0].copy(), goal, action_db, traverse=BFS())
            record(stats[mode], root, exp)
            row[mode] = getNodeCount(root) if root is not False else None

        # DNF ignores PRUNE_MODE - each tree is one disjunct already
        root, exp, _ = runDNF(
            states_db[0].copy(), [d1, d2], action_db, traverse=BFS())
        record(stats["DNF"], root, exp)
        row["DNF"] = getNodeCount(root) if root is not False else None

        paired.append(row)

        if problems % 100 == 0:
            print(f"  {problems} problems")

    return stats, paired, problems


def report(stats, paired, problems):
    print(f"\n{problems} problems\n")
    print(f"  {'mode':<10} {'nodes':>9} {'expansions':>12} "
          f"{'solved':>9} {'vs DNF':>9}")

    dnf_nodes = mean(stats["DNF"]["nodes"])

    for name in list(MODES) + ["DNF"]:
        s = stats[name]
        if not s["attempted"]:
            continue
        n = mean(s["nodes"])
        ratio = n / dnf_nodes if dnf_nodes == dnf_nodes else float("nan")
        print(f"  {name:<10} {n:>9.1f} {mean(s['expansions']):>12.1f} "
              f"{100*s['solved']/s['attempted']:>8.1f}% {ratio:>9.2f}")

    # What scoping gives up relative to global, per problem
    both = [(r["scoped"], r["global"], r["none"]) for r in paired
            if r["scoped"] and r["global"] and r["none"]]
    if both:
        saved_global = mean([n - g for _, g, n in both])
        saved_scoped = mean([n - s for s, _, n in both])
        print(f"\n  nodes removed vs no pruning:")
        print(f"    global: {saved_global:>6.1f}")
        print(f"    scoped: {saved_scoped:>6.1f}  "
              f"({100*saved_scoped/saved_global:.0f}% of global)"
              if saved_global else "")

        wins = sum(1 for s, g, _ in both if s < g)
        ties = sum(1 for s, g, _ in both if s == g)
        print(f"\n  scoped vs global, per problem: "
              f"scoped smaller {wins}, tied {ties}, "
              f"scoped larger {len(both) - wins - ties}")


def main():
    case = {"case": 1, "literals": 100, "distance": 100, "iterations": 100}
    print(f"literals = {case['literals']}, distance = {case['distance']}, "
          f"iterations = {case['iterations']}, subset_prune = False")

    stats, paired, problems = runCase(case)
    report(stats, paired, problems)


if __name__ == "__main__":
    main()