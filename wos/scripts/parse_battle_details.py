#!/usr/bin/env python3
"""Extract hero names from Battle Details screenshots.

Takes 2 screenshots: BD top (unscrolled) and BD bottom (scrolled).
Returns list of hero pairs: [{left_hero, right_hero}, ...]
Left is always the report owner's side, right is opponent's side.

Uses a whitelist of known hero names (data/hero_names.txt) to filter OCR noise.
"""
import sys, json
from pathlib import Path
import cv2
import numpy as np

_rapid = None
_sharpen_kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)

# ── Hero name whitelist ────────────────────────────────────────────────────────
_HERO_NAMES_FILE = Path(__file__).parent.parent / "data" / "hero_names.txt"
_HERO_NAMES: set[str] = set()
_HERO_NAMES_LOWER: dict[str, str] = {}  # lowercase -> canonical


def _load_hero_names():
    global _HERO_NAMES, _HERO_NAMES_LOWER
    if _HERO_NAMES:
        return
    with open(_HERO_NAMES_FILE) as f:
        for line in f:
            name = line.strip()
            if name:
                _HERO_NAMES.add(name)
                _HERO_NAMES_LOWER[name.lower()] = name


def _match_hero_name(text: str) -> str | None:
    """Match OCR text against known hero names. Returns canonical name or None."""
    _load_hero_names()
    t = text.strip()

    # Exact match (case-insensitive)
    if t.lower() in _HERO_NAMES_LOWER:
        return _HERO_NAMES_LOWER[t.lower()]

    # Fuzzy: check if any hero name is contained in the text
    for lower, canonical in _HERO_NAMES_LOWER.items():
        if lower in t.lower() and len(lower) >= 3:
            return canonical

    return None


def _get_rapid():
    global _rapid
    if _rapid is None:
        from rapidocr_onnxruntime import RapidOCR
        cfg = str(Path(__file__).parent.parent / "models" / "rapidocr_config.yaml")
        _rapid = RapidOCR(config_path=cfg)
    return _rapid


def _ocr_full(img):
    """Run RapidOCR on full image with sharpening."""
    sharpened = cv2.filter2D(img, -1, _sharpen_kernel)
    result = _get_rapid()(sharpened)
    if not result or not result[0]:
        return []
    items = []
    for box, text, conf in result[0]:
        ys = [pt[1] for pt in box]
        xs = [pt[0] for pt in box]
        items.append({
            "text": text,
            "y": int(np.mean(ys)),
            "x": int(np.mean(xs)),
        })
    return items


def _extract_heroes_from_image(img):
    """Extract hero names from a single BD screenshot using whitelist matching."""
    raw_items = _ocr_full(img)
    if not raw_items:
        return []

    # Match each OCR item against hero whitelist
    candidates = []
    for it in raw_items:
        # Check for "Vacant"
        if "vacant" in it["text"].lower():
            candidates.append({"name": "Vacant", "y": it["y"], "x": it["x"]})
            continue

        matched = _match_hero_name(it["text"])
        if matched:
            candidates.append({"name": matched, "y": it["y"], "x": it["x"]})

    # Pair by similar y-coordinate
    candidates.sort(key=lambda c: c["y"])
    pairs = []
    used = set()

    for i, c1 in enumerate(candidates):
        if i in used:
            continue
        best_j = None
        for j, c2 in enumerate(candidates):
            if j <= i or j in used:
                continue
            if abs(c1["y"] - c2["y"]) < 40:
                best_j = j
                break

        if best_j is not None:
            c2 = candidates[best_j]
            left = c1 if c1["x"] < c2["x"] else c2
            right = c2 if c1["x"] < c2["x"] else c1
            pairs.append({
                "left_hero": left["name"],
                "right_hero": right["name"],
            })
            used.add(i)
            used.add(best_j)
        else:
            # Unpaired — solo hero visible
            side = "left_hero" if c1["x"] < 360 else "right_hero"
            pairs.append({side: c1["name"]})
            used.add(i)

    return pairs


def parse_battle_details(bd_top_path, bd_bottom_path):
    """Parse two Battle Details screenshots. Returns list of hero pairs."""
    img_top = cv2.imread(str(bd_top_path))
    img_bot = cv2.imread(str(bd_bottom_path))

    if img_top is None:
        raise FileNotFoundError(f"Cannot read {bd_top_path}")
    if img_bot is None:
        raise FileNotFoundError(f"Cannot read {bd_bottom_path}")

    all_pairs = []
    for img in [img_top, img_bot]:
        all_pairs.extend(_extract_heroes_from_image(img))

    # Deduplicate: each hero name appears at most once per side
    seen_left = set()
    seen_right = set()
    unique = []
    for pair in all_pairs:
        lh = pair.get("left_hero", "")
        rh = pair.get("right_hero", "")
        if lh and lh in seen_left:
            lh = ""
        if rh and rh in seen_right:
            rh = ""
        if not lh and not rh:
            continue
        if lh:
            seen_left.add(lh)
        if rh:
            seen_right.add(rh)
        entry = {}
        if lh:
            entry["left_hero"] = lh
        if rh:
            entry["right_hero"] = rh
        unique.append(entry)

    return {"hero_pairs": unique}


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <bd_top.png> <bd_bottom.png>")
        sys.exit(1)
    data = parse_battle_details(sys.argv[1], sys.argv[2])
    print(json.dumps(data, indent=2))
