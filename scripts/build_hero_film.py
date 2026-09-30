# designed by mew
"""Build a stable campus / lab photo film with soft dissolves."""

import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
public = root / "frontend/public"
assets = public / "assets"
workspace = tempfile.TemporaryDirectory(prefix="litong-film-")
temp = Path(workspace.name)
# Start and finish on Mingde so the final fade matches the beginning of the loop.
shots = [
    "assets/campus-hero.jpg",
    "images/group_photo_2025.webp",
    "assets/campus-gate.jpg",
    "images/group_photo_2024_2.webp",
    "images/group_photo_2024.webp",
    "assets/campus-hero.jpg",
]
fps = 24
duration = 4.8
frames = round(fps * duration)
for i, source in enumerate(shots):
    target = temp / f"shot-{i}.mp4"
    # Fixed overscan avoids zoom jitter; the integer crop glides across each still.
    pan = f"38+180*n/{frames - 1}" if i % 2 == 0 else f"218-180*n/{frames - 1}"
    filt = (
        "scale=1856:1044:force_original_aspect_ratio=increase,"
        "crop=1856:1044,setsar=1,"
        f"crop=1600:900:x='{pan}':y=72,format=yuv420p"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-loop",
            "1",
            "-framerate",
            str(fps),
            "-i",
            str(public / source),
            "-vf",
            filt,
            "-frames:v",
            str(frames),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "21",
            str(target),
        ],
        check=True,
    )
    print("Rendered shot", i + 1, flush=True)
# Encode each dissolve independently, avoiding filter frame-rate negotiation issues.
fade_frames = 18
hold_end = frames - fade_frames
parts = []
for i in range(len(shots)):
    start = 0 if i == 0 else fade_frames
    end = frames if i == len(shots) - 1 else hold_end
    hold = temp / f"hold-{i}.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(temp / f"shot-{i}.mp4"),
            "-vf",
            f"trim=start_frame={start}:end_frame={end},setpts=PTS-STARTPTS",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            str(hold),
        ],
        check=True,
    )
    parts.append(hold)
    if i < len(shots) - 1:
        dissolve = temp / f"dissolve-{i}.mp4"
        graph = f"[0:v]trim=start_frame={hold_end}:end_frame={frames},setpts=PTS-STARTPTS[a];[1:v]trim=start_frame=0:end_frame={fade_frames},setpts=PTS-STARTPTS[b];[a][b]blend=all_expr='A*(1-min(N/{fade_frames - 1},1))+B*min(N/{fade_frames - 1},1)':shortest=1,fps={fps}[out]"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(temp / f"shot-{i}.mp4"),
                "-i",
                str(temp / f"shot-{i + 1}.mp4"),
                "-filter_complex",
                graph,
                "-map",
                "[out]",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                str(dissolve),
            ],
            check=True,
        )
        parts.append(dissolve)
    print("Composed scene", i + 1, flush=True)
listing = temp / "sequence.txt"
listing.write_text("".join("file '" + str(p) + "'\n" for p in parts))
subprocess.run(
    [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-reinit_filter",
        "0",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(listing),
        "-vf",
        "scale=1280:-2:flags=lanczos,scale=in_range=auto:out_range=tv,format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "28",
        "-profile:v",
        "main",
        "-level:v",
        "3.1",
        "-pix_fmt",
        "yuv420p",
        "-color_range",
        "tv",
        "-r",
        "24",
        "-movflags",
        "+faststart",
        str(temp / "campus-lab-film.mp4"),
    ],
    check=True,
)
(temp / "campus-lab-film.mp4").replace(assets / "campus-film.mp4")
info = subprocess.check_output(
    [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(assets / "campus-film.mp4"),
    ],
    text=True,
)
(temp / "film-metadata.json").write_text(info)
print("Installed photo film:", assets / "campus-film.mp4", flush=True)
