'''
Disturbance experiment - execution-time ROA preservation.

The ROA results elsewhere are initial-state measures: build the tree, tick from
a pooled state, see whether it reaches the goal. This asks the other question a
behaviour tree is supposed to answer - once the goal has been reached, can the
tree re-achieve it after the world moves underneath it?

Each trial is settle -> inject -> recover, and the tree is NOT reset at
injection; a real tree would keep ticking, so we do too.

WHAT THIS ACTUALLY ESTABLISHES

Every composite in these trees is memory=False and TestAction returns SUCCESS
immediately, so a single tick_once() cascades an entire plan - from the initial
state the tree reaches the goal in one tick, executing all five actions. Node
status therefore carries nothing between ticks, and the tree's behaviour from
any state is a function of that state alone.

The consequence is that disturbance recovery is exactly ROA membership from the
disturbed state. That is not a null result: it means the static ROA numbers
already characterise disturbance robustness, and it is why the base paper can
claim robots are "guaranteed to work under any resolvable disturbances" without
a separate dynamic argument. Unified preserves that robustness at a fraction of
DNF's node count.

Two limits worth stating with the result:

  - ticks-to-recover is not a usable metric here; it is always 1. It becomes
    meaningful only once actions return RUNNING over several ticks, which is
    the Gazebo case, not the mock harness.
  - the cross-branch pruning ablation (arm "pruned", global expanded_literals
    and prune() instead of scopedPrune) does not discriminate in this domain.
    The branches have disjoint literal pools by construction - that is what
    makes the compactness experiment clean - so global pruning has almost
    nothing to remove. Testing the pruning claim needs a domain where branches
    genuinely share conditions: the navigation domain's shared room graph, or
    the synthetic generator.

The `gate` knob on the layered domain was added to try to force the pruning
failure here and does not achieve it; it is left in place, off by default,
because it is the right shape for that test in a shared-structure domain.
'''
import csv
import py_trees

from basic_trees.algorithms import expand, prune, goalScope, scopedPrune, expansionKey
from basic_trees.traverse import BFS, scopedBFS
from basic_trees.Goals.goal_types import AND, OR, GoalSelector
from basic_trees.Goals.goal_tree import buildBaseTree, fixpointBuilder, getAction, setupWorld
from basic_trees.Testing.ROA.Util.membership import goalSatisfied, treeStats
from basic_trees.Testing.ROA.Util.nav_domain import enumerateStates
from basic_trees.Testing.ROA.Util.layered_domain import buildLayeredDomain, layeredInit, layeredTargets, layeredDisjuncts, yLiteral


RECOVERED = "recovered"
STUCK = "stuck"
CYCLE = "cycle"
CAP = "cap"

FIELDS = ["arm", "trial", "inject", "gate_open", "outcome", "ticks",
          "disjunct_used", "false_success", "nodes"]

CHAIN_DEPTH = 3
BRANCH_DEPTH = 2
N_BRANCHES = 2
SETTLE_CAP = 60
RECOVER_CAP = 60
OUT = "disturbance_roa.csv"
GATE = False        # gate machinery kept for the pruning probe; off by default


def fixpointBuilderGlobal(goal_term, action_database, cap=400):
    # Ablation arm: mirrors fixpointBuilder but with one global record of
    # expanded literals and prune() instead of scopedPrune(), which is what
    # PRUNE_MODE = "global" does in runTree. Conditions are therefore shared
    # across GoalSelector branches rather than kept per scope.
    root = buildBaseTree(goal_term)

    expanded_literals = set()
    expansion_count = 0
    traverse = BFS()

    while (next_condition := traverse.getNextCondition(root, expanded_literals)) is not None:
        if expansion_count >= cap:
            raise RuntimeError("global fixpoint did not terminate")

        expanded_literals.add(expansionKey(next_condition))

        root = expand(root, next_condition, action_database, getAction)
        prune(root, expanded_literals)

        expansion_count += 1

    return root, expansion_count


def buildDNF(disjuncts, action_db):
    roots, expansions = [], 0

    for disjunct in disjuncts:
        root, count = fixpointBuilder(AND(*sorted(disjunct)), action_db)
        roots.append(root)
        expansions += count

    join = GoalSelector(name="DNF", memory=False)
    join.add_children(roots)

    return join, expansions


def tickUntilGoal(root, blackboard, goal_term, cap):
    # Shared tick loop. Does not touch node status, so it can be used both to
    # settle a fresh tree and to continue a running one after a disturbance.
    prev_state = frozenset(blackboard.world_state)
    seen = {prev_state}

    false_success = 0
    ticks = 0

    while ticks < cap:
        root.tick_once()
        ticks += 1

        current_state = frozenset(blackboard.world_state)
        status = root.status
        satisfied = goalSatisfied(goal_term, current_state)

        if status == py_trees.common.Status.SUCCESS and satisfied:
            return RECOVERED, ticks, false_success

        if status == py_trees.common.Status.SUCCESS:
            false_success += 1

        if current_state == prev_state:
            return STUCK, ticks, false_success

        if current_state in seen:
            return CYCLE, ticks, false_success

        prev_state = current_state
        seen.add(current_state)

    return CAP, ticks, false_success


def disjunctUsed(state, branch_targets):
    # Which disjunct is satisfied in the final state, if any
    for index, target in enumerate(branch_targets):
        if target <= set(state):
            return index

    return None


def runTrial(root, init_state, inject_state, goal_term, blackboard,
             branch_targets):
    # settle -> inject -> recover
    setupWorld(blackboard, set(init_state))

    for node in root.iterate():
        node.stop(py_trees.common.Status.INVALID)

    settled, _, _ = tickUntilGoal(root, blackboard, goal_term, SETTLE_CAP)

    if settled != RECOVERED:
        return None             # never reached the goal; not a valid trial

    # The world moves. The tree keeps its node status - no reset.
    setupWorld(blackboard, set(inject_state))

    outcome, ticks, false_success = tickUntilGoal(root, blackboard, goal_term, RECOVER_CAP)

    return {
        "outcome": outcome,
        "ticks": ticks,
        "false_success": false_success,
        "disjunct_used": disjunctUsed(blackboard.world_state, branch_targets),
    }


def buildProblem(gate=True, gate_branch=0):
    action_db = buildLayeredDomain(
        chain_depth=CHAIN_DEPTH, branch_depth=BRANCH_DEPTH,
        n_branches=N_BRANCHES, coupling_p=0.0,
        x_reversible=True, y_reversible=False, gate=gate,
        gate_branch=gate_branch)

    init_state = layeredInit(CHAIN_DEPTH, gate=gate)
    shared, branches = layeredTargets(CHAIN_DEPTH, BRANCH_DEPTH, N_BRANCHES)
    goal_term = AND(*sorted(shared), OR(*[AND(*sorted(b)) for b in branches]))

    return action_db, init_state, goal_term, shared, branches


def disturbanceStates(init_state, action_db, goal_term, gate):
    # Exhaustive, not sampled: every reachable state, plus its gate-cleared
    # variant, minus the states where the goal already holds.
    reachable = enumerateStates(init_state, action_db)

    targets = set(reachable)
    if gate:
        targets |= {frozenset(s - {"gate"}) for s in reachable}

    return sorted((t for t in targets if not goalSatisfied(goal_term, t)),
                  key=lambda s: sorted(s))


def main():
    gate = GATE
    action_db, init_state, goal_term, shared, branches = buildProblem(gate)

    arms = {}
    arms["unified"], u_exp = fixpointBuilder(goal_term, action_db)
    arms["pruned"], p_exp = fixpointBuilderGlobal(goal_term, action_db)
    arms["dnf"], d_exp = buildDNF(
        layeredDisjuncts(CHAIN_DEPTH, BRANCH_DEPTH, N_BRANCHES), action_db)

    injects = disturbanceStates(init_state, action_db, goal_term, gate)

    print(f"goal        : AND(x_{CHAIN_DEPTH}, OR(y0_{BRANCH_DEPTH}, "
          f"y1_{BRANCH_DEPTH}))" + ("   gate on branch 0" if GATE else ""))
    print(f"init        : {sorted(init_state)}")
    print(f"disturbances: {len(injects)} (exhaustive)")
    print(f"expansions  : unified={u_exp}  pruned={p_exp}  dnf={d_exp}")
    print(f"nodes       : " + "  ".join(
        f"{name}={treeStats(root)['nodes']}" for name, root in arms.items()))

    rows = []
    summary = {}

    for name, root in arms.items():
        blackboard = py_trees.blackboard.Client(name=f"DIST_{name}")
        counts = {RECOVERED: 0, STUCK: 0, CYCLE: 0, CAP: 0}
        used = {index: 0 for index in range(N_BRANCHES)}
        used[None] = 0
        skipped = 0

        for index, inject in enumerate(injects):
            result = runTrial(root, init_state, inject, goal_term, blackboard, branches)

            if result is None:
                skipped += 1
                continue

            counts[result["outcome"]] += 1
            used[result["disjunct_used"]] += 1

            rows.append({
                "arm": name,
                "trial": index,
                "inject": " ".join(sorted(inject)),
                "gate_open": "gate" in inject,
                "outcome": result["outcome"],
                "ticks": result["ticks"],
                "disjunct_used": result["disjunct_used"],
                "false_success": result["false_success"],
                "nodes": treeStats(root)["nodes"],
            })

        summary[name] = (counts, used, skipped)

    print(f"\n{'arm':>9} {'recovered':>10} {'stuck':>6} {'cycle':>6} "
          f"{'cap':>5} {'via d0':>7} {'via d1':>7}")
    for name, (counts, used, _) in summary.items():
        total = sum(counts.values())
        print(f"{name:>9} {counts[RECOVERED]:>4}/{total:<5} "
              f"{counts[STUCK]:>6} {counts[CYCLE]:>6} {counts[CAP]:>5} "
              f"{used[0]:>7} {used[1]:>7}")

    if GATE:
        # Only meaningful when the gate can close a branch
        print(f"\ngate cleared (the gated branch is unavailable):")
        for name in arms:
            closed = [r for r in rows if r["arm"] == name
                      and not r["gate_open"]]
            ok = sum(1 for r in closed if r["outcome"] == RECOVERED)
            print(f"{name:>9} {ok:>5}/{len(closed):<6}")

    with open(OUT, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nwrote {len(rows)} rows to {OUT}")


if __name__ == '__main__':
    main()