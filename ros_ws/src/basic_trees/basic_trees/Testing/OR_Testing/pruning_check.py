import basic_trees.algorithms as alg

from basic_trees.Testing.setup_tests import generateLiterals, generateSolution
from basic_trees.Goals.goal_tree import runTree
from basic_trees.Testing.OR_Testing.histogram import getDisjunctSets
from basic_trees.Goals.goal_types import OR, AND
from basic_trees.Testing.test_tree import getNodeCount


# This file checks to make sure subset pruning does not take away completeness
# by removing necessary conditions / subtrees

def pruningCheck(case, n_problems):
    counterexamples = []
    sizes = []

    for _ in range(n_problems):
        all_literals = generateLiterals(case["literals"])
        states_db, action_db = generateSolution(all_literals, case["distance"], case["iterations"])

        sample = getDisjunctSets(states_db, action_db)
        if sample is None:
            continue
        d1, d2, _, _ = sample   # Keep the literal sets, not the distances

        alg.SUBSET_PRUNE = False
        exact, _, _= runTree(states_db[0], OR(AND(*d1), AND(*d2)), action_db)

        alg.SUBSET_PRUNE = True
        subset, _, _ = runTree(states_db[0], OR(AND(*d1), AND(*d2)), action_db)

        if exact is not False and subset is not False:
            n_exact = getNodeCount(exact)
            n_subset = getNodeCount(subset)
            sizes.append((n_exact, n_subset))

            if len(sizes) % 500 == 0:
                print(f"  Case {case['case']}: {len(sizes)}/{n_problems} successes ")

    return counterexamples, sizes


def main():
    test_case = {"case": 1, "literals": 100, "distance": 100, "iterations": 10}

    print(f"literals = {test_case['literals']}, distance = {test_case['distance']}, iterations = {test_case['iterations']}")

    counterexamples, sizes = pruningCheck(test_case, 2000)
    print(f"counterexamples: {len(counterexamples)}")

    smaller = sum(1 for e, s in sizes if s < e)
    equal   = sum(1 for e, s in sizes if s == e)
    larger  = sum(1 for e, s in sizes if s > e)

    print(f"compared: {len(sizes)}")
    print(f"  subset smaller: {smaller}")
    print(f"  identical:      {equal}")
    print(f"  subset larger:  {larger}")

    reductions = [(e - s) / e * 100 for e, s in sizes]
    print(f"  mean reduction: {sum(reductions)/len(reductions):.1f}%")
    print(f"  range: {min(reductions):.1f}% - {max(reductions):.1f}%")

if __name__ == '__main__':
    main()