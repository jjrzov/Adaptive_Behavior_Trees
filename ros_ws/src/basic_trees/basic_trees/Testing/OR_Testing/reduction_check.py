import basic_trees.algorithms as alg
import basic_trees.Goals.goal_tree as OR_Trees
import basic_trees.Testing.test_tree as AND_Trees

from basic_trees.Testing.setup_tests import generateLiterals, generateSolution
from basic_trees.Goals.goal_types import OR, AND
from basic_trees.Testing.test_tree import getNodeCount


# Comparing paper's original generator and OR tree generator w/ n = 1 disjuncts
# as they should create the same trees


def reductionCheck(case, n_problems):
    sizes = []
    expansions = []
    
    alg.SUBSET_PRUNE = False
    alg.DEDUP_C_ATTR = False

    for _ in range(n_problems):
        # Generate initial state, action database, and state pool as base paper does
        all_literals = generateLiterals(case["literals"])
        states_db, action_db = generateSolution(all_literals, case["distance"], case["iterations"])
        goal = states_db[-1]

        plain_root, plain_exp, _ = AND_Trees.runTree(states_db[0].copy(), goal, action_db)

        disjunct_root, disjunct_exp, _ = OR_Trees.runTree(states_db[0].copy(), OR(AND(*goal)), action_db)

        if plain_root is not False and disjunct_root is not False:
            n_plain = getNodeCount(plain_root)
            n_disjunct = getNodeCount(disjunct_root)

            sizes.append((n_plain, n_disjunct))
            expansions.append((plain_exp, disjunct_exp))

            if len(sizes) % 500 == 0:
                print(f"  Case {case['case']}: {len(sizes)}/{n_problems} successes ")

    return sizes, expansions


def main():
    test_case = {"case": 1, "literals": 100, "distance": 100, "iterations": 10}
    print(f"literals = {test_case['literals']}, distance = {test_case['distance']}, iterations = {test_case['iterations']}")

    sizes, expansions = reductionCheck(test_case, 2000)

    # Tree sizes
    smaller = sum(1 for p, d in sizes if d < p)
    equal   = sum(1 for p, d in sizes if d == p)
    larger  = sum(1 for p, d in sizes if d > p)

    print(f"Tree Size Comparison")
    print(f"  disjunct smaller: {smaller}")
    print(f"  identical:        {equal}")
    print(f"  disjunct larger:  {larger}")

    diffs = [d - p for p, d in sizes]
    print(f"  mean diff: {sum(diffs)/len(diffs):.2f}")
    print(f"  range: {min(diffs)} to {max(diffs)}")
    print(f"  distinct diffs: {sorted(set(diffs))[:10]}")


    # Expansions
    smaller = sum(1 for p, d in expansions if d < p)
    equal   = sum(1 for p, d in expansions if d == p)
    larger  = sum(1 for p, d in expansions if d > p)

    print(f"Expansion Comparison")
    print(f"  disjunct smaller: {smaller}")
    print(f"  identical:        {equal}")
    print(f"  disjunct larger:  {larger}")

    diffs = [d - p for p, d in expansions]
    print(f"  mean diff: {sum(diffs)/len(diffs):.2f}")
    print(f"  range: {min(diffs)} to {max(diffs)}")
    print(f"  distinct diffs: {sorted(set(diffs))[:10]}")


if __name__ == '__main__':
    main()