#!/usr/bin/env python3
"""Render a real PaperTrail terminal run as a short MP4, from actual stdout."""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
MODEL = "/home/hatch/workspace/slothsort/gemma-download/blob-1b.bin"
env = dict(os.environ, PAPER_GEMMA_MODEL=MODEL)

lines = []
def run(cmd, label):
    lines.append(f"$ {label}")
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, env=env)
    lines.extend(out.stdout.splitlines())
    lines.append("")

run(["python3", "src/papertrail.py", "fetch", "--sample"], "python3 src/papertrail.py fetch --sample")
run(["python3", "src/papertrail.py", "digest", "--date", "2026-11-22"], "python3 src/papertrail.py digest --date 2026-11-22")
run(["python3", "-m", "pytest", "tests/", "-q"], "python3 -m pytest tests/ -q")
lines.append("$ cat output/digest-2026-11-22.txt")
lines.extend(Path(ROOT / "output/digest-2026-11-22.txt").read_text().splitlines())

from PIL import Image, ImageDraw, ImageFont
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 18)
    title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 22)
except Exception:
    font = ImageFont.load_default(); title_font = font

W, H = 1280, 720
frames_dir = ROOT / "demo-frames"
frames_dir.mkdir(exist_ok=True)
for p in frames_dir.glob("*.png"):
    p.unlink()
visible = 32
frame_no = 0
for i in range(len(lines) + 20):
    img = Image.new("RGB", (W, H), (18, 18, 22))
    d = ImageDraw.Draw(img)
    d.text((40, 20), "PaperTrail - real terminal run (fetch, digest, tests)", fill=(255, 200, 80), font=title_font)
    shown = lines[max(0, i - visible + 1):i + 1]
    y = 70
    for line in shown:
        colour = (120, 220, 140) if line.startswith("$") else (230, 230, 230)
        d.text((40, y), line[:110], fill=colour, font=font)
        y += 20
    for _ in range(12):
        img.save(frames_dir / f"f{frame_no:04d}.png")
        frame_no += 1

subprocess.run(["ffmpeg", "-y", "-framerate", "10", "-i", str(frames_dir / "f%04d.png"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", str(ROOT / "demo.mp4")],
               check=True, capture_output=True)
print(f"Wrote {ROOT / 'demo.mp4'} from {len(lines)} real terminal lines")
