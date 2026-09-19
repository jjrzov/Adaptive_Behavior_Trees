'''
Compares the ROA of a fully expanded unified tree against a fully
expanded DNF baseline on identical problems.
'''
import csv
import py_trees
import random

import basic_trees.algorithms as alg
from basic_trees.Goals.goal_types import OR, AND, GoalSelector
from basic_trees.Goals.goal_tree import fixpointBuilder
from basic_trees.Testing.setup_tests import *
from basic_trees.Testing.ROA.Util.membership import *
from basic_trees.Testing.ROA.Util.nav_domain import *


FIELDS = ["problem_id", "both", "unified_only", "dnf_only", "neither",
          "pool_size", "u_nodes", "d_nodes", "u_conditions", "d_conditions",
          "u_unique", "d_unique", "u_expansions", "d_expansions",
          "u_cycles", "d_cycles", "u_violations", "d_violations",
          "shared", "r1", "r2", "caps", "u_false_success", "d_false_success",
          "db_actions", "db_conflict", "mean_del", "branch_actions", "branch_conflict",
          "n_disjuncts", "n_solvable", "interfere_p"]


TARGET_RUNS = 60
CAP = 100
MODE = "nested"         # "flat" | "nested" | "deep"
DOMAIN = "nav"          # "synthetic" | "nav"


# Navigation domain only: interference cycles through these across problems
INTERFERE_PS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
NAV_START = {"at_B"}


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


def buildDeepGoalTerm(states_db):
    # AND(shared, OR(A1, A2), OR(B1, B2)) -> DNF must enumerate 4 disjuncts.
    # Split one subset per state so at least two of the four are reachable.
    for _ in range(50):
        s1 = set(random.choice(states_db))
        s2 = set(random.choice(states_db))
        if s1 == s2:
            continue

        shared = getRandomSubset(s1 & s2)
        if not shared:
            continue

        d1 = getRandomSubset(s1) - shared
        d2 = getRandomSubset(s2) - shared
        if len(d1) < 2 or len(d2) < 2:
            continue

        # Split each state's residual into the two OR groups
        l1, l2 = sorted(d1), sorted(d2)
        random.shuffle(l1)
        random.shuffle(l2)
        c1, c2 = len(l1) // 2, len(l2) // 2
        A1, B1 = set(l1[:c1]), set(l1[c1:])
        A2, B2 = set(l2[:c2]), set(l2[c2:])

        if not (A1 and B1 and A2 and B2):
            continue

        goal_term = AND(*sorted(shared),
                        OR(AND(*sorted(A1)), AND(*sorted(A2))),
                        OR(AND(*sorted(B1)), AND(*sorted(B2))))

        # Equivalent DNF: one conjunction per combination
        disjuncts = [shared | X | Y for X in (A1, A2) for Y in (B1, B2)]

        return goal_term, shared, A1 | A2, B1 | B2, disjuncts

    return None


def syntheticProblem(case):
    # Random STRIPS problem from the base paper's generator
    all_literals = generateLiterals(case["literals"])
    states_db, action_db, states_pool = generateSolution(
        all_literals, case["distance"], case["iterations"], return_pool=True)

    sample = getDisjunctSetsWithCosts(states_db, action_db)
    if sample is None:
        return None
    d1, d2, _, _ = sample

    # Generate the goal terms
    if MODE == "deep":
        deep = buildDeepGoalTerm(states_db)
        if deep is None:
            return None
        goal_term, shared, r1, r2, disjuncts = deep
    elif MODE == "nested":
        factored = buildGoalTerm(d1, d2)
        if factored is None:
            return None
        goal_term, shared, r1, r2 = factored
        disjuncts = [d1, d2]
    else:
        shared = set(d1) & set(d2)
        goal_term = OR(AND(*sorted(d1)), AND(*sorted(d2)))
        r1, r2 = set(d1) - shared, set(d2) - shared
        disjuncts = [d1, d2]

    # Deduplicate the universe; states_pool holds repeats
    pool = {frozenset(s) for s in states_pool}

    return goal_term, shared, r1, r2, disjuncts, action_db, pool, 0.0


def navProblem(p_index):
    # Navigation-style domain: small del sets, interference as an explicit knob
    interfere_p = INTERFERE_PS[p_index % len(INTERFERE_PS)]
    rng = random.Random(p_index)
    rooms = DEFAULT_ROOMS
    key_room, box_room, drop_room = rng.sample(rooms, 3)
    action_db = buildNavDomain(key_room=key_room, box_room=box_room,
                               drop_room=drop_room, interfere_p=interfere_p, rng=rng)
    pool = enumerateStates(NAV_START, action_db)   # Exact reachable universe

    shared = {"has_key"}

    if MODE == "deep":
        # The second OR must be over flags; room literals are mutually exclusive
        goal_term = AND("has_key",
                        OR(AND("at_A"), AND("at_C")),
                        OR(AND("has_box"), AND("box_delivered")))
        r1, r2 = {"at_A", "at_C"}, {"has_box", "box_delivered"}
        disjuncts = [shared | {x} | {y} for x in sorted(r1) for y in sorted(r2)]
    elif MODE == "nested":
        goal_term = AND("has_key", OR(AND("at_A"), AND("at_C")))
        r1, r2 = {"at_A"}, {"at_C"}
        disjuncts = [shared | r1, shared | r2]
    else:
        goal_term = OR(AND("at_A", "has_key"), AND("at_C", "has_key"))
        r1, r2 = {"at_A"}, {"at_C"}
        disjuncts = [shared | r1, shared | r2]

    return goal_term, shared, r1, r2, disjuncts, action_db, pool, interfere_p


def runCase(case, out_path):
    alg.SUBSET_PRUNE = True
    alg.DEDUP_C_ATTR = False

    blackboard = py_trees.blackboard.Client(name="ROA")

    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()

        for p_index in range(TARGET_RUNS):
            problem = (navProblem(p_index) if DOMAIN == "nav"
                       else syntheticProblem(case))
            if problem is None:
                continue

            goal_term, shared, r1, r2, disjuncts, action_db, pool, interfere_p = problem

            u_root, u_expansions = fixpointBuilder(goal_term, action_db)
            d_root, d_expansions = buildDNF(disjuncts, action_db)

            buckets, outcomes, false_success, disagreements = sweep(
                pool, u_root, d_root, goal_term, blackboard, cap=CAP)

            bad = [s for s, u, d in disagreements if u == MEM_VIOLATION]
            # if bad:
                # diagnoseViolation(u_root, bad[0], blackboard, goal_term, shared, action_db)
                # break

            conflicts = conflictStats(u_root, shared, action_db)

            u_stats = treeStats(u_root)
            d_stats = treeStats(d_root)

            n_solvable, n_total = solvableDisjuncts(disjuncts, pool, action_db)

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
                **conflicts,
                "n_disjuncts": n_total,
                "n_solvable": n_solvable,
                "interfere_p": interfere_p,
            })


if __name__ == "__main__":
    out = "roa_nav.csv" if DOMAIN == "nav" else f"roa_{MODE}.csv"
    runCase({"literals": 10, "distance": 10, "iterations": 10}, out)