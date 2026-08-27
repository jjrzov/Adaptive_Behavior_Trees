import basic_trees.algorithms as alg

from basic_trees.Testing.setup_tests import generateLiterals, generateSolution
from basic_trees.Goals.goal_tree import runTree
from basic_trees.Testing.OR_Testing.histogram import getDisjunctSets
from basic_trees.Goals.goal_types import OR, AND


def pruningCheck(case, n_problems):
    counterexamples = []
    for _ in range(n_problems):
        all_literals = generateLiterals(case["literals"])
        states_db, action_db = generateSolution(all_literals, case["distance"], case["iterations"])

        sample = getDisjunctSets(states_db, action_db)
        if sample is None:
            continue
        d1, d2 = sample   # the literal sets, not the distances

        alg.SUBSET_PRUNE = False
        alg.expansion_counter = 0
        exact = runTree(states_db[0], OR(AND(*d1), AND(*d2)), action_db)

        alg.SUBSET_PRUNE = True
        alg.expansion_counter = 0
        subset = runTree(states_db[0], OR(AND(*d1), AND(*d2)), action_db)

        if exact is not False and subset is False:
            counterexamples.append({"s0": states_db[0], "actions": action_db, "d1": d1, "d2": d2})

    return counterexamples


def main():
    test_case = {"case": 1, "literals": 100, "distance": 100, "iterations": 10}

    print(f"literals = {test_case['literals']}, distance = {test_case['distance']}, iterations = {test_case['iterations']}")

    counterexamples = pruningCheck(test_case, 2000)
    print(f"counterexamples: {len(counterexamples)}")

if __name__ == '__main__':
    main()