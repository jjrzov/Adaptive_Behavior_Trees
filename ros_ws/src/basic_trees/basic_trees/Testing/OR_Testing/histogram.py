import random
import math
import matplotlib.pyplot as plt
from collections import Counter

from basic_trees.Testing.setup_tests import generateLiterals, generateSolution

TARGET_SUCCESSES = 500


def recordData(case):
    invalid = 0 # Count for amount of times a valid state cannot be found
    infs = 0
    runs = []  # Run for 500 trees


    while len(runs) < TARGET_SUCCESSES:
        all_literals = generateLiterals(case["literals"])
        states_database, action_database = generateSolution(
            all_literals, case["distance"], case["iterations"]
        )
 
        # Record data
        sample = getDisjunctSets(states_database, action_database)
        if (sample == None):
            invalid += 1
            continue

        d1, d2 = sample
        if d1 == math.inf or d2 == math.inf:
            infs += 1
        else:
            hi, lo = max(d1, d2), min(d1, d2)
            runs.append({"min": lo, "max": hi, "spread": hi - lo, "ratio": (hi - lo) / hi})

        # if len(runs) % 50 == 0:
        #     print(f"   Case {case['case']}: {len(runs)}/{TARGET_SUCCESSES} successes")

    return runs, invalid, infs


def getRandomSubset(state):
    subset = set()

    for literal in state:
        if random.random() > 0.25:
            subset.add(literal)

    return subset


def distToSubset(states_database, action_database, disjunct):
    depth = 0

    q = [(states_database[0], depth)]  # Initialize queue
    visited = {frozenset(states_database[0])}
    states_pool = {frozenset(s) for s in states_database}

    while (len(q) != 0):
        # Keep searching until empty
        state, depth = q.pop(0)
        if disjunct.issubset(state):
            return depth

        for _, ops in action_database.items():
            if ops["pre"].issubset(state):
                # action is possible because the state has its preconditions
                next_state = frozenset(state.union(ops["add"]) - ops["del"])   # Calulate possible next state

                if (next_state not in visited) and (next_state in states_pool):
                    # Possible next state hasn't been explored and is in the state pool
                    visited.add(next_state)
                    q.append((next_state, depth + 1))

    return math.inf # No valid state found


def getDisjunctSets(states_database, action_database):
    # Pick 2 random and distinct states
    max_attempts = 50

    for _ in range(max_attempts):
        s1 = set(random.choice(states_database))
        s2 = set(random.choice(states_database))

        if (s2 == s1):
            continue

        # Get a random subset of both
        d1 = getRandomSubset(s1)                        
        d2 = getRandomSubset(s2)

        if (d1.issubset(states_database[0]) or d2.issubset(states_database[0]) 
                or (d1.issubset(d2) or d2.issubset(d1))):
            continue

        # Caluclate distance from a state containing the disjuct set and the root
        d1 = distToSubset(states_database, action_database, d1)
        d2 = distToSubset(states_database, action_database, d2)

        return (d1, d2)

    return None


def plotSpread(runs, case):
    spreads = [r["spread"] for r in runs]

    counts = Counter(spreads)
    print(f"n = {len(spreads)}")
    for s in sorted(counts):
        print(f"  spread {s:>3}: {counts[s]:>4}  ({counts[s]/len(spreads):.1%})")

    fig, ax = plt.subplots(figsize=(8, 5))
    bins = range(0, max(spreads) + 2)
    ax.hist(spreads, bins=bins, align="left", edgecolor="black")
    ax.set_xlabel("spread (max disjunct distance − min)")
    ax.set_ylabel("problems")
    ax.set_title(
        f"Disjunct distance spread — literals={case['literals']}, "
        f"distance={case['distance']}, iterations={case['iterations']}"
    )
    ax.set_xticks(list(bins)[:-1])
    fig.tight_layout()
    fig.savefig("spread_histogram.png", dpi=150)
    plt.close(fig)


def main():
    test_case = {"case": 1, "literals": 100, "distance": 50, "iterations": 10}

    runs, invalid, infs = recordData(test_case)

    print(f"literals = {test_case['literals']}, distance = {test_case['distance']}, iterations = {test_case['iterations']}")

    plotSpread(runs, test_case)

    buckets = [(1, 10), (11, 20), (21, 30), (31, 999)]
    print("\n  spread bucket |   n | min: mean (range)")
    for lo, hi in buckets:
        sel = [r["min"] for r in runs if lo <= r["spread"] <= hi]
        if sel:
            print(f"  {lo:>3}-{hi:<3}      | {len(sel):>3} | {sum(sel)/len(sel):>5.1f} ({min(sel)}-{max(sel)})")


    ratio_buckets = [(0.0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 1.01)]
    print("\n  ratio bucket |   n | min: mean (range)")
    for lo, hi in ratio_buckets:
        sel = [r["min"] for r in runs if lo <= r["ratio"] < hi]
        if sel:
            print(f"  {lo:.2f}-{hi:.2f}   | {len(sel):>3} | {sum(sel)/len(sel):>5.1f} ({min(sel)}-{max(sel)})")

    print(f"invalid: {invalid}")
    print(f"infinites: {infs}")



if __name__ == '__main__':
    main()