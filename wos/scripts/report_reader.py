"""High-level battle report reading flow for WOS inbox tabs."""
from __future__ import annotations

import difflib
import json
import logging
import re
import tempfile
import time
from pathlib import Path

from capture_report_top_bottom import capture_full_report
from navigation import (
    WosNavigationError,
    find_template,
    goto_city,
    goto_world_map,
)

_rapid_ocr = None
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_CAPTURED_REPORTS_DIR = Path(__file__).resolve().parent.parent / "captures" / "reports"
TEMPLATE_MAIL_ICON = str(_TEMPLATES_DIR / "tpl_mail_icon.png")
TEMPLATE_BATTLE_OVERVIEW = str(_TEMPLATES_DIR / "tpl_battle_overview.png")
TEMPLATE_REPORT_NEXT_BUTTON = str(_TEMPLATES_DIR / "report_next_button.png")

_REPORT_ENTRY_Y = {
    1: 220,
    2: 340,
    3: 510,
    4: 680,
    5: 880,
}
_REPORT_ENTRY_X = 360
_REPORT_NEXT_BUTTON_REGION = (620, 560, 720, 720)
_REPORT_NEXT_BUTTON_FALLBACK = (700, 640)

_MAIL_TAB_ALIASES = {
    "war": "war",
    "wars": "war",
    "report": "reports",
    "reports": "reports",
    "star": "starred",
    "starred": "starred",
}
_MAIL_TAB_LABELS = {
    "war": {"war", "wars"},
    "reports": {"report", "reports"},
    "starred": {"starred", "star"},
}
_MAIL_TAB_FALLBACK_X = {
    "war": 85,
    "reports": 240,
    "starred": 400,
}
_MAIL_TAB_Y = 92


def _get_rapid():
    global _rapid_ocr
    if _rapid_ocr is None:
        from rapidocr_onnxruntime import RapidOCR

        cfg = str(Path(__file__).resolve().parent.parent / "models" / "rapidocr_config.yaml")
        _rapid_ocr = RapidOCR(config_path=cfg)
    return _rapid_ocr


def normalize_mail_tab(tab: str) -> str:
    key = re.sub(r"[^a-z]", "", tab.lower())
    if key not in _MAIL_TAB_ALIASES:
        allowed = ", ".join(sorted({"war", "reports", "starred"}))
        raise ValueError(f"Unknown report tab '{tab}'. Use one of: {allowed}")
    return _MAIL_TAB_ALIASES[key]


def _ocr_text_items(img_bgr, y1: int, y2: int) -> list[dict]:
    crop = img_bgr[y1:y2, :, :]
    if crop.size == 0:
        return []
    result = _get_rapid()(crop)
    if not result or not result[0]:
        return []

    items: list[dict] = []
    for box, text, _conf in result[0]:
        xs = [pt[0] for pt in box]
        ys = [pt[1] for pt in box]
        items.append({
            "text": text,
            "x": int(sum(xs) / len(xs)),
            "y": y1 + int(sum(ys) / len(ys)),
        })
    return items


def _find_mail_tab_target(img_bgr, tab: str) -> tuple[int, int]:
    labels = _MAIL_TAB_LABELS[tab]
    candidates = _ocr_text_items(img_bgr, 40, 180)

    best: tuple[int, int] | None = None
    best_score = 0.0
    for item in candidates:
        cleaned = re.sub(r"[^a-z]", "", item["text"].lower())
        if not cleaned:
            continue
        if cleaned in labels:
            return item["x"], item["y"]
        score = max(difflib.SequenceMatcher(None, cleaned, label).ratio() for label in labels)
        if score > best_score:
            best = (item["x"], item["y"])
            best_score = score

    if best is not None and best_score >= 0.6:
        return best

    return _MAIL_TAB_FALLBACK_X[tab], _MAIL_TAB_Y


def _open_mail_inbox(emulator) -> None:
    goto_world_map(emulator)
    img = emulator.screencap_bgr()
    found, (cx, cy) = find_template(img, TEMPLATE_MAIL_ICON, threshold=0.8)
    if not found:
        # Mail icon not visible on world map — go to city and retry from there
        logging.info("Mail icon not found on world map; navigating to city and retrying")
        goto_city(emulator)
        goto_world_map(emulator)
        img = emulator.screencap_bgr()
        found, (cx, cy) = find_template(img, TEMPLATE_MAIL_ICON, threshold=0.8)
        if not found:
            raise WosNavigationError("Mail icon template not found on world map")
    emulator.tap(cx, cy)
    time.sleep(1.5)


def _select_mail_tab(emulator, tab: str) -> None:
    img = emulator.screencap_bgr()
    cx, cy = _find_mail_tab_target(img, tab)
    emulator.tap(cx, cy)
    time.sleep(1.5)


def _open_report_entry(emulator, index: int) -> None:
    if index not in _REPORT_ENTRY_Y:
        raise ValueError("Report index must be between 1 and 5")

    emulator.tap(_REPORT_ENTRY_X, _REPORT_ENTRY_Y[index])
    time.sleep(1.5)

    img = emulator.screencap_bgr()
    found, _ = find_template(img, TEMPLATE_BATTLE_OVERVIEW, threshold=0.8)
    if not found:
        raise WosNavigationError(
            f"Report entry {index} did not open a battle report screen"
        )


def _find_template_in_region(
    img_bgr,
    template_path: str,
    region: tuple[int, int, int, int],
    threshold: float = 0.8,
) -> tuple[bool, tuple[int, int]]:
    x1, y1, x2, y2 = region
    crop = img_bgr[y1:y2, x1:x2, :]
    if crop.size == 0:
        return False, (0, 0)

    found, (cx, cy) = find_template(crop, template_path, threshold=threshold)
    if not found:
        return False, (0, 0)
    return True, (x1 + cx, y1 + cy)


def _is_battle_report_screen(img_bgr) -> bool:
    found, _ = find_template(img_bgr, TEMPLATE_BATTLE_OVERVIEW, threshold=0.8)
    return found


def _tap_next_report(emulator) -> None:
    img = emulator.screencap_bgr()
    found, (cx, cy) = _find_template_in_region(
        img,
        TEMPLATE_REPORT_NEXT_BUTTON,
        _REPORT_NEXT_BUTTON_REGION,
        threshold=0.72,
    )
    if not found:
        cx, cy = _REPORT_NEXT_BUTTON_FALLBACK
        logging.info(
            "Next-report button template not found; using fallback tap at (%d,%d)",
            cx,
            cy,
        )
    emulator.tap(cx, cy)
    time.sleep(1.2)


def _advance_to_next_battle_report(emulator, max_attempts: int = 12) -> None:
    for attempt in range(1, max_attempts + 1):
        _tap_next_report(emulator)
        img = emulator.screencap_bgr()
        if _is_battle_report_screen(img):
            logging.info("Advanced to next battle report after %d tap(s)", attempt)
            return
        logging.info(
            "Next item after tap %d/%d is not a battle report; advancing again",
            attempt,
            max_attempts,
        )

    raise WosNavigationError(
        f"Could not reach the next battle report after {max_attempts} next-button taps"
    )


def _merge_report_and_heroes(report: dict, battle_details: dict) -> dict:
    for pair in battle_details.get("hero_pairs", []):
        if "left_hero" in pair:
            report["left"].setdefault("heroes", []).append(pair["left_hero"])
        if "right_hero" in pair:
            report["right"].setdefault("heroes", []).append(pair["right_hero"])
    return report


def _copy_capture_debug_files(capture: dict, out_root: Path) -> None:
    out_root.mkdir(parents=True, exist_ok=True)
    for key, value in capture.items():
        if key.endswith("_reached"):
            continue
        try:
            src = Path(value)
            if src.exists():
                (out_root / src.name).write_bytes(src.read_bytes())
        except Exception:
            pass


def _parse_captured_report(capture: dict, debug_dir: Path | None = None) -> dict:
    from parse_battle_details import parse_battle_details
    from parse_report import parse_battle_report

    report = parse_battle_report(
        capture["report_top"],
        capture["report_bot"],
        capture.get("report_tpc"),
        debug_outdir=str(debug_dir) if debug_dir else None,
    )
    battle_details = parse_battle_details(capture["bd_top"], capture["bd_bot"])
    return _merge_report_and_heroes(report, battle_details)


def _capture_and_parse_open_report(emulator, debug_dir: Path | None = None) -> dict:
    with tempfile.TemporaryDirectory(prefix="wos_report_") as tmpdir:
        tmp_path = Path(tmpdir)
        capture = capture_full_report(emulator, tmp_path)

        if debug_dir is not None:
            _copy_capture_debug_files(capture, debug_dir)

        return _parse_captured_report(capture, debug_dir=debug_dir)


def _next_capture_run_dir(tab: str) -> Path:
    _CAPTURED_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    base = _CAPTURED_REPORTS_DIR / f"{stamp}_{tab}"
    candidate = base
    suffix = 2
    while candidate.exists():
        candidate = _CAPTURED_REPORTS_DIR / f"{base.name}_{suffix:02d}"
        suffix += 1
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def _save_report_json(report: dict, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n")
    return out_path


def get_latest_report_timestamp(emulator, tab: str) -> float:
    """Read the timestamp of the latest report in the given tab.
    
    Returns the UTC calendar timestamp (seconds since epoch) of the newest
    report, or 0.0 if no reports are found.
    """
    import calendar
    _open_mail_inbox(emulator)
    _select_mail_tab(emulator, tab)
    img = emulator.screencap_bgr()
    candidates = _ocr_text_items(img, _REPORT_ENTRY_Y[1], _REPORT_ENTRY_Y[1] + 150)
    for item in candidates:
        match = re.search(r'(\d{4}-\d{2}-\d{2})\s*(\d{2}:\d{2}:\d{2})', item["text"])
        if match:
            timestamp_str = f"{match.group(1)} {match.group(2)}"
            try:
                timestamp = calendar.timegm(time.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S"))
                logging.info("get_latest_report_timestamp: latest report = %s (%.0f)", timestamp_str, timestamp)
                return timestamp
            except ValueError:
                continue
    logging.warning("get_latest_report_timestamp: no timestamp found, returning 0")
    return 0.0


def wait_for_new_report(emulator, tab: str, after: float, timeout_sec: int = 300, poll_sec: int = 5) -> bool:
    """Wait until a new report appears in the given tab after the specified timestamp."""
    import calendar
    # open the inbox and select the tab to ensure we're looking at the right place
    _open_mail_inbox(emulator)
    _select_mail_tab(emulator, tab)
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        img = emulator.screencap_bgr()
        # Check the first report entry for a timestamp newer than 'after'
        candidates = _ocr_text_items(img, _REPORT_ENTRY_Y[1], _REPORT_ENTRY_Y[1] + 150)
        # Convert from YYYY-MM-DD HH:MM:SS format to UTC timestamp and compare with 'after'
        found_ts = None
        for item in candidates:
            match = re.search(r'(\d{4}-\d{2}-\d{2})\s*(\d{2}:\d{2}:\d{2})', item["text"])
            if match:
                timestamp_str = f"{match.group(1)} {match.group(2)}"
                try:
                    # Game displays UTC — parse as UTC using calendar.timegm
                    timestamp = calendar.timegm(time.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S"))
                    found_ts = timestamp
                    if timestamp > after:
                        logging.info("wait_for_new_report: found report with timestamp %s (%.0f > %.0f)", timestamp_str, timestamp, after)
                        return True
                except ValueError:
                    continue
        if found_ts is not None:
            logging.info("wait_for_new_report: latest report timestamp %.0f, waiting for > %.0f", found_ts, after)
        else:
            logging.info("wait_for_new_report: no timestamp found in OCR, retrying...")
            # Save a debug screencap on first miss
            try:
                import cv2
                debug_path = "/tmp/wait_for_new_report_debug.png"
                cv2.imwrite(debug_path, img)
                logging.info("wait_for_new_report: saved debug screencap to %s", debug_path)
                # Also log what OCR actually found
                logging.info("wait_for_new_report: OCR candidates: %s", candidates)
            except Exception:
                pass
        # No new report found yet, wait and try again
        time.sleep(poll_sec)
    return False

def read_battle_report(emulator, tab: str, index: int = 1, debug: bool = False) -> dict:
    """Open a report from the given inbox tab and return merged parsed JSON.

    If debug=True, captured screenshots are copied to ./tmp/<temp_name>/ for inspection.
    """
    normalized_tab = normalize_mail_tab(tab)

    _open_mail_inbox(emulator)
    _select_mail_tab(emulator, normalized_tab)
    _open_report_entry(emulator, index)

    debug_dir = None
    if debug:
        debug_dir = Path.cwd() / "tmp" / f"wos_report_{int(time.time())}"

    return _capture_and_parse_open_report(emulator, debug_dir=debug_dir)


def capture_multiple_reports(emulator, tab: str, count: int, debug: bool = False) -> list[str]:
    """Capture, parse, and save multiple consecutive battle reports.

    Starts from the first visible report entry in the requested inbox tab, saves
    each merged report JSON under ``wos/captures/reports/<run>/``, and returns
    the saved JSON paths.
    """
    normalized_tab = normalize_mail_tab(tab)
    if count < 1:
        raise ValueError("Report count must be at least 1")

    _open_mail_inbox(emulator)
    _select_mail_tab(emulator, normalized_tab)
    _open_report_entry(emulator, 1)

    out_root = _next_capture_run_dir(normalized_tab)
    debug_root = None
    if debug:
        debug_root = Path.cwd() / "tmp" / out_root.name
        debug_root.mkdir(parents=True, exist_ok=True)

    saved_paths: list[str] = []
    for report_num in range(1, count + 1):
        report_debug_dir = None
        if debug_root is not None:
            report_debug_dir = debug_root / f"report_{report_num:02d}"

        merged = _capture_and_parse_open_report(emulator, debug_dir=report_debug_dir)
        saved = _save_report_json(merged, out_root / f"report_{report_num:02d}.json")
        saved_paths.append(str(saved.resolve()))

        if report_num < count:
            _advance_to_next_battle_report(emulator)

    return saved_paths
