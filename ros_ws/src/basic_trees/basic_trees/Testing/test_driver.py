# Sweeps the 10 Table 2 test-set configurations and records BT expansion
# tree-size statistics (avg/std) for comparison against the paper's reported values.
# Also tracks average prune-node counts per case, to help diagnose whether
# stale/redundant condition subtrees are accumulating across expansions.

import statistics

from basic_trees.Testing.setup_tests import generateLiterals, generateSolution
from basic_trees.Testing.test_tree import runTree, getNodeCount

TARGET_SUCCESSES = 1000

# (literals, distance, iterations) triples, matching Table 2, cases 0-9
TEST_CASES = [
    {"case": 0, "literals": 10, "distance": 10, "iterations": 10},
    {"case": 1, "literals": 10, "distance": 10, "iterations": 100},
    {"case": 2, "literals": 10, "distance": 10, "iterations": 1000},
    {"case": 3, "literals": 100, "distance": 10, "iterations": 10},
    {"case": 4, "literals": 100, "distance": 10, "iterations": 1000},
    {"case": 5, "literals": 10, "distance": 50, "iterations": 10},
    {"case": 6, "literals": 10, "distance": 50, "iterations": 100},
    {"case": 7, "literals": 10, "distance": 50, "iterations": 1000},
    {"case": 8, "literals": 100, "distance": 50, "iterations": 10},
    {"case": 9, "literals": 100, "distance": 50, "iterations": 1000},
]


def runCase(case):
    sizes = []
    prune_counts = []
    duplicate_counts = []
    max_condition_sizes = []
    mean_branching_factors = []
    failures = 0
 
    while len(sizes) < TARGET_SUCCESSES:
        all_literals = generateLiterals(case["literals"])
        states_database, action_database = generateSolution(
            all_literals, case["distance"], case["iterations"]
        )
 
        root = runTree(states_database[0].copy(), states_database[-1], action_database)
 
        if root is False:
            failures += 1
            continue
 
        sizes.append(getNodeCount(root))
        prune_counts.append(getattr(root, "total_prunes", 0))
        duplicate_counts.append(getattr(root, "total_duplicates", 0))
 
        condition_sizes = getattr(root, "condition_size_trace", [])
        branching = getattr(root, "branching_trace", [])
        if condition_sizes:
            max_condition_sizes.append(max(condition_sizes))
        if branching:
            mean_branching_factors.append(statistics.mean(branching))
 
        if len(sizes) % 500 == 0:
            print(f"  Case {case['case']}: {len(sizes)}/{TARGET_SUCCESSES} successes "
                  f"({failures} failures so far)")
 
    return {
        "case": case["case"],
        "literals": case["literals"],
        "distance": case["distance"],
        "iterations": case["iterations"],
        "avg_tree_size": statistics.mean(sizes),
        "std_tree_size": statistics.stdev(sizes),
        "avg_prunes": statistics.mean(prune_counts),
        "std_prunes": statistics.stdev(prune_counts),
        "avg_duplicates": statistics.mean(duplicate_counts),
        "std_duplicates": statistics.stdev(duplicate_counts),
        "avg_max_condition_size": statistics.mean(max_condition_sizes) if max_condition_sizes else 0,
        "avg_mean_branching": statistics.mean(mean_branching_factors) if mean_branching_factors else 0,
        "failures": failures,
        "sizes": sizes,          # raw per-trial sizes, kept for later inspection if needed
        "prune_counts": prune_counts,  # raw per-trial prune counts, same reason
        "duplicate_counts": duplicate_counts,  # raw per-trial duplicate counts, same reason
    }
 
 
def runAllCases():
    results = []
 
    for case in TEST_CASES:
        result = runCase(case)
        results.append(result)
        print(
            f"Case {result['case']}: "
            f"avg_size={result['avg_tree_size']:.1f}, "
            f"std_size={result['std_tree_size']:.1f}, "
            f"avg_prunes={result['avg_prunes']:.1f}, "
            f"std_prunes={result['std_prunes']:.1f}, "
            f"avg_dupes={result['avg_duplicates']:.1f}, "
            f"std_dupes={result['std_duplicates']:.1f}, "
            f"avg_max_cset={result['avg_max_condition_size']:.1f}, "
            f"avg_branching={result['avg_mean_branching']:.2f}, "
            f"failures={result['failures']}"
        )
 
    return results

def main():
    results = runAllCases()
    return results


if __name__ == '__main__':
    main()