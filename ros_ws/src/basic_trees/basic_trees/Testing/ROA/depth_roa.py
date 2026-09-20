'''
Experiment 2 - compactness.

Sweeps the structural knobs of the layered domain at zero coupling and
compares the unified tree against the DNF baseline on ROA and size.

Zero coupling means no action deletes a literal outside its own pool, so
sibling subtrees cannot interfere. Every arm is sound by construction and the
protect guard is inert, which is what isolates this experiment from the
soundness question: any ROA difference here would be a bug, not a result.

The domain is deterministic given (chain_depth, branch_depth, n_branches), so
there is nothing to average over - each grid cell is run once and the sweep is
a curve, not a sample. Set JITTER to add randomised per-branch chain lengths if
a reviewer wants variation rather than a clean analytic curve.
'''
import csv
import py_trees

from basic_trees.Goals.goal_types import AND, OR, GoalSelector
from basic_trees.Goals.goal_tree import fixpointBuilder
from basic_trees.Testing.ROA.Util.membership import sweep, treeStats
from basic_trees.Testing.ROA.Util.nav_domain import enumerateStates
from basic_trees.Testing.ROA.Util.layered_domain import (
    buildLayeredDomain, layeredInit, layeredTargets, layeredDisjuncts)


FIELDS = ["axis", "chain_depth", "branch_depth", "n_branches", "reversible",
          "pool_size", "u_nodes", "d_nodes", "node_ratio",
          "u_conditions", "d_conditions", "u_unique", "d_unique",
          "u_expansions", "d_expansions", "expansion_ratio",
          "both", "unified_only", "dnf_only", "neither",
          "u_false_success", "d_false_success"]

CAP = 100
REVERSIBLE = False      # False for the scaling claim, True for disturbance reuse
OUT = "depth_roa.csv"

# One axis varies per sweep; the others hold at these values
BASE = {"chain_depth": 3, "branch_depth": 2, "n_branches": 2}

SWEEPS = {
    "chain_depth": [0, 1, 2, 3, 4, 5, 6, 8, 10],
    "branch_depth": [1, 2, 3, 4, 5],
    "n_branches": [2, 3, 4, 5, 6],
}


def buildArms(chain_depth, branch_depth, n_branches, reversible):
    # Unified: one tree from the nested goal. DNF: one fixpoint tree per
    # disjunct, joined under a fallback only so the sweep can tick it.
    action_db = buildLayeredDomain(chain_depth=chain_depth,
                                   branch_depth=branch_depth,
                                   n_branches=n_branches,
                                   coupling_p=0.0,
                                   reversible=reversible)

    shared, branches = layeredTargets(chain_depth, branch_depth, n_branches)
    goal_term = AND(*sorted(shared),
                    OR(*[AND(*sorted(b)) for b in branches]))

    unified_root, u_expansions = fixpointBuilder(goal_term, action_db)

    roots, d_expansions = [], 0
    for disjunct in layeredDisjuncts(chain_depth, branch_depth, n_branches):
        root, count = fixpointBuilder(AND(*sorted(disjunct)), action_db)
        roots.append(root)
        d_expansions += count

    dnf_root = GoalSelector(name="DNF", memory=False)
    dnf_root.add_children(roots)

    pool = enumerateStates(layeredInit(chain_depth), action_db)

    return goal_term, unified_root, dnf_root, pool, u_expansions, d_expansions


def runCell(axis, chain_depth, branch_depth, n_branches, reversible):
    goal_term, u_root, d_root, pool, u_exp, d_exp = buildArms(
        chain_depth, branch_depth, n_branches, reversible)

    blackboard = py_trees.blackboard.Client(
        name=f"ROA_{axis}_{chain_depth}_{branch_depth}_{n_branches}")

    buckets, _, false_success, _ = sweep(
        pool, u_root, d_root, goal_term, blackboard, cap=CAP)

    u_stats, d_stats = treeStats(u_root), treeStats(d_root)

    return {
        "axis": axis,
        "chain_depth": chain_depth,
        "branch_depth": branch_depth,
        "n_branches": n_branches,
        "reversible": reversible,
        "pool_size": len(pool),
        "u_nodes": u_stats["nodes"],
        "d_nodes": d_stats["nodes"],
        "node_ratio": round(d_stats["nodes"] / u_stats["nodes"], 4),
        "u_conditions": u_stats["condition_nodes"],
        "d_conditions": d_stats["condition_nodes"],
        "u_unique": u_stats["unique_conditions"],
        "d_unique": d_stats["unique_conditions"],
        "u_expansions": u_exp,
        "d_expansions": d_exp,
        "expansion_ratio": round(d_exp / u_exp, 4) if u_exp else 0.0,
        "both": buckets["both"],
        "unified_only": buckets["unified_only"],
        "dnf_only": buckets["dnf_only"],
        "neither": buckets["neither"],
        "u_false_success": false_success["unified"],
        "d_false_success": false_success["dnf"],
    }


def main():
    rows = []

    for axis, values in SWEEPS.items():
        print(f"\n--- {axis} ---")
        print(f"{axis:>13} {'|S|':>5} {'u_n':>5} {'d_n':>5} {'ratio':>6} "
              f"{'u_exp':>6} {'d_exp':>6} {'exp_r':>6} {'ROA':>9} {'fs':>3}")

        for value in values:
            params = dict(BASE)
            params[axis] = value

            row = runCell(axis, params["chain_depth"], params["branch_depth"],
                          params["n_branches"], REVERSIBLE)
            rows.append(row)

            roa = f"{row['both']}/{row['pool_size']}"
            flag = "" if row["both"] == row["pool_size"] else "  <-- CHECK"

            print(f"{value:>13} {row['pool_size']:>5} {row['u_nodes']:>5} "
                  f"{row['d_nodes']:>5} {row['node_ratio']:>6.2f} "
                  f"{row['u_expansions']:>6} {row['d_expansions']:>6} "
                  f"{row['expansion_ratio']:>6.2f} {roa:>9} "
                  f"{row['u_false_success']:>3}{flag}")

    with open(OUT, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    # At zero coupling every arm is sound, so these must all be clean
    bad = [r for r in rows if r["both"] != r["pool_size"]
           or r["u_false_success"] or r["d_false_success"]]

    print(f"\nwrote {len(rows)} rows to {OUT}")
    print("ROA identical on every cell, no false successes"
          if not bad else f"VALIDITY FAILURE on {len(bad)} cells")


if __name__ == '__main__':
    main()