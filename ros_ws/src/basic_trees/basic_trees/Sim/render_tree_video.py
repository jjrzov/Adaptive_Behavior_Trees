'''
Turns the frames written by TreeRecorder into a video that plays in real time,
each tree held on screen for as long as it lasted during the run.

    python3 render_tree_video.py tree_frames/ --out tree.mp4

Needs Graphviz (dot) and ffmpeg. Frames are padded to one canvas, since the
tree grows during the run and a video needs a fixed size. With --png-only it
stops after writing transparent PNGs, for laying the tree over the robot
footage in a video editor.
'''
import argparse
import csv
import glob
import os
import subprocess

from PIL import Image


def renderPngs(frame_dir, dpi, background):
    pngs = []
    for dot_path in sorted(glob.glob(os.path.join(frame_dir, "frame_*.dot"))):
        png_path = dot_path[:-4] + ".png"
        subprocess.run(["dot", "-Tpng", f"-Gdpi={dpi}", f"-Gbgcolor={background}",
                        dot_path, "-o", png_path], check=True)
        pngs.append(png_path)
    return pngs


def padToCanvas(pngs, background):
    # One canvas big enough for the largest tree, with even sides for H.264
    sizes = [Image.open(p).size for p in pngs]
    width = max(w for w, _ in sizes) + 40
    height = max(h for _, h in sizes) + 40
    width, height = width + width % 2, height + height % 2

    fill = (0, 0, 0, 0) if background == "transparent" else background
    padded = []
    for p in pngs:
        im = Image.open(p).convert("RGBA")
        canvas = Image.new("RGBA", (width, height), fill)
        canvas.alpha_composite(im, ((width - im.width) // 2, 20))    # Centred, pinned to the top
        out = p.replace("frame_", "padded_")
        canvas.save(out)
        padded.append(out)
    return padded


def frameTimes(frame_dir):
    with open(os.path.join(frame_dir, "frames.csv")) as f:
        return [float(r["time_s"]) for r in csv.DictReader(f)]


def sampleFrames(times, fps, hold_last):
    # For each video frame, the tree current at that moment: the last one recorded
    # at or before it. Sampling on the video clock keeps the video in step with the
    # run; trees that lasted less than one video frame are simply never shown.
    total = round((times[-1] + hold_last) * fps)
    shown, i = [], 0
    for k in range(total):
        t = k / fps
        while i + 1 < len(times) and times[i + 1] <= t:
            i += 1
        shown.append(i)
    return shown


def writeVideo(padded, times, out_path, fps, hold_last):
    # ffmpeg concat list, one entry per run of video frames showing the same tree
    shown = sampleFrames(times, fps, hold_last)
    runs = []
    for i in shown:
        if runs and runs[-1][0] == i:
            runs[-1][1] += 1
        else:
            runs.append([i, 1])

    list_path = os.path.join(os.path.dirname(padded[0]), "concat.txt")
    with open(list_path, "w") as f:
        for i, count in runs:
            f.write(f"file '{os.path.abspath(padded[i])}'\nduration {count / fps:.6f}\n")
        f.write(f"file '{os.path.abspath(padded[runs[-1][0]])}'\n")   # concat needs the last file repeated

    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", list_path,
                    "-vf", f"fps={fps},format=yuv420p", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "18", out_path], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("frame_dir")
    parser.add_argument("--out", default="tree.mp4")
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--background", default="white",
                        help="canvas colour for the video, e.g. white or '#fafafa'")
    parser.add_argument("--hold-last", type=float, default=3.0, help="seconds to hold the final tree")
    parser.add_argument("--png-only", action="store_true",
                        help="stop after writing transparent, equally sized PNGs")
    args = parser.parse_args()

    background = "transparent" if args.png_only else args.background
    pngs = renderPngs(args.frame_dir, args.dpi, background)
    padded = padToCanvas(pngs, background)
    if args.png_only:
        print(f"{len(padded)} padded PNGs in {args.frame_dir}/")
        return

    writeVideo(padded, frameTimes(args.frame_dir), args.out, args.fps, args.hold_last)
    print(f"wrote {args.out} from {len(padded)} frames")


if __name__ == "__main__":
    main()