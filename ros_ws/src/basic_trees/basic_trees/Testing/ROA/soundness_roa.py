'''
Experiment 1 - soundness.

Separately expanded conjuncts under a GoalSequence let an action admitted into
one sibling delete a literal another sibling has already established. With
memory=False the sequence ticks both children in one tick and does not
re-check the first, so the root can report SUCCESS on a state where the goal is
false. The protect guard forbids those actions at build time.

Arms, all measured against DNF on identical problems:

  unified      PROTECT_MODE off - reproduces the defect
  protect_l    protect against left siblings only
  protect_s    protect against all siblings
  dnf          one fixpoint tree per disjunct, joined under a fallback.
               Sound and complete by construction, so it is the reference and
               never an arm under test.

Reporting rules this file enforces, because getting them wrong makes the
numbers unreadable:

  - node_ratio is DNF / arm throughout. Above 1 means the arm is smaller.
  - an honest FAILURE and a dead-end false success are different outcomes.
    MEM_VIOLATION is counted separately and never folded into "neither".
  - tick soundness requires BOTH false_success == 0 and violations == 0.
  - arm_only must be zero. DNF is sound and complete, so an arm solving a
    state DNF cannot is a bug in the harness, not a result.
  - completeness is scored against DNF only, never against unpr otected
    unified, whose ROA contains states it does not actually solve.
  - a goal whose conjunction is satisfiable in no reachable state is dropped,
    otherwise FAILURE everywhere is scored as lost completeness.

Usage:
    python soundness_roa.py --mode nested --checks shared --target 1000
'''

import argparse
import csv
import math
import random
import statistics

import py_trees

import basic_trees.algorithms as alg
from basic_trees.Goals.goal_types import AND, OR
from basic_trees.Goals.goal_tree import fixpointBuilder
from basic_trees.Testing.setup_tests import generateLiterals, generateSolution, getRandomSubset, unweightedDistToSubset, MAX_HOP_GAP
from basic_trees.Testing.ROA.Util.membership import (sweepArms, treeStats, conflictStats, solvableDisjuncts, solvableStates,
                                                    MEM_SUCCESS, MEM_FAILURE, MEM_CYCLE, MEM_CAP, MEM_VIOLATION)


MODE = "nested"             # "nested" | "deep"
TARGET_PROBLEMS = 1000      # Admissible problems to keep
MAX_ATTEMPTS = 50           # Per kept problem, so a strict filter cannot loop forever
GOAL_ATTEMPTS = 50          # Goal draws per generated pool before the pool is discarded
CAP = 100
SEED = 0

CASE = {"literals": 10, "distance": 10, "iterations": 10}

# Admissibility checks on a drawn goal, applied per goal shape:
#   init     no disjunct already holds in the initial state
#   subsume  neither operand of any OR contains the other, so every OR offers
#            a genuine alternative
#   hop_gap  every disjunct is reachable along the generated path, and their
#            hop distances from the initial state differ by at most MAX_HOP_GAP
CHECK_PRESETS = {
    # The same full set for both shapes
    "full":   {"nested": {"init", "subsume", "hop_gap"},
                 "deep":   {"init", "subsume", "hop_gap"}},
    # Only the check that changes what the goal means. init and hop_gap concern
    # the initial state, which neither the fixpoint tree nor pool scoring uses.
    "minimal":  {"nested": {"subsume"}, "deep": {"subsume"}},
}
CHECK_PRESET = "minimal"

# name -> protect_mode. The reference arm is added separately.
ARMS = {"unified": "off", "protect_l": "left", "protect_s": "symmetric"}
REFERENCE = "dnf"

# Drop problems where some disjunct is satisfiable in no reachable state
REQUIRE_ALL_SOLVABLE = True

FIELDS = ["problem_id", "arm", "protect_mode", "pool_size",
          "nodes", "ref_nodes", "node_ratio",
          "expansions", "ref_expansions", "expansion_ratio", "filtered",
          "solved", "both", "arm_only", "ref_only", "neither",
          "failure", "cycle", "cap", "violations", "false_success",
          "ref_violations", "ref_false_success",
          "ref_violations", "ref_false_success", "ref_failure", "ref_cycle",
          "solvable",
          "shared", "r1", "r2", "n_disjuncts", "n_solvable",
          "db_actions", "db_conflict", "mean_del",
          "branch_actions", "branch_conflict"]


def drawNestedGoal(states_db):
    # AND(shared, OR(r1, r2)) from two path states. Factoring the shared
    # literals out is what makes the unified arm expand them once, and is also
    # what creates the sibling the OR branch can break.
    s1 = set(random.choice(states_db))
    s2 = set(random.choice(states_db))

    if s1 == s2:
        return None

    d1, d2 = getRandomSubset(s1), getRandomSubset(s2)

    shared = d1 & d2
    r1, r2 = d1 - shared, d2 - shared

    if not shared or not r1 or not r2:
        return None         # nothing to factor, or one OR operand is empty

    return {
        "goal": AND(*sorted(shared), OR(AND(*sorted(r1)), AND(*sorted(r2)))),
        "shared": shared,
        "operands": [(r1, r2)],
        "disjuncts": [d1, d2],
        "r1": r1, "r2": r2,
    }


def drawDeepGoal(states_db):
    # AND(shared, OR(A1, A2), OR(B1, B2)). DNF must enumerate four disjuncts.
    s1 = set(random.choice(states_db))
    s2 = set(random.choice(states_db))

    if s1 == s2:
        return None

    shared = getRandomSubset(s1 & s2)
    if not shared:
        return None

    d1 = getRandomSubset(s1) - shared
    d2 = getRandomSubset(s2) - shared
    if len(d1) < 2 or len(d2) < 2:
        return None

    l1, l2 = sorted(d1), sorted(d2)
    random.shuffle(l1)
    random.shuffle(l2)

    c1, c2 = len(l1) // 2, len(l2) // 2
    A1, B1 = set(l1[:c1]), set(l1[c1:])
    A2, B2 = set(l2[:c2]), set(l2[c2:])

    if not (A1 and B1 and A2 and B2):
        return None

    return {
        "goal": AND(*sorted(shared),
                    OR(AND(*sorted(A1)), AND(*sorted(A2))),
                    OR(AND(*sorted(B1)), AND(*sorted(B2)))),
        "shared": shared,
        "operands": [(A1, A2), (B1, B2)],
        "disjuncts": [shared | X | Y for X in (A1, A2) for Y in (B1, B2)],
        "r1": A1 | A2, "r2": B1 | B2,
    }


def admissible(built, states_db, action_db, checks):
    # Apply the configured checks to a drawn goal
    init_state = set(states_db[0])

    if "init" in checks and any(set(d) <= init_state for d in built["disjuncts"]):
        return False

    if "subsume" in checks and any(a <= b or b <= a for a, b in built["operands"]):
        return False

    if "hop_gap" in checks:
        hops = [unweightedDistToSubset(states_db, action_db, set(d))
                for d in built["disjuncts"]]

        # An infinite distance means the disjunct is not reachable along the
        # path, and inf - inf is nan, so it has to be rejected explicitly
        if any(math.isinf(h) for h in hops) or max(hops) - min(hops) > MAX_HOP_GAP:
            return False

    return True


def sampleGoal(states_db, action_db, mode, checks):
    draw = drawDeepGoal if mode == "deep" else drawNestedGoal

    for _ in range(GOAL_ATTEMPTS):
        built = draw(states_db)

        if built is not None and admissible(built, states_db, action_db, checks):
            return built

    return None


def syntheticProblem(checks):
    all_literals = generateLiterals(CASE["literals"])
    states_db, action_db, states_pool = generateSolution(
        all_literals, CASE["distance"], CASE["iterations"], return_pool=True)

    built = sampleGoal(states_db, action_db, MODE, checks)

    if built is None:
        return None

    pool = {frozenset(s) for s in states_pool}   # states_pool holds repeats

    return (built["goal"], built["shared"], built["r1"], built["r2"],
            built["disjuncts"], action_db, pool)


def buildReference(disjuncts, action_db):
    # DNF: each disjunct regressed jointly in its own tree, never protected.
    # Joined under a plain fallback only so the sweep has one root to tick.
    roots, expansions = [], 0

    for disjunct in disjuncts:
        root, count = fixpointBuilder(AND(*sorted(disjunct)), action_db,
                                      protect_mode="off")
        roots.append(root)
        expansions += count

    join = py_trees.composites.Selector(name="DNF", memory=False)
    join.add_children(roots)

    return join, expansions


def buildArms(goal_term, disjuncts, action_db):
    # Every arm is built from the same goal and action set. protect_mode is
    # passed explicitly rather than read from the module flag, so building
    # several arms in one process cannot pick up a stale value.
    roots, expansions, filtered = {}, {}, {}

    for name, mode in ARMS.items():
        alg.PROTECT_STATS["filtered"] = 0

        root, count = fixpointBuilder(goal_term, action_db, protect_mode=mode)

        roots[name] = root
        expansions[name] = count
        filtered[name] = alg.PROTECT_STATS["filtered"]

    roots[REFERENCE], expansions[REFERENCE] = buildReference(disjuncts, action_db)
    filtered[REFERENCE] = 0

    return roots, expansions, filtered


def runProblem(p_index, blackboard, checks):
    problem = syntheticProblem(checks)

    if problem is None:
        return None, "no_admissible_goal"

    goal_term, shared, r1, r2, disjuncts, action_db, pool = problem

    n_solvable, n_disjuncts = solvableDisjuncts(disjuncts, pool, action_db)

    if REQUIRE_ALL_SOLVABLE and n_solvable < n_disjuncts:
        # FAILURE everywhere here would be correct behaviour, so scoring it as
        # lost completeness would understate every arm
        return None, "unsatisfiable"

    roots, expansions, filtered = buildArms(goal_term, disjuncts, action_db)

    outcomes, false_success, solved, buckets = sweepArms(
        pool, roots, goal_term, blackboard, reference=REFERENCE, cap=CAP)

    # States from which the goal is reachable at all
    solvable = solvableStates(pool, goal_term, action_db)

    for name, members in solved.items():
        if members - solvable:
            raise AssertionError(f"{name} is a member on {len(members - solvable)} "f"states from which the goal is unreachable")

    stats = {name: treeStats(root) for name, root in roots.items()}
    ref_nodes = stats[REFERENCE]["nodes"]
    ref_expansions = expansions[REFERENCE]

    rows = []

    for name in ARMS:
        conflicts = conflictStats(roots[name], shared, action_db)
        bucket = buckets[name]

        rows.append({
            "problem_id": p_index,
            "arm": name,
            "protect_mode": ARMS[name],
            "pool_size": len(pool),
            "nodes": stats[name]["nodes"],
            "ref_nodes": ref_nodes,
            "node_ratio": round(ref_nodes / stats[name]["nodes"], 4),
            "expansions": expansions[name],
            "ref_expansions": ref_expansions,
            "expansion_ratio": round(ref_expansions / expansions[name], 4)
                               if expansions[name] else 0.0,
            "filtered": filtered[name],
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
            "ref_violations": outcomes[REFERENCE][MEM_VIOLATION],
            "ref_false_success": false_success[REFERENCE],
            "ref_failure": outcomes[REFERENCE][MEM_FAILURE],
            "ref_cycle": outcomes[REFERENCE][MEM_CYCLE],
            "solvable": len(solvable),
            "shared": len(shared),
            "r1": len(r1),
            "r2": len(r2),
            "n_disjuncts": n_disjuncts,
            "n_solvable": n_solvable,
            **conflicts,
        })

    return rows, None


def summarise(rows):
    print(f"\n{'arm':>10} {'ROA pres':>9} {'ref_only':>9} {'arm_only':>9} "
          f"{'false_s':>8} {'viol':>6} {'cycles':>7} {'filtered':>9} "
          f"{'node ratio':>11}")

    for name in ARMS:
        arm_rows = [r for r in rows if r["arm"] == name]
        if not arm_rows:
            continue

        both = sum(r["both"] for r in arm_rows)
        ref_only = sum(r["ref_only"] for r in arm_rows)
        arm_only = sum(r["arm_only"] for r in arm_rows)

        preservation = both / (both + ref_only) if (both + ref_only) else 1.0
        ratios = [r["node_ratio"] for r in arm_rows]

        print(f"{name:>10} {preservation:>8.1%} {ref_only:>9} {arm_only:>9} "
              f"{sum(r['false_success'] for r in arm_rows):>8} "
              f"{sum(r['violations'] for r in arm_rows):>6} "
              f"{sum(r['cycle'] for r in arm_rows):>7} "
              f"{sum(r['filtered'] for r in arm_rows):>9} "
              f"{statistics.mean(ratios):>7.2f} "
              f"±{statistics.stdev(ratios) if len(ratios) > 1 else 0.0:.2f}")

    print("\n  ROA pres = both / (both + ref_only), against the DNF reference")
    print("  node ratio = DNF / arm, so above 1 means the arm is smaller")

    # Tick soundness needs both counters clear, and arm_only clear is a
    # harness check rather than a result
    print()
    for name in ARMS:
        arm_rows = [r for r in rows if r["arm"] == name]
        if not arm_rows:
            continue

        unsound = (sum(r["false_success"] for r in arm_rows)
                   + sum(r["violations"] for r in arm_rows))
        leaked = sum(r["arm_only"] for r in arm_rows)

        verdict = "no false SUCCESS observed" if not unsound else f"UNSOUND ({unsound} events)"
        print(f"  {name:>10}: {verdict}"
              + (f"   ** arm_only = {leaked}, harness bug **" if leaked else ""))


def main():
    global MODE, CHECK_PRESET, TARGET_PROBLEMS, SEED

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default=MODE, choices=["nested", "deep"])
    parser.add_argument("--checks", default=CHECK_PRESET, choices=list(CHECK_PRESETS))
    parser.add_argument("--target", type=int, default=TARGET_PROBLEMS)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    MODE, CHECK_PRESET = args.mode, args.checks
    TARGET_PROBLEMS, SEED = args.target, args.seed
    checks = CHECK_PRESETS[CHECK_PRESET][MODE]

    random.seed(SEED)

    alg.SUBSET_PRUNE = True
    alg.DEDUP_C_ATTR = False

    blackboard = py_trees.blackboard.Client(name="ROA")
    out_path = f"soundness_{MODE}_{CHECK_PRESET}.csv"

    rows = []
    kept = 0
    attempts = 0
    skipped = {"no_admissible_goal": 0, "unsatisfiable": 0}

    # Draw until the target is reached, so the sample size is fixed
    while kept < TARGET_PROBLEMS and attempts < MAX_ATTEMPTS * TARGET_PROBLEMS:
        problem_rows, reason = runProblem(attempts, blackboard, checks)
        attempts += 1

        if problem_rows is None:
            skipped[reason] += 1
            continue

        rows.extend(problem_rows)
        kept += 1

    pooled = sum(r["pool_size"] for r in rows if r["arm"] == list(ARMS)[0])

    print(f"mode {MODE}  checks {CHECK_PRESET} {sorted(checks)}  seed {SEED}")
    print(f"problems  : {kept} kept of {attempts} attempts "
          f"({skipped['no_admissible_goal']} no admissible goal, "
          f"{skipped['unsatisfiable']} unsatisfiable)")
    if kept < TARGET_PROBLEMS:
        print(f"  ** stopped at the attempt limit before reaching {TARGET_PROBLEMS} **")
    print(f"pooled    : {pooled} states")

    if rows:
        conflict = [r for r in rows if r["arm"] == list(ARMS)[0]]
        branch = sum(r["branch_actions"] for r in conflict)
        clash = sum(r["branch_conflict"] for r in conflict)
        print(f"conflict  : {clash}/{branch} OR-branch actions delete a shared "
              f"literal ({clash / branch:.1%})" if branch else "conflict  : n/a")

        summarise(rows)

    with open(out_path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nwrote {len(rows)} rows to {out_path}")


if __name__ == '__main__':
    main()