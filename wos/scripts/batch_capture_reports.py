#!/usr/bin/env python3
"""Batch-capture WOS reports.

For each report (assumes a report is open in Mail viewer):
- capture top (Battle Overview)
- scroll to bottom (detect Battle Details / Power Up)
- capture bottom (Stat Bonuses + troop numbers visible)
- tap right-edge chevron to advance to next report

Outputs two PNGs per report.
"""

import argparse
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np
import pytesseract

pytesseract.pytesseract.tesseract_cmd = "/home/linuxbrew/.linuxbrew/bin/tesseract"


def adb_swipe(serial, x1, y1, x2, y2, dur=700):
    subprocess.check_call(["adb", "-s", serial, "shell", "input", "swipe",
                           str(x1), str(y1), str(x2), str(y2), str(dur)])


def adb_tap(serial, x, y):
    subprocess.check_call(["adb", "-s", serial, "shell", "input", "tap", str(x), str(y)])


def adb_screencap(serial, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        p = subprocess.Popen(["adb", "-s", serial, "exec-out", "screencap", "-p"], stdout=f)
        p.wait()
        if p.returncode != 0:
            raise RuntimeError(f"screencap failed rc={p.returncode}")


def _end_region(img_bgr):
    h, w = img_bgr.shape[:2]
    footer_h = 103
    y2 = max(0, h - footer_h)
    y1 = max(0, y2 - 360)
    return img_bgr[y1:y2, :, :]


def contains_end_buttons(img_bgr) -> bool:
    band = _end_region(img_bgr)
    if band.size == 0:
        return False
    gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (gray.shape[1] * 2, gray.shape[0] * 2), interpolation=cv2.INTER_LINEAR)
    gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    text = pytesseract.image_to_string(gray, config='--psm 6')
    t = " ".join(text.split())
    return ("Battle" in t and "Details" in t) or ("Power" in t and "Up" in t)


def scroll_to_top(serial, swipes=6):
    for _ in range(swipes):
        adb_swipe(serial, 360, 300, 360, 1200, 800)
        time.sleep(0.35)


def scroll_to_bottom(serial, max_steps=40):
    tmp = Path('/tmp/wos_tmp_bottom_check.png')
    for _ in range(max_steps):
        adb_screencap(serial, tmp)
        img = cv2.imread(str(tmp))
        if img is not None and contains_end_buttons(img):
            return True
        adb_swipe(serial, 360, 1120, 360, 120, 700)
        time.sleep(0.55)
    # final check
    adb_screencap(serial, tmp)
    img = cv2.imread(str(tmp))
    return bool(img is not None and contains_end_buttons(img))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--serial', required=True)
    ap.add_argument('--outdir', required=True)
    ap.add_argument('--n', type=int, default=10)
    ap.add_argument('--start', type=int, default=1)
    ap.add_argument('--chev-x', type=int, default=705)
    ap.add_argument('--chev-y', type=int, default=640)
    ap.add_argument('--sleep-after-next', type=float, default=0.8)
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    for i in range(args.start, args.start + args.n):
        prefix = f"r{i:02d}"
        print(f"=== {prefix} ===")

        scroll_to_top(args.serial)
        top_path = outdir / f"{prefix}_top.png"
        adb_screencap(args.serial, top_path)

        reached = scroll_to_bottom(args.serial)
        bottom_path = outdir / f"{prefix}_bottom.png"
        adb_screencap(args.serial, bottom_path)

        print(f"top={top_path}")
        print(f"bottom={bottom_path} bottom_reached={reached}")

        # next report
        adb_tap(args.serial, args.chev_x, args.chev_y)
        time.sleep(args.sleep_after_next)


if __name__ == '__main__':
    main()
