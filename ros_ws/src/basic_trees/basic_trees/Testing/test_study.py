# Replicates the mobile manipulator case study (Table 1 / Fig. S1)
# to validate expand() against a known-correct expected tree.

import py_trees

from basic_trees.Testing.test_tree import runTree, getNodeCount

ACTIONS = {
    "Move(b,ab)": {
        "pre": {"Free(ab)", "WayClear"},
        "add": {"At(b,ab)"},
        "del": {"Free(ab)", "At(b,pb)"},
    },
    "Move(s,ab)": {
        "pre": {"Free(ab)"},
        "add": {"At(s,ab)", "WayClear"},
        "del": {"Free(ab)", "At(s,ps)"},
    },
    "Move(s,as)": {
        "pre": {"Free(as)"},
        "add": {"At(s,as)", "WayClear"},
        "del": {"Free(as)", "At(s,ps)"},
    },
}

INIT_STATE = {"At(b,pb)", "At(s,ps)", "Free(ab)", "Free(as)"}  # WayClear false: s blocks
GOAL_STATE = {"At(b,ab)"}


def main():
    root = runTree(INIT_STATE.copy(), GOAL_STATE, ACTIONS)

    if root is False:
        print("FAIL: reported unsolvable, but Fig. S1 shows a solution")
        return

    print(py_trees.display.unicode_tree(root))
    print(f"nodes      = {getNodeCount(root)}")
    print(f"expansions = {getattr(root, 'expansion_count', '?')}")

    names = []
    q = [root]
    while q:
        n = q.pop(0)
        names.append(n.name)
        if isinstance(n, py_trees.composites.Composite):
            q.extend(n.children)

    conflict = any("Move(s,ab)" in n for n in names)
    print(f"Move(s,ab) present = {conflict}   (expected False)")


if __name__ == '__main__':
    main()