# Testing/test_states.py — validates generated state count against Table 2

import statistics
from basic_trees.Testing.setup_tests import generateLiterals, generateAction
import random

TRIALS = 200
CASES = [
    (0, 10, 10, 10, 20.6), (1, 10, 10, 100, 103.9), (2, 10, 10, 1000, 607.5),
    (3, 100, 10, 10, 21.0), (4, 100, 10, 1000, 1011.0),
    (5, 10, 50, 10, 58.8), (6, 10, 50, 100, 138.1), (7, 10, 50, 1000, 621.0),
    (8, 100, 50, 10, 61.0), (9, 100, 50, 1000, 1051.0),
]


def countDistinctStates(literals, distance, iterations):
    curr = {l for l in literals if random.random() > 0.5}
    path = []
    for _ in range(distance):
        a = generateAction(literals, curr)
        path.append(curr)
        curr = curr.union(a["add"]) - a["del"]
    path.append(curr)

    pool = list(path)
    for _ in range(iterations):
        s = random.choice(pool)
        a = generateAction(literals, s)
        pool.append(s.union(a["add"]) - a["del"])

    return len({frozenset(s) for s in pool})


def main():
    print(f"{'case':>5} {'mine':>9} {'paper':>9} {'ratio':>7}")
    for case, lits, dist, iters, paper in CASES:
        literals = generateLiterals(lits)
        counts = [countDistinctStates(literals, dist, iters) for _ in range(TRIALS)]
        m = statistics.mean(counts)
        print(f"{case:>5} {m:>9.1f} {paper:>9.1f} {m / paper:>7.2f}")


if __name__ == '__main__':
    main()