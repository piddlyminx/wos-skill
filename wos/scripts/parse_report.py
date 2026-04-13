#!/usr/bin/env python3
"""Parse a Whiteout Survival battle report from top + bottom screenshots.

Anchoring:  cv2 template matching against header images.
Numbers:    RapidOCR (primary) with CRNN-CTC and Tesseract fallbacks.
Names:      RapidOCR (PaddleOCR v5 ONNX) with sharpening.

Usage:
    parse_report.py <top_screenshot> [bottom_screenshot]
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

# ── Paths ──────────────────────────────────────────────────────────────────────
SKILL_DIR  = Path(__file__).resolve().parent.parent
TPL_BATTLE = SKILL_DIR / "templates" / "tpl_battle_overview.png"
TPL_STAT   = SKILL_DIR / "templates" / "tpl_stat_bonuses.png"
ONNX_MODEL = SKILL_DIR / "models"    / "wos_ocr.onnx"
TESSERACT  = "/home/linuxbrew/.linuxbrew/bin/tesseract"

# Offset from template top-left y to anchor origin.
BO_ANCHOR_OFFSET = 12
SB_ANCHOR_OFFSET = 12

# ── CRNN-CTC charset ──────────────────────────────────────────────────────────
CHARS    = "+-,.0123456789%"
IDX2CHAR = {i + 1: c for i, c in enumerate(CHARS)}
IMG_H, IMG_W = 32, 160   # model input size

# ── Crop geometry — Top screenshot (relative to Battle Overview anchor) ───────
_NAME_Y  = (172, 204)
_STAT_ROWS = {
    "troops":          (326, 356),
    "losses":          (384, 414),
    "injured":         (442, 472),
    "lightly_injured": (500, 530),
    "survivors":       (558, 588),
}
_LEFT_NAME_X  = (25,  335)
_RIGHT_NAME_X = (385, 695)
_LEFT_STAT_X  = (105, 255)
_RIGHT_STAT_X = (476, 615)

# ── Crop geometry — Bottom screenshot (relative to Stat Bonuses anchor) ───────
_SB_FIRST_Y = 45          # first row centre, relative to anchor
_SB_STRIDE  = 58.5        # row spacing
_SB_LEFT_X  = (100, 231)
_SB_RIGHT_X = (470, 606)
_SB_LABELS  = [
    "infantry_attack",  "infantry_defense",  "infantry_lethality",  "infantry_health",
    "lancer_attack",    "lancer_defense",    "lancer_lethality",    "lancer_health",
    "marksman_attack",  "marksman_defense",  "marksman_lethality",  "marksman_health",
]

# Troop power numbers sit above the Stat Bonuses header.
_TP_Y_REL = (-83, -60)    # (top, bottom) relative to SB anchor
_TP_XS = [
    (32, 128), (128, 224), (224, 322),    # left: infantry, lancer, marksman
    (400, 497), (497, 592), (592, 690),   # right
]
_TP_KEYS = [
    "left_infantry",  "left_lancer",  "left_marksman",
    "right_infantry", "right_lancer", "right_marksman",
]

# Sharpen kernel for name crops
_SHARPEN = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)


# ── Singletons (lazy-loaded) ──────────────────────────────────────────────────
_onnx_sess: ort.InferenceSession | None = None
_rapid_ocr: RapidOCR | None = None


def _get_onnx() -> ort.InferenceSession:
    global _onnx_sess
    if _onnx_sess is None:
        _onnx_sess = ort.InferenceSession(str(ONNX_MODEL))
    return _onnx_sess


def _get_rapid() -> RapidOCR:
    global _rapid_ocr
    if _rapid_ocr is None:
        cfg = str(SKILL_DIR / "models" / "rapidocr_config.yaml")
        _rapid_ocr = RapidOCR(config_path=cfg)
    return _rapid_ocr


# ── Low-level helpers ──────────────────────────────────────────────────────────
def _match_template(img_bgr: np.ndarray, tpl_bgr: np.ndarray) -> tuple[int, int, float]:
    """Return (x, y, score) of best template match."""
    res = cv2.matchTemplate(
        cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY),
        cv2.cvtColor(tpl_bgr, cv2.COLOR_BGR2GRAY),
        cv2.TM_CCOEFF_NORMED,
    )
    _, score, _, (x, y) = cv2.minMaxLoc(res)
    return x, y, score


def _safe_crop(img: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
    h, w = img.shape[:2]
    return img[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]


def _crop_gray(img_bgr: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
    crop = _safe_crop(img_bgr, x1, y1, x2, y2)
    if crop.size == 0:
        return np.zeros((1, 1), dtype=np.uint8)
    return cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)


def _crop_bgr(img_bgr: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
    return _safe_crop(img_bgr, x1, y1, x2, y2)


# ── OCR engines ────────────────────────────────────────────────────────────────
def _ocr_rapid(crop_bgr: np.ndarray) -> str:
    """Run RapidOCR on a BGR crop."""
    if crop_bgr.size == 0:
        return ""
    result = _get_rapid()(crop_bgr)
    if not result or not result[0]:
        return ""
    return " ".join(r[1] for r in result[0])


def _ocr_crnn(gray: np.ndarray, sharpen: bool = False) -> str:
    """Run the CRNN-CTC model on a grayscale crop."""
    if gray.size == 0:
        return ""
    if sharpen:
        gray = cv2.filter2D(gray, -1, _SHARPEN)
    pil = Image.fromarray(gray).convert("L")
    w, h = pil.size
    pil = pil.resize((min(int(w * IMG_H / h), IMG_W), IMG_H), Image.BILINEAR)
    padded = Image.new("L", (IMG_W, IMG_H), 255)
    padded.paste(pil, (0, 0))
    arr = np.array(padded, dtype=np.float32)[np.newaxis, np.newaxis] / 255.0
    logits = _get_onnx().run(None, {"image": arr})[0][:, 0, :]
    indices = logits.argmax(axis=1)
    chars, prev = [], 0
    for idx in indices:
        if idx != 0 and idx != prev and idx in IDX2CHAR:
            chars.append(IDX2CHAR[idx])
        prev = idx
    return "".join(chars)


def _ocr_tesseract(gray: np.ndarray) -> str:
    """Run Tesseract on a grayscale crop."""
    if gray.size == 0:
        return ""
    cv2.imwrite("/tmp/_tess_crop.png", gray)
    r = subprocess.run(
        [TESSERACT, "/tmp/_tess_crop.png", "-", "--psm", "7"],
        capture_output=True, text=True,
    )
    return r.stdout.strip()


# ── Parsing helpers ────────────────────────────────────────────────────────────
def _parse_int(s: str) -> int:
    cleaned = re.sub(r"[^0-9]", "", s) if s else ""
    return int(cleaned) if cleaned else 0


def _parse_pct(s: str) -> float:
    cleaned = re.sub(r"[^0-9.+\-]", "", s) if s else ""
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


def _valid_pct(v: float) -> bool:
    """Stat bonus sanity check: 0.0% to 4000.0%, 1 decimal place."""
    if v < 0.0 or v > 4000.0:
        return False
    return abs(round(v * 10) - v * 10) < 0.01


def _valid_tp(v: int) -> bool:
    """Troop power sanity check: 0 to 2,000,000."""
    return 0 <= v <= 2_000_000


def _find_hdr_y(img_bgr: np.ndarray, needle: str) -> tuple[int, int] | None:
    """Return (y1, y2) of the best OCR box matching needle."""
    needle_clean = re.sub(r"\s+", "", needle.lower())
    result = _get_rapid()(img_bgr)
    if not result or not result[0]:
        return None

    best = None
    for box, text, conf in result[0]:
        text_clean = re.sub(r"\s+", "", str(text).lower())
        if needle_clean in text_clean:
            ys = [p[1] for p in box]
            cand = (float(conf), int(min(ys)), int(max(ys)))
            if best is None or cand[0] > best[0]:
                best = cand

    if best is None:
        return None
    _, y1, y2 = best
    return y1, y2


def _extract_tpc_window(tpc_img: np.ndarray) -> dict[str, object] | None:
    """Return validated TPC strip metadata, or None when headers are not usable."""
    tpc_box = _find_hdr_y(tpc_img, "Troop Power Comparison")
    sb_box = _find_hdr_y(tpc_img, "Stat Bonuses")
    if not (tpc_box and sb_box):
        return None

    y_top = tpc_box[1] + 4
    y_bot = sb_box[0] - 2
    if y_bot <= y_top:
        return None

    strip = tpc_img[y_top:y_bot, :, :]
    mid = strip.shape[1] // 2
    return {
        "tpc_box": tpc_box,
        "sb_box": sb_box,
        "y_top": y_top,
        "y_bot": y_bot,
        "strip": strip,
        "halves": {"left": strip[:, :mid, :], "right": strip[:, mid:, :]},
    }


def _read_name(img_bgr: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> str:
    """Read a player/enemy name with RapidOCR (sharpened, then unsharpened fallback)."""
    crop = _safe_crop(img_bgr, x1, y1, x2, y2)
    if crop.size == 0:
        return ""
    # Try sharpened first (better for clean text)
    sharp = cv2.filter2D(crop, -1, _SHARPEN)
    result = _get_rapid()(sharp)
    if result and result[0]:
        return " ".join(r[1] for r in result[0])
    # Fallback: unsharpened color crop
    result = _get_rapid()(crop)
    if result and result[0]:
        return " ".join(r[1] for r in result[0])
    return ""


def _detect_roles(img_bgr: np.ndarray, anchor_y: int) -> tuple[str, str]:
    """Red banner = attacker, blue = defender."""
    y = anchor_y + 55
    if y >= img_bgr.shape[0]:
        return "attacker", "defender"
    left_bgr = img_bgr[y, 150:250, :].mean(axis=0)
    return ("attacker", "defender") if left_bgr[2] > left_bgr[0] else ("defender", "attacker")


# ── OCR with validation + fallback ────────────────────────────────────────────
def _read_pct_validated(bot: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> float:
    """Read a stat bonus percentage with validation and fallback chain."""
    crop_bgr = _crop_bgr(bot, x1, y1, x2, y2)
    gray = _crop_gray(bot, x1, y1, x2, y2)

    raw = _ocr_rapid(crop_bgr)
    v = _parse_pct(raw)
    if _valid_pct(v):
        return v

    raw = _ocr_crnn(gray)
    v = _parse_pct(raw)
    if _valid_pct(v):
        return v

    raw = _ocr_tesseract(gray)
    v = _parse_pct(raw)
    if _valid_pct(v):
        return v

    return _parse_pct(_ocr_rapid(crop_bgr))


def _read_tp_validated(bot: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> int:
    """Read a troop power integer with validation and fallback chain."""
    crop_bgr = _crop_bgr(bot, x1, y1, x2, y2)
    gray = _crop_gray(bot, x1, y1, x2, y2)

    raw = _ocr_rapid(crop_bgr)
    v = _parse_int(raw)
    if _valid_tp(v):
        return v

    raw = _ocr_crnn(gray, sharpen=True)
    v = _parse_int(raw)
    if _valid_tp(v):
        return v

    raw = _ocr_tesseract(gray)
    v = _parse_int(raw)
    if _valid_tp(v):
        return v

    return _parse_int(_ocr_rapid(crop_bgr))


# ── Public API ─────────────────────────────────────────────────────────────────
def parse_battle_report(
    top_path: str,
    bottom_path: str | None = None,
    tpc_path: str | None = None,
    debug_outdir: str | None = None,
) -> dict:
    """Parse a battle report from screenshots.

    Args:
        top_path:    Screenshot taken at the top of the report (Battle Overview).
        bottom_path: Screenshot taken at the bottom (legacy Troop Power slots + Stat Bonuses).
        tpc_path:    Optional screenshot that includes the region between the
                     "Troop Power Comparison" header and the "Stat Bonuses" header.
                     When provided, troop_power is parsed from avatar templates + OCR under-avatar
                     (more reliable than compacted slot parsing).

    Returns:
        dict with keys: result, left, right.
    """
    top = cv2.imread(top_path)
    if top is None:
        raise FileNotFoundError(f"Cannot read: {top_path}")

    tpl_bo = cv2.imread(str(TPL_BATTLE))
    if tpl_bo is None:
        raise FileNotFoundError(f"Missing template: {TPL_BATTLE}")
    _, bo_y, _ = _match_template(top, tpl_bo)
    anchor = bo_y + BO_ANCHOR_OFFSET

    # ── Roles ──────────────────────────────────────────────────────────────────
    left_role, right_role = _detect_roles(top, anchor)

    # ── Names ──────────────────────────────────────────────────────────────────
    ny1, ny2 = anchor + _NAME_Y[0], anchor + _NAME_Y[1]
    left_name  = _read_name(top, _LEFT_NAME_X[0],  ny1, _LEFT_NAME_X[1],  ny2)
    right_name = _read_name(top, _RIGHT_NAME_X[0], ny1, _RIGHT_NAME_X[1], ny2)

    # ── Stat rows (CRNN) ──────────────────────────────────────────────────────
    stats: dict[str, int] = {}
    for field, (off_y1, off_y2) in _STAT_ROWS.items():
        sy1, sy2 = anchor + off_y1, anchor + off_y2
        for side, (sx1, sx2) in [("left", _LEFT_STAT_X), ("right", _RIGHT_STAT_X)]:
            gray = _crop_gray(top, sx1, sy1, sx2, sy2)
            stats[f"{side}_{field}"] = _parse_int(_ocr_crnn(gray))

    # ── Bottom screenshot ──────────────────────────────────────────────────────
    troop_power:  dict[str, int]   = {}
    stat_bonuses: dict[str, float] = {}

    if bottom_path:
        bot = cv2.imread(bottom_path)
        if bot is None:
            raise FileNotFoundError(f"Cannot read: {bottom_path}")

        tpl_sb = cv2.imread(str(TPL_STAT))
        if tpl_sb is None:
            raise FileNotFoundError(f"Missing template: {TPL_STAT}")
        _, sb_y, _ = _match_template(bot, tpl_sb)
        sb_anchor = sb_y + SB_ANCHOR_OFFSET

        # Legacy troop power numbers from compacted slots above Stat Bonuses.
        # NOTE: if tpc_path is provided, we will NOT use this legacy parsing.
        tp_y1, tp_y2 = sb_anchor + _TP_Y_REL[0], sb_anchor + _TP_Y_REL[1]
        for key, (x1, x2) in zip(_TP_KEYS, _TP_XS):
            troop_power[key] = _read_tp_validated(bot, x1, tp_y1, x2, tp_y2)

        # Cross-check: troop power sums should equal troops from top section
        for prefix, keys in [("left", ["left_infantry", "left_lancer", "left_marksman"]),
                              ("right", ["right_infantry", "right_lancer", "right_marksman"])]:
            tp_sum = sum(troop_power.get(k, 0) for k in keys)
            troops_total = stats.get(f"{prefix}_troops", 0)
            if tp_sum != troops_total and troops_total > 0:
                # Retry with CRNN+sharpen
                for key in keys:
                    idx = _TP_KEYS.index(key)
                    x1, x2 = _TP_XS[idx]
                    gray = _crop_gray(bot, x1, tp_y1, x2, tp_y2)
                    v = _parse_int(_ocr_crnn(gray, sharpen=True))
                    if _valid_tp(v):
                        troop_power[key] = v
                # Check again, try tesseract
                tp_sum = sum(troop_power.get(k, 0) for k in keys)
                if tp_sum != troops_total:
                    for key in keys:
                        idx = _TP_KEYS.index(key)
                        x1, x2 = _TP_XS[idx]
                        gray = _crop_gray(bot, x1, tp_y1, x2, tp_y2)
                        v = _parse_int(_ocr_tesseract(gray))
                        if _valid_tp(v):
                            troop_power[key] = v

        # Stat bonuses (12 rows × 2 sides, validated with fallback)
        for i, label in enumerate(_SB_LABELS):
            yc = sb_anchor + _SB_FIRST_Y + round(i * _SB_STRIDE)
            y1, y2 = yc - 4, yc + 26
            for side, (x1, x2) in [("left", _SB_LEFT_X), ("right", _SB_RIGHT_X)]:
                stat_bonuses[f"{side}_{label}"] = _read_pct_validated(bot, x1, y1, x2, y2)

    # ── Optional: Troop Power Comparison strip (avatar templates + OCR) ───────
    if tpc_path:
        tpc_img = cv2.imread(tpc_path)
        if tpc_img is None:
            raise FileNotFoundError(f"Cannot read: {tpc_path}")

        # Debug: save annotated and intermediate crops when requested
        _dbg_dir = None
        if debug_outdir:
            try:
                _dbg_dir = Path(debug_outdir)
                _dbg_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                _dbg_dir = None

        tpc_window = _extract_tpc_window(tpc_img)
        if tpc_window is None:
            raise RuntimeError(
                "TPC frame is not parseable: required headers were missing, clipped, or overlapped "
                f"in {tpc_path}"
            )
        else:
            tpc_box = tpc_window["tpc_box"]
            sb_box = tpc_window["sb_box"]
            y_top = tpc_window["y_top"]
            y_bot = tpc_window["y_bot"]
            strip = tpc_window["strip"]
            halves = tpc_window["halves"]

            if _dbg_dir is not None:
                # Save the strip and halves
                cv2.imwrite(str(_dbg_dir / "tpc_strip.png"), strip)
                cv2.imwrite(str(_dbg_dir / "tpc_strip_left.png"), halves["left"])
                cv2.imwrite(str(_dbg_dir / "tpc_strip_right.png"), halves["right"])

                # Save an annotated header/cutoff image
                ann = tpc_img.copy()
                cv2.rectangle(ann, (0, tpc_box[0]), (ann.shape[1]-1, tpc_box[1]), (0,255,255), 2)
                cv2.rectangle(ann, (0, sb_box[0]), (ann.shape[1]-1, sb_box[1]), (255,255,0), 2)
                cv2.line(ann, (0, y_top), (ann.shape[1]-1, y_top), (0,255,0), 2)
                cv2.line(ann, (0, y_bot), (ann.shape[1]-1, y_bot), (0,0,255), 2)
                cv2.imwrite(str(_dbg_dir / "tpc_headers_annotated.png"), ann)

            # ── TPC slot geometry (relative to Stat Bonuses anchor in tpc_path image) ──
            # Positions confirmed from report_tpc.png OCR measurements.
            # Left fills L1→L2→L3; right fills R3←R2←R1 (rightmost first).
            # Avatar y: -160 to -70 relative to SB anchor.
            # Count y:  -63 to -40 relative to SB anchor.
            _TPC_AVATAR_Y = (-160, -70)
            _TPC_COUNT_Y  = (-63,  -40)
            # (x1, x2) for each slot in the full tpc_path image (not the half-strip)
            _TPC_SLOTS = {
                "L1": (28, 128), "L2": (126, 225), "L3": (226, 324),
                "R1": (396, 496), "R2": (495, 596), "R3": (596, 692),
            }
            _TROOP_TYPES = ("infantry", "lancer", "marksman")

            sb_anchor_tpc = sb_box[0]  # top of Stat Bonuses text

            def _ocr_count_crop(crop: np.ndarray) -> int:
                """OCR a count crop; return integer or 0 if no number found."""
                if crop.size == 0:
                    return 0
                r = _get_rapid()(crop)
                if not r or not r[0]:
                    return 0
                joined = "".join(str(t) for (_b, t, _c) in r[0])
                s = re.sub(r"[^0-9,]", "", joined).replace(",", "")
                return int(s) if s else 0

            def _best_match(avatar_crop: np.ndarray, candidates: tuple[str, ...]) -> tuple[str, float, str]:
                """Return (troop_type, score, tpl_name) — best template match among candidates."""
                best = ("unknown", -1.0, "none")
                if avatar_crop.size == 0:
                    return best
                for troop in candidates:
                    tpl_dir = SKILL_DIR / "templates" / "troop_avatars_trimmed2" / troop
                    for p in tpl_dir.glob("*.png"):
                        tpl = cv2.imread(str(p))
                        if tpl is None:
                            continue
                        th, tw = tpl.shape[:2]
                        ih, iw = avatar_crop.shape[:2]
                        if th >= ih or tw >= iw:
                            continue
                        res = cv2.matchTemplate(avatar_crop, tpl, cv2.TM_CCOEFF_NORMED)
                        _, v, _, _ = cv2.minMaxLoc(res)
                        if v > best[1]:
                            best = (troop, float(v), p.name)
                return best

            def _read_slot(slot: str) -> tuple[int, np.ndarray]:
                """Return (count, avatar_crop) for a named slot. count=0 means slot is empty."""
                x1, x2 = _TPC_SLOTS[slot]
                ay1 = sb_anchor_tpc + _TPC_AVATAR_Y[0]
                ay2 = sb_anchor_tpc + _TPC_AVATAR_Y[1]
                cy1 = sb_anchor_tpc + _TPC_COUNT_Y[0]
                cy2 = sb_anchor_tpc + _TPC_COUNT_Y[1]
                count_crop  = tpc_img[cy1:cy2, x1:x2]
                avatar_crop = tpc_img[ay1:ay2, x1:x2]
                return _ocr_count_crop(count_crop), avatar_crop

            # ── Classify each side using slot occupancy + positional logic ──────────
            # Left side fills L1→L2→L3; right side fills R3←R2←R1.
            # Order is always infantry < lancer < marksman.
            # OCR determines occupancy; template matching resolves type only when ambiguous.

            new_tp = {
                "left":  {"infantry": 0, "lancer": 0, "marksman": 0},
                "right": {"infantry": 0, "lancer": 0, "marksman": 0},
            }
            debug_lines = []  # (side, slot, troop_type, score, tpl_name, count)

            for side, slots in [("left", ("L1", "L2", "L3")), ("right", ("R1", "R2", "R3"))]:
                counts = {}
                avatars = {}
                for sl in slots:
                    cnt, av = _read_slot(sl)
                    counts[sl] = cnt
                    avatars[sl] = av

                occupied = [sl for sl in slots if counts[sl] > 0]
                n = len(occupied)

                if n == 0:
                    pass  # nothing on this side

                elif n == 3:
                    # Position is definitive — no template matching needed
                    for sl, troop in zip(slots, _TROOP_TYPES):
                        new_tp[side][troop] = counts[sl]
                        debug_lines.append((side, sl, troop, 1.0, "positional", counts[sl]))

                elif n == 2:
                    sl1, sl2 = occupied
                    # Classify the first occupied slot to resolve ambiguity
                    if side == "left":
                        # L1 is inf or lancer; if inf then L2 is lancer or marksman
                        candidates1 = ("infantry", "lancer")
                    else:
                        # R2 is inf or lancer; if inf then R3 is lancer or marksman
                        candidates1 = ("infantry", "lancer")
                    t1, score1, tpl1 = _best_match(avatars[sl1], candidates1)
                    new_tp[side][t1] = counts[sl1]
                    debug_lines.append((side, sl1, t1, score1, tpl1, counts[sl1]))
                    if t1 == "lancer":
                        # Second must be marksman
                        new_tp[side]["marksman"] = counts[sl2]
                        debug_lines.append((side, sl2, "marksman", 1.0, "positional", counts[sl2]))
                    else:
                        # t1 == infantry; classify sl2 between lancer and marksman
                        t2, score2, tpl2 = _best_match(avatars[sl2], ("lancer", "marksman"))
                        new_tp[side][t2] = counts[sl2]
                        debug_lines.append((side, sl2, t2, score2, tpl2, counts[sl2]))

                else:  # n == 1
                    sl1 = occupied[0]
                    t1, score1, tpl1 = _best_match(avatars[sl1], _TROOP_TYPES)
                    new_tp[side][t1] = counts[sl1]
                    debug_lines.append((side, sl1, t1, score1, tpl1, counts[sl1]))

            if _dbg_dir is not None:
                (_dbg_dir / "tpc_match_debug.txt").write_text(
                    "\n".join(
                        f"{side}\t{slot}\t{troop}\tscore={score:.4f}\ttpl={tpl}\tval={count}"
                        for (side, slot, troop, score, tpl, count) in debug_lines
                    )
                    + "\n"
                )
                # Save annotated tpc image showing slot boxes
                ann = tpc_img.copy()
                for slot, (x1, x2) in _TPC_SLOTS.items():
                    ay1 = sb_anchor_tpc + _TPC_AVATAR_Y[0]
                    ay2 = sb_anchor_tpc + _TPC_AVATAR_Y[1]
                    cy1 = sb_anchor_tpc + _TPC_COUNT_Y[0]
                    cy2 = sb_anchor_tpc + _TPC_COUNT_Y[1]
                    cv2.rectangle(ann, (x1, ay1), (x2, ay2), (0, 255, 0), 2)
                    cv2.rectangle(ann, (x1, cy1), (x2, cy2), (0, 0, 255), 2)
                    cv2.putText(ann, slot, (x1, ay1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
                cv2.imwrite(str(_dbg_dir / "tpc_slots_annotated.png"), ann)

            if any(new_tp["left"].values()) or any(new_tp["right"].values()):
                troop_power.update({
                    "left_infantry":   new_tp["left"]["infantry"],
                    "left_lancer":     new_tp["left"]["lancer"],
                    "left_marksman":   new_tp["left"]["marksman"],
                    "right_infantry":  new_tp["right"]["infantry"],
                    "right_lancer":    new_tp["right"]["lancer"],
                    "right_marksman":  new_tp["right"]["marksman"],
                })
            else:
                raise RuntimeError(
                    "TPC troop-power parse failed (no non-zero troop counts). "
                    f"Debug: {debug_lines}"
                )

    # ── Winner ─────────────────────────────────────────────────────────────────
    l_surv = stats.get("left_survivors", 0)
    r_surv = stats.get("right_survivors", 0)
    if l_surv > 0 and r_surv == 0:
        result = "left_wins"
    elif r_surv > 0 and l_surv == 0:
        result = "right_wins"
    else:
        result = "draw"

    # ── Assemble output ────────────────────────────────────────────────────────
    def _side(prefix: str, role: str, name: str) -> dict:
        side = {
            "role": role,
            "name": name,
            "troops":          stats.get(f"{prefix}_troops", 0),
            "losses":          stats.get(f"{prefix}_losses", 0),
            "injured":         stats.get(f"{prefix}_injured", 0),
            "lightly_injured": stats.get(f"{prefix}_lightly_injured", 0),
            "survivors":       stats.get(f"{prefix}_survivors", 0),
        }
        if troop_power:
            side["troop_power"] = {
                t: troop_power.get(f"{prefix}_{t}", 0)
                for t in ("infantry", "lancer", "marksman")
            }
        if stat_bonuses:
            side["stat_bonuses"] = {
                label: stat_bonuses.get(f"{prefix}_{label}", 0.0)
                for label in _SB_LABELS
            }
        return side

    return {
        "result": result,
        "left":   _side("left",  left_role,  left_name),
        "right":  _side("right", right_role, right_name),
    }


# ── CLI ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: parse_report.py <top_screenshot> [bottom_screenshot]")
        sys.exit(1)
    top = sys.argv[1]
    bot = sys.argv[2] if len(sys.argv) > 2 else None
    tpc = sys.argv[3] if len(sys.argv) > 3 else None
    dbg = sys.argv[4] if len(sys.argv) > 4 else None
    result = parse_battle_report(top, bot, tpc, debug_outdir=dbg)
    print(json.dumps(result, indent=2))
