# Compares the two readings of supplementary Step 2 for in-state literals:
#   "else"       - current implementation (pre XOR shot-at-del)
#   "sequential" - pre at 50%, then independently del at 50% (allows pre & del)

import random
import statistics

from basic_trees.Testing.setup_tests import generateLiterals
from basic_trees.Testing.test_tree import runTree, getNodeCount

TRIALS = 200
CASES = [
    (0, 10,  10, 10,    20.6),
    (1, 10,  10, 100,  103.9),
    (2, 10,  10, 1000, 607.5),
    (3, 100, 10, 10,    21.0),
    (4, 100, 10, 1000, 1011.0),
    (5, 10,  50, 10,    58.8),
    (6, 10,  50, 100,  138.1),
    (7, 10,  50, 1000, 621.0),
    (8, 100, 50, 10,    61.0),
    (9, 100, 50, 1000, 1051.0),
]


def generateActionVariant(literals, state, mode):
    pre, add, dels = set(), set(), set()
    for literal in literals:
        if literal in state:
            if mode == "else":
                if random.random() > 0.5:
                    pre.add(literal)
                elif random.random() > 0.5:
                    dels.add(literal)
            else:
                if random.random() > 0.5:
                    pre.add(literal)
                if random.random() > 0.5:
                    dels.add(literal)
        else:
            if random.random() > 0.5:
                add.add(literal)
            elif random.random() > 0.5:
                dels.add(literal)
    return {"pre": pre, "add": add, "del": dels}


def countDistinctStates(literals, distance, iterations, mode):
    curr = {l for l in literals if random.random() > 0.5}
    path = []
    for _ in range(distance):
        a = generateActionVariant(literals, curr, mode)
        path.append(curr)
        curr = curr.union(a["add"]) - a["del"]
    path.append(curr)

    pool = list(path)
    for _ in range(iterations):
        s = random.choice(pool)
        a = generateActionVariant(literals, s, mode)
        pool.append(s.union(a["add"]) - a["del"])

    return len({frozenset(s) for s in pool}), statistics.mean(len(s) for s in pool)


def main():
    print(f"{'case':>5} {'mode':>11} {'mine':>9} {'paper':>9} {'ratio':>7} {'avg_k':>7}")
    for case, lits, dist, iters, paper in CASES:
        literals = generateLiterals(lits)
        for mode in ("else", "sequential"):
            res = [countDistinctStates(literals, dist, iters, mode) for _ in range(TRIALS)]
            m = statistics.mean(r[0] for r in res)
            k = statistics.mean(r[1] for r in res)
            print(f"{case:>5} {mode:>11} {m:>9.1f} {paper:>9.1f} {m / paper:>7.2f} {k:>7.1f}")


if __name__ == '__main__':
    main()