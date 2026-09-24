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
'''
import csv
import random
import statistics

import py_trees

import basic_trees.algorithms as alg
from basic_trees.Goals.goal_types import AND, OR, GoalSelector
from basic_trees.Goals.goal_tree import fixpointBuilder
from basic_trees.Testing.setup_tests import (generateLiterals, generateSolution,
                                             getDisjunctSetsWithCosts,
                                             getRandomSubset)
from basic_trees.Testing.ROA.Util.membership import (
    sweepArms, treeStats, conflictStats, solvableDisjuncts,
    MEM_SUCCESS, MEM_FAILURE, MEM_CYCLE, MEM_CAP, MEM_VIOLATION)
from basic_trees.Testing.ROA.Util.nav_domain import (buildNavDomain,
                                                     enumerateStates,
                                                     DEFAULT_ROOMS)


DOMAIN = "synthetic"        # "synthetic" | "nav"
MODE = "nested"             # "nested" | "deep"
TARGET_RUNS = 50
CAP = 100
SEED = 0

CASE = {"literals": 10, "distance": 10, "iterations": 10}

# name -> protect_mode. The reference arm is added separately.
ARMS = {"unified": "off", "protect_l": "left", "protect_s": "symmetric"}
REFERENCE = "dnf"

# Drop problems where some disjunct is satisfiable in no reachable state
REQUIRE_ALL_SOLVABLE = True

NAV_START = {"at_B"}
INTERFERE_PS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]

FIELDS = ["problem_id", "arm", "protect_mode", "pool_size",
          "nodes", "ref_nodes", "node_ratio",
          "expansions", "ref_expansions", "expansion_ratio", "filtered",
          "solved", "both", "arm_only", "ref_only", "neither",
          "failure", "cycle", "cap", "violations", "false_success",
          "ref_violations", "ref_false_success",
          "shared", "r1", "r2", "n_disjuncts", "n_solvable",
          "db_actions", "db_conflict", "mean_del",
          "branch_actions", "branch_conflict", "interfere_p"]


def buildNestedGoal(d1, d2):
    # AND(shared, OR(r1, r2)). Factoring the shared literals out is what makes
    # the unified arm expand them once, and is also what creates the sibling
    # the OR branch can break.
    shared = set(d1) & set(d2)
    r1 = set(d1) - shared
    r2 = set(d2) - shared

    if not shared or not r1 or not r2:
        return None         # nothing shared, or one disjunct subsumes the other

    goal_term = AND(*sorted(shared),
                    OR(AND(*sorted(r1)), AND(*sorted(r2))))

    return goal_term, shared, r1, r2, [d1, d2]


def buildDeepGoal(states_db):
    # AND(shared, OR(A1, A2), OR(B1, B2)) - DNF must enumerate four disjuncts
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

        disjuncts = [shared | X | Y for X in (A1, A2) for Y in (B1, B2)]

        return goal_term, shared, A1 | A2, B1 | B2, disjuncts

    return None


def syntheticProblem():
    all_literals = generateLiterals(CASE["literals"])
    states_db, action_db, states_pool = generateSolution(
        all_literals, CASE["distance"], CASE["iterations"], return_pool=True)

    if MODE == "deep":
        built = buildDeepGoal(states_db)
    else:
        sample = getDisjunctSetsWithCosts(states_db, action_db)
        if sample is None:
            return None
        d1, d2, _, _ = sample
        built = buildNestedGoal(d1, d2)

    if built is None:
        return None

    goal_term, shared, r1, r2, disjuncts = built
    pool = {frozenset(s) for s in states_pool}   # states_pool holds repeats

    return goal_term, shared, r1, r2, disjuncts, action_db, pool, 0.0


def navProblem(p_index):
    interfere_p = INTERFERE_PS[p_index % len(INTERFERE_PS)]
    rng = random.Random(p_index)

    key_room, box_room, drop_room = rng.sample(DEFAULT_ROOMS, 3)
    action_db = buildNavDomain(key_room=key_room, box_room=box_room,
                               drop_room=drop_room, interfere_p=interfere_p,
                               rng=rng)
    pool = enumerateStates(NAV_START, action_db)

    shared = {"has_key"}

    if MODE == "deep":
        # The second OR must be over flags - room literals are mutually exclusive
        goal_term = AND("has_key",
                        OR(AND("at_A"), AND("at_C")),
                        OR(AND("has_box"), AND("box_delivered")))
        r1, r2 = {"at_A", "at_C"}, {"has_box", "box_delivered"}
        disjuncts = [shared | {x} | {y} for x in sorted(r1) for y in sorted(r2)]
    else:
        goal_term = AND("has_key", OR(AND("at_A"), AND("at_C")))
        r1, r2 = {"at_A"}, {"at_C"}
        disjuncts = [shared | r1, shared | r2]

    return goal_term, shared, r1, r2, disjuncts, action_db, pool, interfere_p


def buildReference(disjuncts, action_db):
    # DNF: each disjunct regressed jointly in its own tree, never protected.
    # Joined under a fallback only so the sweep has one root to tick.
    roots, expansions = [], 0

    for disjunct in disjuncts:
        root, count = fixpointBuilder(AND(*sorted(disjunct)), action_db,
                                      protect_mode="off")
        roots.append(root)
        expansions += count

    join = GoalSelector(name="DNF", memory=False)
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


def runProblem(p_index, blackboard):
    problem = navProblem(p_index) if DOMAIN == "nav" else syntheticProblem()

    if problem is None:
        return None, "ungeneratable"

    goal_term, shared, r1, r2, disjuncts, action_db, pool, interfere_p = problem

    n_solvable, n_disjuncts = solvableDisjuncts(disjuncts, pool, action_db)

    if REQUIRE_ALL_SOLVABLE and n_solvable < n_disjuncts:
        # FAILURE everywhere here would be correct behaviour, so scoring it as
        # lost completeness would understate every arm
        return None, "unsatisfiable"

    roots, expansions, filtered = buildArms(goal_term, disjuncts, action_db)

    outcomes, false_success, solved, buckets = sweepArms(
        pool, roots, goal_term, blackboard, reference=REFERENCE, cap=CAP)

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
            "shared": len(shared),
            "r1": len(r1),
            "r2": len(r2),
            "n_disjuncts": n_disjuncts,
            "n_solvable": n_solvable,
            **conflicts,
            "interfere_p": interfere_p,
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
    random.seed(SEED)

    alg.SUBSET_PRUNE = True
    alg.DEDUP_C_ATTR = False

    blackboard = py_trees.blackboard.Client(name="ROA")
    out_path = f"soundness_{DOMAIN}_{MODE}.csv"

    rows = []
    skipped = {"ungeneratable": 0, "unsatisfiable": 0}

    for p_index in range(TARGET_RUNS):
        problem_rows, reason = runProblem(p_index, blackboard)

        if problem_rows is None:
            skipped[reason] += 1
            continue

        rows.extend(problem_rows)

    problems = len({r["problem_id"] for r in rows})
    pooled = sum(r["pool_size"] for r in rows if r["arm"] == list(ARMS)[0])

    print(f"domain {DOMAIN}  mode {MODE}  seed {SEED}")
    print(f"problems  : {problems} kept of {TARGET_RUNS} "
          f"({skipped['ungeneratable']} ungeneratable, "
          f"{skipped['unsatisfiable']} unsatisfiable)")
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