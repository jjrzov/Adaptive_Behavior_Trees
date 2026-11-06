'''
Records the tree every time its shape or any node's status changes, so the
tree can be played as a video next to a screen recording of the robot.

During the run it only writes Graphviz DOT text, which is cheap enough to keep
the tick loop on time. Render the frames into a video afterwards with
render_tree_video.py.

    snapshot = py_trees.visitors.SnapshotVisitor()
    tree.add_visitor(snapshot)            # records which nodes each tick visits
    recorder = TreeRecorder(out_dir="tree_frames")
    ...
    tree.tick()
    recorder.after_tick(root, snapshot.visited)   # after every tick, and again after an expansion
    ...
    recorder.close()

Output, in out_dir:
    frame_00000.dot ...   one tree per change
    frames.csv            frame number and wall-clock seconds since the first frame

Times are wall clock, not the node clock, because a screen recording runs on
wall time. Node colours follow the presentation: SUCCESS green, FAILURE red,
RUNNING yellow, and white for a node not ticked on that tick. py_trees leaves
an unticked node holding its last status, so pass the snapshot visitor's
visited map, or the frame shows stale colours on branches the tick skipped.
'''
import csv
import os
import time

import py_trees


Status = py_trees.common.Status

# (fill, border) per status. A node not ticked this tick (INVALID) keeps the default.
STATUS_STYLE = {
    Status.SUCCESS: ("#d5e8d4", "#2e7d32"),
    Status.FAILURE: ("#f8cecc", "#d0412a"),
    Status.RUNNING: ("#fff2cc", "#b8860b"),
}


def isKind(node, class_name):
    # Match by class name so the recorder needs no imports from basic_trees
    return any(c.__name__ == class_name for c in type(node).__mro__)


def walk(node):
    # Pre-order, so children are emitted left to right
    yield node
    for child in node.children:
        yield from walk(child)


def quote(text):
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


class TreeRecorder:
    def __init__(self, out_dir="tree_frames", literals_per_line=2):
        os.makedirs(out_dir, exist_ok=True)
        self.out_dir = out_dir
        self.literals_per_line = literals_per_line

        self.t0 = None              # Set on the first frame
        self.last_signature = None
        self.frame = 0

        self.index_file = open(os.path.join(out_dir, "frames.csv"), "w", newline="")
        self.index = csv.writer(self.index_file)
        self.index.writerow(["frame", "time_s"])

    def after_tick(self, root, visited=None):
        # visited maps node id to status for the nodes ticked on this tick. Without
        # it every node shows its stored status, which may be left over from an
        # earlier tick.
        self.visited = visited

        # Write a frame only when the shape or a shown status has changed
        signature = tuple((id(node), self.shownStatus(node)) for node in walk(root))
        if signature == self.last_signature:
            return
        self.last_signature = signature

        now = time.monotonic()
        if self.t0 is None:
            self.t0 = now

        with open(os.path.join(self.out_dir, f"frame_{self.frame:05d}.dot"), "w") as f:
            f.write(self.toDot(root))

        self.index.writerow([self.frame, f"{now - self.t0:.3f}"])
        self.index_file.flush()     # Keep the index usable if the run is killed
        self.frame += 1

    def shownStatus(self, node):
        if self.visited is None:
            return node.status
        return self.visited.get(node.id, Status.INVALID)

    def close(self):
        self.index_file.close()
        print(f"  tree recorder    : {self.frame} frames in {self.out_dir}/")

    def nodeAttributes(self, node):
        # Shapes match the slides: ? and -> boxes, double border on goal structure,
        # ellipses for conditions, grey boxes for actions
        if isKind(node, "GoalSequence") or isKind(node, "GoalSelector"):
            label = "→" if isKind(node, "Sequence") else "?"
            return {"shape": "box", "label": label, "peripheries": 2, "fontsize": 20,
                    "width": 0.5, "height": 0.5, "fixedsize": "true"}

        if isKind(node, "Selector") or isKind(node, "Sequence"):
            label = "→" if isKind(node, "Sequence") else "?"
            return {"shape": "box", "label": label, "fontsize": 20,
                    "width": 0.45, "height": 0.45, "fixedsize": "true"}

        if hasattr(node, "preconditions"):
            literals = sorted(node.preconditions)
            n = self.literals_per_line
            lines = [", ".join(literals[i:i + n]) for i in range(0, len(literals), n)]
            return {"shape": "ellipse", "label": "\n".join(lines) or node.name}

        return {"shape": "box", "label": node.name, "fillcolor": "#f5f5f5"}

    def toDot(self, root):
        lines = ["digraph tree {",
                 '  graph [ordering=out, bgcolor="transparent", nodesep=0.25, ranksep=0.4];',
                 '  node [fontname="Helvetica", fontsize=14, style=filled, fillcolor="#ffffff",'
                 ' color="#333333", penwidth=1.2];',
                 '  edge [arrowhead=none, color="#333333", penwidth=1.2];']

        for node in walk(root):
            attrs = self.nodeAttributes(node)

            status = self.shownStatus(node)
            if status in STATUS_STYLE:
                fill, border = STATUS_STYLE[status]
                attrs.update(fillcolor=fill, color=border, penwidth=2.5)

            body = ", ".join(f"{k}={quote(v)}" for k, v in attrs.items())
            lines.append(f"  {quote(node.id)} [{body}];")

            for child in node.children:
                lines.append(f"  {quote(node.id)} -> {quote(child.id)};")

        lines.append("}")
        return "\n".join(lines) + "\n"