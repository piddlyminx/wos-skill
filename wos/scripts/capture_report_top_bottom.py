"""Capture a full WOS battle report: 4 screenshots.

1. report_top.png  — Battle Overview (scrolled to top)
2. report_bot.png  — Troop Power + Stat Bonuses (scrolled to bottom)
3. bd_top.png      — Battle Details top (after tapping BD button)
4. bd_bot.png      — Battle Details bottom (scrolled down)

Bottom detection uses OCR to find "Battle Details" / "Power Up" buttons
(report) or "Attacker" / "Defender" banners (BD page).
"""
from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
import pytesseract

from emulator import WosEmulator

logger = logging.getLogger(__name__)
_rapid_ocr = None

_TPC_MIN_HEADER_GAP = 24
_TPC_MIN_TOP_MARGIN = 8
_TPC_AVATAR_TOP_REL = -160

# Use brew tesseract v5 if present
pytesseract.pytesseract.tesseract_cmd = "/home/linuxbrew/.linuxbrew/bin/tesseract"

# ── Battle Details button location (fallback only) ─────────────────────────────
BD_BUTTON_X, BD_BUTTON_Y = 185, 970


def _get_rapid():
    global _rapid_ocr
    if _rapid_ocr is None:
        from rapidocr_onnxruntime import RapidOCR

        cfg = str(Path(__file__).resolve().parent.parent / "models" / "rapidocr_config.yaml")
        _rapid_ocr = RapidOCR(config_path=cfg)
    return _rapid_ocr


# ── Bottom detection ───────────────────────────────────────────────────────────
def _end_region(img_bgr):
    """Return a crop just above the footer where end buttons would appear."""
    h, w = img_bgr.shape[:2]
    footer_h = 103
    y2 = max(0, h - footer_h)
    y1 = max(0, y2 - 360)
    return img_bgr[y1:y2, :, :]


def _ocr_region(img_bgr) -> str:
    """OCR a region, return cleaned text."""
    if img_bgr.size == 0:
        return ""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (gray.shape[1] * 2, gray.shape[0] * 2), interpolation=cv2.INTER_LINEAR)
    gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    text = pytesseract.image_to_string(gray, config='--psm 6')
    return " ".join(text.split())


def contains_report_end(img_bgr) -> tuple[bool, str]:
    """Detect report bottom by looking for Battle Details / Power Up buttons."""
    band = _end_region(img_bgr)
    t = _ocr_region(band)
    is_end = ("Battle" in t and "Details" in t) or ("Power" in t and "Up" in t)
    return is_end, t[:200]


def contains_bd_end(img_bgr) -> tuple[bool, str]:
    """Detect BD bottom by looking for final Defender banner in lower half."""
    h, w = img_bgr.shape[:2]
    # Check lower third of screen
    band = img_bgr[h * 2 // 3:, :, :]
    t = _ocr_region(band)
    # BD bottom has the last "Defender" or "Attacker" section with hero rows
    # When we've scrolled far enough, we'll see the bottom content
    # Use a simpler approach: detect if scroll made no change (content stopped)
    return False, t[:200]


def _find_text_box(img_bgr: np.ndarray, needle: str) -> tuple[int, int, float] | None:
    """Return (y1, y2, confidence) of the best OCR box matching needle."""
    needle_clean = re.sub(r"\s+", "", needle.lower())
    result = _get_rapid()(img_bgr)
    if not result or not result[0]:
        return None

    best = None
    for box, text, conf in result[0]:
        text_clean = re.sub(r"\s+", "", str(text).lower())
        if needle_clean in text_clean:
            ys = [pt[1] for pt in box]
            cand = (int(min(ys)), int(max(ys)), float(conf))
            if best is None or cand[2] > best[2]:
                best = cand
    return best


def _inspect_tpc_frame(img_bgr: np.ndarray) -> dict[str, object]:
    """Inspect whether a frame contains both TPC and Stat Bonuses headers."""
    tpc_box = _find_text_box(img_bgr, "Troop Power Comparison")
    sb_box = _find_text_box(img_bgr, "Stat Bonuses")
    gap = (sb_box[0] - tpc_box[1]) if (tpc_box and sb_box) else None
    sb_top = sb_box[0] if sb_box else None
    avatar_top = (sb_top + _TPC_AVATAR_TOP_REL) if sb_top is not None else None
    parseable = bool(
        tpc_box
        and sb_box
        and gap is not None
        and gap >= _TPC_MIN_HEADER_GAP
        and avatar_top is not None
        and avatar_top >= _TPC_MIN_TOP_MARGIN
        and tpc_box[0] >= _TPC_MIN_TOP_MARGIN
    )

    score = 0.0
    if tpc_box:
        score += 1.0 + min(tpc_box[2], 1.0)
    if sb_box:
        score += 1.0 + min(sb_box[2], 1.0)
    if gap is not None:
        score += 1.0 if gap > 0 else -1.0
        score += min(max(gap, 0), 120) / 120.0
    if avatar_top is not None:
        score += min(max(avatar_top, 0), 120) / 120.0

    return {
        "tpc_box": tpc_box,
        "sb_box": sb_box,
        "gap": gap,
        "sb_top": sb_top,
        "avatar_top": avatar_top,
        "parseable": parseable,
        "score": score,
    }


def _drag_vertical(emulator: WosEmulator, delta_px: int, dur_ms: int = 500) -> None:
    """Perform a small controlled vertical drag around screen centre."""
    if delta_px == 0:
        return
    y1 = 640
    y2 = int(np.clip(y1 + delta_px, 180, 1140))
    if y1 == y2:
        return
    emulator.swipe(360, y1, 360, y2, dur_ms)


def _capture_tpc_with_retries(
    emulator: WosEmulator,
    outdir: Path,
    prefix: str,
    debug: bool = False,
    max_attempts: int = 10,
) -> str:
    """Capture a TPC screenshot using validated small drag adjustments."""
    tpc_path = outdir / f"{prefix}_tpc.png"
    best_img = None
    best_state = None

    for attempt in range(max_attempts):
        img = emulator.screencap_bgr()
        state = _inspect_tpc_frame(img)

        if debug:
            cv2.imwrite(str(outdir / f"{prefix}_tpc_attempt_{attempt:02d}.png"), img)
            logger.info(
                "TPC attempt %d: parseable=%s gap=%s avatar_top=%s tpc=%s sb=%s score=%.3f",
                attempt,
                state["parseable"],
                state["gap"],
                state["avatar_top"],
                state["tpc_box"],
                state["sb_box"],
                state["score"],
            )

        if best_state is None or float(state["score"]) > float(best_state["score"]):
            best_img = img
            best_state = state

        if state["parseable"]:
            cv2.imwrite(str(tpc_path), img)
            return str(tpc_path)

        if attempt == max_attempts - 1:
            break

        if state["tpc_box"] and not state["sb_box"]:
            delta = -70
        elif not state["tpc_box"] and state["sb_box"]:
            delta = 150 if attempt < 3 else 105
        elif state["tpc_box"] and state["sb_box"]:
            if state["avatar_top"] is not None and int(state["avatar_top"]) < _TPC_MIN_TOP_MARGIN:
                delta = 60
            else:
                delta = 40
        else:
            delta = 180 if attempt == 0 else 120

        _drag_vertical(emulator, delta)
        time.sleep(0.45)

    if best_img is not None:
        cv2.imwrite(str(tpc_path), best_img)
    raise RuntimeError(
        "TPC capture failed after "
        f"{max_attempts} attempts; best observed frame was not parseable (state={best_state}, saved={tpc_path})"
    )


# ── Scroll helpers ─────────────────────────────────────────────────────────────
def scroll_to_top(emulator: WosEmulator, swipes: int = 6) -> None:
    """Scroll up to reach the top of the page."""
    for _ in range(swipes):
        emulator.swipe(360, 300, 360, 1200, 800)
        time.sleep(0.35)


def scroll_to_bottom(
    emulator: WosEmulator,
    detect_fn: Callable[[np.ndarray], tuple[bool, str]],
    max_steps: int = 30,
    debug: bool = False,
) -> bool:
    """Repeatedly swipe up until detect_fn returns True or content stops moving."""
    prev_hash = None

    for step in range(max_steps):
        img = emulator.screencap_bgr()
        hit, snippet = detect_fn(img)
        if debug:
            print(f'step {step:02d}: end={hit} text="{snippet}"')
        if hit:
            return True

        # Check if content stopped scrolling (image unchanged)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        curr_hash = gray[200:-200, :].mean()
        if prev_hash is not None and abs(curr_hash - prev_hash) < 0.5:
            if debug:
                print(f'step {step:02d}: content stopped scrolling')
            return True
        prev_hash = curr_hash

        emulator.swipe(360, 1120, 360, 120, 700)
        time.sleep(0.55)

    # Final check
    img = emulator.screencap_bgr()
    hit, _ = detect_fn(img)
    return bool(hit)


# ── Public capture functions ───────────────────────────────────────────────────
def capture_report(
    emulator: WosEmulator,
    outdir: Path,
    prefix: str = "report",
    debug: bool = False,
) -> dict[str, str | bool]:
    """Capture report_top, report_bot, and report_tpc.

    Assumes report is already open at top.

    - report_top: Battle Overview (top)
    - report_bot: bottom area containing Stat Bonuses
    - report_tpc: after reaching bottom, scroll up slightly so "Troop Power Comparison" is visible
      (used by parse_report.py to extract troop types + counts under avatars).
    """
    outdir.mkdir(parents=True, exist_ok=True)
    top_path = outdir / f'{prefix}_top.png'
    emulator.screencap(str(top_path))

    ok = scroll_to_bottom(emulator, contains_report_end, debug=debug)
    bot_path = outdir / f'{prefix}_bot.png'
    emulator.screencap(str(bot_path))

    # ADB gestures are only approximate, so validate the TPC frame after each
    # small drag instead of assuming one fixed swipe will land correctly.
    tpc_path = _capture_tpc_with_retries(emulator, outdir, prefix, debug=debug)

    return {
        "report_top": str(top_path),
        "report_bot": str(bot_path),
        "report_tpc": str(tpc_path),
        "report_bottom_reached": ok,
    }


def _find_battle_details_button(img_bgr) -> tuple[int, int] | None:
    """Find the 'Battle Details' button centre via OCR. Returns (x, y) or None."""
    from rapidocr_onnxruntime import RapidOCR
    ocr = RapidOCR()
    result = ocr(img_bgr)
    if not result or not result[0]:
        return None
    needle = "battledetails"
    for box, text, _conf in result[0]:
        if needle in re.sub(r"\s+", "", str(text).lower()):
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            return int((min(xs) + max(xs)) / 2), int((min(ys) + max(ys)) / 2)
    return None


def capture_battle_details(
    emulator: WosEmulator,
    outdir: Path,
    prefix: str = "bd",
    debug: bool = False,
) -> dict[str, str]:
    """Tap Battle Details, capture bd_top and bd_bot. Assumes report bottom is visible."""
    outdir.mkdir(parents=True, exist_ok=True)

    # Scroll back to bottom to ensure Battle Details button is visible
    # (capture_report leaves the screen mid-scroll after taking the TPC screenshot)
    scroll_to_bottom(emulator, contains_report_end, max_steps=10, debug=debug)

    # Find the Battle Details button via OCR on the current screen
    img = emulator.screencap_bgr()
    btn_pos = _find_battle_details_button(img)
    if btn_pos is not None:
        bx, by = btn_pos
        logger.info("Battle Details button found via OCR at (%d, %d)", bx, by)
    else:
        bx, by = BD_BUTTON_X, BD_BUTTON_Y
        logger.warning("Battle Details button not found via OCR; using fallback (%d, %d)", bx, by)

    emulator.tap(bx, by)
    time.sleep(1.5)

    # Already at top when BD opens — no scroll needed
    top_path = outdir / f'{prefix}_top.png'
    emulator.screencap(str(top_path))

    # Small scroll down (less than half screen) to reveal remaining heroes
    emulator.swipe(360, 800, 360, 500, 500)
    time.sleep(0.5)

    bot_path = outdir / f'{prefix}_bot.png'
    emulator.screencap(str(bot_path))

    emulator.back()
    time.sleep(1.0)

    return {
        "bd_top": str(top_path),
        "bd_bot": str(bot_path),
    }


def capture_full_report(
    emulator: WosEmulator,
    outdir: Path,
    debug: bool = False,
) -> dict[str, str | bool]:
    """Capture all 4 screenshots for a single report."""
    outdir.mkdir(parents=True, exist_ok=True)

    logger.info("Capturing battle report to %s", outdir)
    report_data = capture_report(emulator, outdir, debug=debug)

    logger.info("Capturing battle details to %s", outdir)
    bd_data = capture_battle_details(emulator, outdir, debug=debug)

    return report_data | bd_data
