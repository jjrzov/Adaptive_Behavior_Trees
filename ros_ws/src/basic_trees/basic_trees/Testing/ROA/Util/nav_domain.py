'''
Navigation-style domain with small del sets, in contrast to the synthetic
generator's large ones. Interference is an explicit knob so the ROA gap can be
measured as a function of it rather than as a property of one domain.
'''
import random


DEFAULT_ROOMS = ["A", "B", "C", "D", "E", "F"]
DEFAULT_SAFE_EDGES = [("A", "B"), ("B", "C")]

# Triple-room style layout: B is the connecting hub
DEFAULT_EDGES = [("A", "B"), ("B", "C"), ("B", "D"), ("D", "E"), ("E", "F"), ("C", "F")]


def buildNavDomain(rooms=None, edges=None, key_room="E", box_room="F",
                   drop_room="A", interfere_p=0.0, rng=None, safe_edges=None):
    # Rooms are mutually exclusive; flags are carried state
    rooms = rooms or DEFAULT_ROOMS
    edges = edges or DEFAULT_EDGES
    rng = rng or random

    action_db = {}


    safe = {frozenset(e) for e in (safe_edges if safe_edges is not None
                                   else DEFAULT_SAFE_EDGES)}

    for x, y in edges:
        for src, dst in ((x, y), (y, x)):
            dels = {f"at_{src}"}

            if rng.random() < interfere_p:
                # Rough traversal: the robot drops what it is carrying
                dels.add(rng.choice(["has_key", "has_box"]))


                if frozenset((x, y)) not in safe and rng.random() < interfere_p:
                    dels.add(rng.choice(["has_key", "has_box"]))

            action_db[f"move_{src}_{dst}"] = {
                "pre": {f"at_{src}"},
                "add": {f"at_{dst}"},
                "del": dels,
                "cost": 1.0,
            }

    action_db["pickup_key"] = {
        "pre": {f"at_{key_room}"}, "add": {"has_key"}, "del": set(), "cost": 1.0}
    action_db["pickup_box"] = {
        "pre": {f"at_{box_room}"}, "add": {"has_box"}, "del": set(), "cost": 1.0}
    action_db["deliver_box"] = {
        "pre": {f"at_{drop_room}", "has_box"}, "add": {"box_delivered"},
        "del": {"has_box"}, "cost": 1.0}

    return action_db


def enumerateStates(init_state, action_db, cap=5000):
    # Exact reachable universe: no sampling, so the ROA denominator is exact
    start = frozenset(init_state)
    seen = {start}
    frontier = [start]

    actions = [(set(a["pre"]), set(a["add"]), set(a["del"])) for a in action_db.values()]

    while frontier and len(seen) < cap:
        state = frontier.pop(0)

        for pre, add, dele in actions:
            if not pre <= state:
                continue

            nxt = frozenset((state - dele) | add)
            if nxt not in seen:
                seen.add(nxt)
                frontier.append(nxt)

    return seen


def navLiterals(rooms=None):
    rooms = rooms or DEFAULT_ROOMS
    return [f"at_{r}" for r in rooms] + ["has_key", "has_box", "box_delivered"]