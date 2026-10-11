import csv

import py_trees

from basic_trees.Conditions.condition import Condition


RUNNING = py_trees.common.Status.RUNNING
SUCCESS = py_trees.common.Status.SUCCESS
FAILURE = py_trees.common.Status.FAILURE
INVALID = py_trees.common.Status.INVALID


class TickLogger:
    '''
    Records when things happen during a run, in the node's clock.

    Call after_tick() once after every tree.tick() and expansion() for every
    condition the runner expands. Events are written to a CSV with one row per
    event. Times are seconds since the first tick.

        start      an action went to RUNNING
        success    an action finished with SUCCESS
        failure    an action finished with FAILURE
        halted     a RUNNING action was stopped by its parent (preempted)
        expand     the runner expanded a condition
        state      the world state changed (detail is the new state)
        goal       the goal started or stopped holding (detail is held or lost)

    Run the node on sim time so the times match Gazebo
        ros2 run basic_trees sim --ros-args -p use_sim_time:=true
    '''

    FIELDS = ["time_s", "tick", "event", "node", "detail"]

    def __init__(self, node, out_path="sim_timing.csv"):
        self.node = node
        self.out_path = out_path

        self.t0 = None
        self.tick_count = 0
        self.previous = {}          # id(behaviour) -> status after the previous tick
        self.last_state = None
        self.last_goal = None
        self.rows = []

        if not self._usesSimTime():
            self.node.get_logger().warn(
                "TickLogger is on wall time. Run with -p use_sim_time:=true for sim time.")


    def _usesSimTime(self):
        try:
            return bool(self.node.get_parameter("use_sim_time").value)
        except Exception:
            return False


    def _now(self):
        now = self.node.get_clock().now().nanoseconds * 1e-9
        if self.t0 is None:
            self.t0 = now
        return now - self.t0


    def _record(self, event, name="", detail=""):
        self.rows.append({"time_s": round(self._now(), 3), "tick": self.tick_count,
                          "event": event, "node": name, "detail": detail})


    def expansion(self, condition):
        self._record("expand", condition.name)


    def after_tick(self, root, world_state, goal_held):
        self.tick_count += 1

        for behaviour in root.iterate():
            # Actions only. Conditions and composites change status every tick.
            if isinstance(behaviour, (Condition, py_trees.composites.Composite)):
                continue

            key = id(behaviour)
            before = self.previous.get(key, INVALID)
            after = behaviour.status
            self.previous[key] = after

            if after == RUNNING and before != RUNNING:
                self._record("start", behaviour.name)
            elif before == RUNNING and after == SUCCESS:
                self._record("success", behaviour.name)
            elif before == RUNNING and after == FAILURE:
                self._record("failure", behaviour.name)
            elif before == RUNNING and after == INVALID:
                self._record("halted", behaviour.name)
            elif before != RUNNING and after in (SUCCESS, FAILURE) and before != after:
                # Started and finished within one tick
                self._record("start", behaviour.name)
                self._record(after.name.lower(), behaviour.name)

        state = frozenset(world_state)
        if state != self.last_state:
            self._record("state", detail=" ".join(sorted(state)))
            self.last_state = state

        if goal_held != self.last_goal:
            if goal_held or self.last_goal is not None:
                self._record("goal", detail="held" if goal_held else "lost")
            self.last_goal = goal_held


    def close(self):
        with open(self.out_path, "w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.FIELDS)
            writer.writeheader()
            writer.writerows(self.rows)

        self._printSummary()
        print(f"  timing log       : {self.out_path} ({len(self.rows)} events)")


    def _printSummary(self):
        # One line per action run, start to end, for the thesis timeline table
        open_runs = {}
        print("\n  action timeline (s since first tick)")

        for row in self.rows:
            name, event = row["node"], row["event"]

            if event == "start":
                open_runs[name] = row["time_s"]
            elif event in ("success", "failure", "halted") and name in open_runs:
                start = open_runs.pop(name)
                print(f"    {name:<12} {start:>8.2f} {row['time_s']:>8.2f}  {event}")
            elif event == "goal":
                print(f"    goal {row['detail']:<7} {row['time_s']:>17.2f}")

        for name, start in open_runs.items():
            print(f"    {name:<12} {start:>8.2f}  still running")