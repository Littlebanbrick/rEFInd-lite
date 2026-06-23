#!/usr/bin/env python3
"""
rEFInd-lite background configuration tool.

One-command background setup: detects your screen resolution, resizes any
image to fit, and updates the theme configuration — no manual copying, no
hand-editing config files.

Usage:
    python3 configure.py                        # auto-detect, use default bg
    python3 configure.py --bg ~/my_wallpaper.jpg  # set a custom background
    python3 configure.py --resolution 1920x1080   # specify resolution explicitly
    python3 configure.py --bg image.png -r 2560x1440
    python3 configure.py --detect                 # print detected resolution only

Requirements: Python 3.8+, Pillow (pip install Pillow)
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
BG_DIR = SCRIPT_DIR / "bg"
DEFAULT_BG = BG_DIR / "background.png"
THEME_CONF = SCRIPT_DIR / "theme.conf"
BANNER_LINE_PREFIX = "banner themes/rEFInd-lite/bg/"


# ---------------------------------------------------------------------------
# Resolution detection
# ---------------------------------------------------------------------------
def detect_resolution():
    """Detect the primary display resolution. Returns (width, height) or None."""
    # Method 1: xrandr
    try:
        out = subprocess.check_output(
            ["xrandr", "--current"], text=True, stderr=subprocess.DEVNULL
        )
        for line in out.splitlines():
            if " connected primary " in line or " connected " in line:
                # e.g. "HDMI-0 connected primary 1920x1080+0+0"
                parts = line.split()
                for p in parts:
                    if "x" in p and "+" in p:
                        res = p.split("+")[0]
                        w, h = res.split("x")
                        return int(w), int(h)
    except (FileNotFoundError, subprocess.CalledProcessError, ValueError):
        pass

    # Method 2: /sys/class/drm
    try:
        for card in sorted(Path("/sys/class/drm").iterdir()):
            if not card.name.endswith("-1"):
                continue  # skip connectors that aren't the first output
            status = (card / "status").read_text().strip()
            if status != "connected":
                continue
            modes = (card / "modes").read_text().strip().splitlines()
            if modes:
                w, h = modes[0].split("x")
                return int(w), int(h)
    except (FileNotFoundError, PermissionError, ValueError, IndexError):
        pass

    return None


# ---------------------------------------------------------------------------
# Image processing
# ---------------------------------------------------------------------------
def resize_image(src_path, width, height, dst_path):
    """Resize an image to exactly width×height and save as PNG."""
    try:
        from PIL import Image
    except ImportError:
        print(
            "ERROR: Pillow is required for image processing.\n"
            "       Install it with:  pip install Pillow"
        )
        sys.exit(1)

    print(f"  Reading: {src_path}")
    img = Image.open(src_path)
    src_w, src_h = img.size
    print(f"  Original size: {src_w}×{src_h}")

    # Convert RGBA images to RGB (PNG backgrounds don't need transparency)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        # Composite onto black background to remove transparency
        bg = Image.new("RGB", img.size, (0, 0, 0))
        bg.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Resize to exact screen dimensions (simple stretch)
    img = img.resize((width, height), Image.LANCZOS)
    print(f"  Resized to:  {width}×{height}")

    # Save
    img.save(dst_path, "PNG")
    print(f"  Saved: {dst_path}")


# ---------------------------------------------------------------------------
# Config update
# ---------------------------------------------------------------------------
def update_theme_conf(bg_filename):
    """Update the banner line in theme.conf to point to bg_filename."""
    lines = THEME_CONF.read_text(encoding="utf-8").splitlines()
    new_lines = []
    updated = False

    for line in lines:
        if line.lstrip().startswith("banner themes/rEFInd-lite/bg/"):
            new_lines.append(f"banner themes/rEFInd-lite/bg/{bg_filename}")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        # Banner line not found — append one
        new_lines.append(f"banner themes/rEFInd-lite/bg/{bg_filename}")

    THEME_CONF.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"  Updated: {THEME_CONF}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="rEFInd-lite background configuration tool"
    )
    parser.add_argument(
        "--bg",
        metavar="IMAGE",
        help="Path to a custom background image (PNG, JPG, BMP, etc.)",
    )
    parser.add_argument(
        "-r", "--resolution",
        metavar="WxH",
        help="Screen resolution, e.g. 1920x1080. Auto-detected if omitted.",
    )
    parser.add_argument(
        "--detect",
        action="store_true",
        help="Print detected screen resolution and exit.",
    )
    args = parser.parse_args()

    # --detect mode
    if args.detect:
        res = detect_resolution()
        if res:
            print(f"{res[0]}x{res[1]}")
        else:
            print("Could not detect resolution. Please specify with --resolution.")
            sys.exit(1)
        return

    # Resolve resolution
    if args.resolution:
        try:
            w, h = args.resolution.split("x")
            width, height = int(w), int(h)
        except ValueError:
            print(f"ERROR: Invalid resolution format '{args.resolution}'. Use WxH, e.g. 1920x1080.")
            sys.exit(1)
    else:
        detected = detect_resolution()
        if detected:
            width, height = detected
            print(f"Detected resolution: {width}×{height}")
        else:
            print(
                "ERROR: Could not auto-detect screen resolution.\n"
                "       Please specify it manually with --resolution, e.g.:\n"
                "         python3 configure.py --resolution 1920x1080"
            )
            sys.exit(1)

    # Determine source image
    if args.bg:
        src = Path(args.bg).expanduser().resolve()
        if not src.is_file():
            print(f"ERROR: Image not found: {src}")
            sys.exit(1)
        # Use the original filename, but ensure it's a PNG for rEFInd
        dst_name = src.stem + ".png"
    else:
        src = DEFAULT_BG
        dst_name = "background.png"

    dst = BG_DIR / dst_name

    print(f"Configuring rEFInd-lite background for {width}×{height}:")
    resize_image(str(src), width, height, str(dst))
    update_theme_conf(dst_name)

    print()
    print("Done! Your rEFInd-lite theme is now configured.")
    print(f"  Background:   bg/{dst_name}")
    print(f"  Resolution:   {width}×{height}")
    print()
    print("To complete installation:")
    print(f"  Add 'include themes/rEFInd-lite/theme.conf' to your refind.conf")


if __name__ == "__main__":
    main()
