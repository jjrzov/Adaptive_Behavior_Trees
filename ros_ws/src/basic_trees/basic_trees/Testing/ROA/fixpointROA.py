'''
Compares the ROA of a fully expanded unified tree against a fully
expanded DNF baseline on identical problems.
'''
import csv
import py_trees

import basic_trees.algorithms as alg
from basic_trees.Goals.goal_types import OR, AND, GoalSelector
from basic_trees.Goals.goal_tree import fixpointBuilder
from basic_trees.Testing.setup_tests import generateLiterals, generateSolution, getDisjunctSetsWithCosts
from basic_trees.Testing.ROA.Util.membership import *

TARGET_RUNS = 50
CAP = 100

FIELDS = ["problem_id", "both", "unified_only", "dnf_only", "neither",
          "pool_size", "u_nodes", "d_nodes", "u_conditions", "d_conditions",
          "u_unique", "d_unique", "u_expansions", "d_expansions",
          "u_cycles", "d_cycles", "u_violations", "d_violations",
          "shared", "r1", "r2", "caps", "u_false_success", "d_false_success"]


NESTED = True   # False reproduces the flat null test


def buildGoalTerm(d1, d2):
    # Factor the shared literals so the unified arm expands them once.
    # Returns None if factoring is degenerate for this problem.
    shared = set(d1) & set(d2)
    r1 = set(d1) - shared
    r2 = set(d2) - shared

    if not shared or not r1 or not r2:
        # Nothing to share, or one disjunct subsumes the other
        return None

    return AND(*sorted(shared), OR(AND(*sorted(r1)), AND(*sorted(r2)))), shared, r1, r2


def buildDNF(disjuncts, action_db):
    # Each disjunct is its own fixpoint tree, joined only for measurement
    roots, expansions = [], 0
    
    for d in disjuncts:
        root, count = fixpointBuilder(AND(*sorted(d)), action_db)
        roots.append(root)
        expansions += count

    join = GoalSelector(name="DNF", memory=False)
    join.add_children(roots)

    return join, expansions


def runCase(case, out_path):
    alg.SUBSET_PRUNE = True
    alg.DEDUP_C_ATTR = False

    blackboard = py_trees.blackboard.Client(name="ROA")

    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()

        for p_index in range(TARGET_RUNS):
            all_literals = generateLiterals(case["literals"])
            states_db, action_db, states_pool = generateSolution(
                all_literals, case["distance"], case["iterations"], return_pool=True)

            sample = getDisjunctSetsWithCosts(states_db, action_db)
            if sample is None:
                continue
            d1, d2, _, _ = sample

            # Generate the goal terms
            if NESTED:
                factored = buildGoalTerm(d1, d2)
                if factored is None:
                    continue
                goal_term, shared, r1, r2 = factored
            else:
                goal_term = OR(AND(*sorted(d1)), AND(*sorted(d2)))
                shared, r1, r2 = set(d1) & set(d2), set(d1), set(d2)


            # Both arms fully expanded, identical flags
            u_root, u_expansions = fixpointBuilder(goal_term, action_db)
            d_root, d_expansions = buildDNF([d1, d2], action_db)

            # Deduplicate the universe; states_pool holds repeats
            pool = {frozenset(s) for s in states_pool}

            buckets, outcomes, false_success, disagreements = sweep(
                pool, u_root, d_root, goal_term, blackboard, cap=CAP)

            bad = [s for s, u, d in disagreements if u == MEM_VIOLATION]
            # if bad:
                # diagnoseViolation(u_root, bad[0], blackboard, goal_term, shared, action_db)
                # break

            u_stats = treeStats(u_root)
            d_stats = treeStats(d_root)

            writer.writerow({
                "problem_id": p_index,
                "both": buckets["both"],
                "unified_only": buckets["unified_only"],
                "dnf_only": buckets["dnf_only"],
                "neither": buckets["neither"],
                "pool_size": len(pool),
                "u_nodes": u_stats["nodes"],
                "d_nodes": d_stats["nodes"],
                "u_conditions": u_stats["condition_nodes"],
                "d_conditions": d_stats["condition_nodes"],
                "u_unique": u_stats["unique_conditions"],
                "d_unique": d_stats["unique_conditions"],
                "u_expansions": u_expansions,
                "d_expansions": d_expansions,
                "u_cycles": outcomes["unified"][MEM_CYCLE],
                "d_cycles": outcomes["dnf"][MEM_CYCLE],
                "u_violations": outcomes["unified"][MEM_VIOLATION],
                "d_violations": outcomes["dnf"][MEM_VIOLATION],
                "shared": len(shared),
                "r1": len(r1),
                "r2": len(r2),
                "caps": outcomes["unified"][MEM_CAP] + outcomes["dnf"][MEM_CAP],
                "u_false_success": false_success["unified"],
                "d_false_success": false_success["dnf"],
            })


if __name__ == "__main__":
    runCase({"literals": 10, "distance": 10, "iterations": 10}, "roa_nested.csv")