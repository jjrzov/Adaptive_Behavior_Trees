'''
Persistence of success after a membership test.

Finite time success (Definition 2 of Cai et al. 2021) requires the root to keep
reporting SUCCESS once it first does. The membership test stops at the first
tick on which the root reports SUCCESS with the goal holding, so it does not
check that by itself. This script repeats the soundness sweep's problems and,
for every member, ticks the tree once more after that first success.

Each member is classified by that extra tick:

    stationary   SUCCESS, goal holds, state unchanged. Composites carry no
                 memory and actions are deterministic, so the same tick then
                 repeats forever and the success persists indefinitely.
    moving       SUCCESS, goal holds, but the state changed. Persistence is
                 not settled by one tick, so the member is ticked up to
                 EXTRA_TICKS more times until it becomes stationary or is lost.
    lost         The root reported something other than SUCCESS, or the goal
                 stopped holding. Finite time success fails for this member.

Problems are drawn exactly as in soundness_roa.py, with the same seed and skip
rules, so the member counts match the soundness sweep.

Usage:
    python persistence_check.py --mode nested --checks minimal --target 1000
'''
import argparse
import csv
import random

import py_trees

import basic_trees.algorithms as alg
import basic_trees.Testing.ROA.soundness_roa as sr
from basic_trees.Goals.goal_tree import fixpointBuilder, setupWorld
from basic_trees.Goals.goal_types import goalSatisfied
from basic_trees.Testing.ROA.Util.membership import assertMemoryless, solvableDisjuncts


MODE = "nested"
CHECK_PRESET = "minimal"
TARGET_PROBLEMS = 1000
MAX_ATTEMPTS = 50           # Per kept problem
CAP = 100                   # Tick cap for reaching the first success
EXTRA_TICKS = 20            # Further ticks allowed for a member that is still moving
SEED = 0

# Arms that satisfy condition (ii). The unprotected arm is left out, since its
# successes are not guaranteed to lie in S_g in the first place.
ARMS = {"protect_l": "left", "protect_s": "symmetric"}
REFERENCE = "dnf"

FIELDS = ["problem_id", "arm", "members", "stationary", "moving_settled", "lost"]

SUCCESS = py_trees.common.Status.SUCCESS


def tickOnce(root, blackboard, goal_term):
    # One tick, returning whether it ended in SUCCESS inside S_g and the state
    root.tick_once()
    state = frozenset(blackboard.world_state)
    return root.status == SUCCESS and goalSatisfied(goal_term, state), state


def persistence(root, state, blackboard, goal_term):
    # None if the state is not a member, else how its success behaved after
    setupWorld(blackboard, set(state))
    for node in root.iterate():
        node.stop(py_trees.common.Status.INVALID)

    for _ in range(CAP):
        succeeded, current = tickOnce(root, blackboard, goal_term)
        if succeeded:
            break
    else:
        return None

    # The tick after the first success decides the classification
    succeeded, after = tickOnce(root, blackboard, goal_term)
    if not succeeded:
        return "lost"
    if after == current:
        return "stationary"

    # Still moving: follow it until it settles or is lost
    for _ in range(EXTRA_TICKS):
        current = after
        succeeded, after = tickOnce(root, blackboard, goal_term)
        if not succeeded:
            return "lost"
        if after == current:
            return "moving_settled"

    return "lost"           # Did not settle within the allowance


def main():
    global MODE, CHECK_PRESET, TARGET_PROBLEMS, SEED

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default=MODE, choices=["nested", "deep"])
    parser.add_argument("--checks", default=CHECK_PRESET, choices=list(sr.CHECK_PRESETS))
    parser.add_argument("--target", type=int, default=TARGET_PROBLEMS)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    MODE, CHECK_PRESET = args.mode, args.checks
    TARGET_PROBLEMS, SEED = args.target, args.seed

    sr.MODE = MODE
    checks = sr.CHECK_PRESETS[CHECK_PRESET][MODE]

    random.seed(SEED)
    alg.SUBSET_PRUNE = True
    alg.DEDUP_C_ATTR = False

    blackboard = py_trees.blackboard.Client(name="PERSIST")
    names = list(ARMS) + [REFERENCE]
    totals = {name: {"members": 0, "stationary": 0, "moving_settled": 0, "lost": 0}
              for name in names}
    rows = []

    kept = attempts = 0

    # Same loop and skip rules as the soundness sweep, so the problems match
    while kept < TARGET_PROBLEMS and attempts < MAX_ATTEMPTS * TARGET_PROBLEMS:
        problem_id = attempts
        attempts += 1

        problem = sr.syntheticProblem(checks)
        if problem is None:
            continue

        goal_term, shared, r1, r2, disjuncts, action_db, pool = problem

        n_solvable, n_disjuncts = solvableDisjuncts(disjuncts, pool, action_db)
        if n_solvable < n_disjuncts:
            continue

        kept += 1

        roots = {name: fixpointBuilder(goal_term, action_db, protect_mode=mode)[0]
                 for name, mode in ARMS.items()}
        roots[REFERENCE] = sr.buildReference(disjuncts, action_db)[0]

        for name, root in roots.items():
            assertMemoryless(root)
            counts = {"members": 0, "stationary": 0, "moving_settled": 0, "lost": 0}

            for state in pool:
                outcome = persistence(root, state, blackboard, goal_term)
                if outcome is None:
                    continue
                counts["members"] += 1
                counts[outcome] += 1

            for key, value in counts.items():
                totals[name][key] += value

            rows.append({"problem_id": problem_id, "arm": name, **counts})

    print(f"mode {MODE}  checks {CHECK_PRESET} {sorted(checks)}  seed {SEED}")
    print(f"problems  : {kept} kept of {attempts} attempts\n")
    print(f"{'arm':>10} {'members':>8} {'stationary':>11} {'settled':>8} {'lost':>6}")

    for name in names:
        t = totals[name]
        print(f"{name:>10} {t['members']:>8} {t['stationary']:>11} "
              f"{t['moving_settled']:>8} {t['lost']:>6}")

    out_path = f"persistence_{MODE}_{CHECK_PRESET}.csv"
    with open(out_path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nwrote {len(rows)} rows to {out_path}")


if __name__ == '__main__':
    main()