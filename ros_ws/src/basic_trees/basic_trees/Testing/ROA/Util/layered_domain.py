'''
Domain-neutral generator for the compactness experiment.

Two disjoint literal pools with no shared literals:

  X : a linear chain  x_0 -> x_1 -> ... -> x_d     (the shared conjunct)
  Y : k linear chains y_start -> y{b}_1 -> ... -> y{b}_m   (the disjuncts)

Goal:     AND(x_d, OR(y0_m, y1_m, ...))
DNF:      [{x_d, y0_m}, {x_d, y1_m}, ...]

The DNF arm regresses each conjunction jointly, so the whole X chain is
duplicated inside every disjunct tree; the unified arm expands it once. The
node ratio is therefore a function of chain_depth, which is the knob.

Coupling (a Y action also deleting an X literal) is the interference axis and
defaults to zero. At coupling_p = 0 no action deletes a literal outside its own
pool, so sibling subtrees provably cannot interfere: every arm is sound and the
protect guard is inert. Experiment 2 is run only at coupling_p = 0; the knob
exists so the same generator can serve the soundness experiment later.

Chain steps delete their predecessor, so each pool's literals are mutually
exclusive and the reachable universe stays small enough to enumerate exactly:
|S| = (chain_depth + 1) * (1 + k * branch_depth).
'''
import random


def xLiteral(i):
    return f"x_{i}"


def yLiteral(branch, j):
    return "y_start" if j == 0 else f"y{branch}_{j}"


def buildLayeredDomain(chain_depth=3, branch_depth=2, n_branches=2,
                       coupling_p=0.0, reversible=True, rng=None, cost=1.0,
                       x_reversible=None, y_reversible=None, gate=False,
                       gate_branch=0):
    # Two independent subsystems; coupling_p is the only way they interact.
    #
    # x_reversible / y_reversible override `reversible` per subsystem and
    # default to it, so existing callers are unaffected. The disturbance
    # experiment wants x reversible (knock the robot back, let it re-climb)
    # and y one-way (committing to a branch is a real commitment, so which
    # branch the tree can still reach actually matters).
    #
    # gate=True puts a `gate` literal on the entry of branch `gate_branch`. No action adds it,
    # so a disturbance that clears it closes branch 0 permanently and leaves
    # branch 1 as the only completion. That is the state which separates a
    # tree that kept both branches from one that pruned across them.
    rng = rng or random

    x_rev = reversible if x_reversible is None else x_reversible
    y_rev = reversible if y_reversible is None else y_reversible

    action_db = {}
    x_literals = [xLiteral(i) for i in range(chain_depth + 1)]

    def coupledDels(base):
        # A Y action may also drop an X literal - this is the interference axis
        dels = set(base)

        if coupling_p > 0.0 and chain_depth > 0 and rng.random() < coupling_p:
            dels.add(rng.choice(x_literals))

        return dels

    # X chain: shared conjunct, expanded once by unified and k times by DNF
    for i in range(1, chain_depth + 1):
        action_db[f"x_step_{i}"] = {
            "pre": {xLiteral(i - 1)},
            "add": {xLiteral(i)},
            "del": {xLiteral(i - 1)},
            "cost": cost,
        }

        if x_rev:
            action_db[f"x_back_{i}"] = {
                "pre": {xLiteral(i)},
                "add": {xLiteral(i - 1)},
                "del": {xLiteral(i)},
                "cost": cost,
            }

    # Y branches: one chain per disjunct, all leaving from y_start
    for b in range(n_branches):
        for j in range(1, branch_depth + 1):
            pre = {yLiteral(b, j - 1)}

            if gate and b == gate_branch and j == 1:
                pre = pre | {"gate"}

            action_db[f"y{b}_step_{j}"] = {
                "pre": pre,
                "add": {yLiteral(b, j)},
                "del": coupledDels({yLiteral(b, j - 1)}),
                "cost": cost,
            }

            if y_rev:
                action_db[f"y{b}_back_{j}"] = {
                    "pre": {yLiteral(b, j)},
                    "add": {yLiteral(b, j - 1)},
                    "del": coupledDels({yLiteral(b, j)}),
                    "cost": cost,
                }

    return action_db


def layeredInit(chain_depth=3, gate=False):
    # Start at the foot of both subsystems
    init = {xLiteral(0), "y_start"}

    if gate:
        init.add("gate")

    return init


def layeredTargets(chain_depth=3, branch_depth=2, n_branches=2):
    # Shared conjunct and one target literal per disjunct
    shared = {xLiteral(chain_depth)}
    branches = [{yLiteral(b, branch_depth)} for b in range(n_branches)]

    return shared, branches


def layeredDisjuncts(chain_depth=3, branch_depth=2, n_branches=2):
    # The DNF arm's conjunctions: shared duplicated into every disjunct
    shared, branches = layeredTargets(chain_depth, branch_depth, n_branches)

    return [shared | branch for branch in branches]


# Observed scaling, reversible=False, measured not predicted.
#
# Both arms are linear in every knob; the ratio is the ratio of slopes and
# saturates rather than growing without bound:
#
#   nodes_unified ~ 24 + 4*chain_depth      (X chain expanded once)
#   nodes_dnf     ~ 21 + 24*chain_depth     (X chain expanded once per disjunct,
#                                            with joint regression producing
#                                            cross-product condition sets)
#
# A naive duplication argument predicts the ratio tends to n_branches. The
# measured slope ratio is ~6 at n_branches = 2, so duplication alone
# understates it: DNF's joint conditions {x_i, y_j} form a product where the
# unified arm's form a sum. Report the measured curve, not the naive bound.
#
# reversible=True makes both arms quadratic in n_branches, because every
# branch's regression passes through y_start and admits every other branch's
# reverse action. Use reversible=False for the scaling claim and
# reversible=True for disturbance recovery, where going back matters.