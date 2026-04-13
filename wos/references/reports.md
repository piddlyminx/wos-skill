# WOS Reports

Use this reference only when working on battle-report reading, OCR, or report-output behavior.

## Output Schema

```json
{
  "result": "left_wins|right_wins|draw",
  "left": {
    "role": "attacker|defender",
    "name": "[TAG]PlayerName",
    "troops": 850517,
    "losses": 0,
    "injured": 0,
    "lightly_injured": 0,
    "survivors": 850517,
    "troop_power": {
      "infantry": 403603,
      "lancer": 211623,
      "marksman": 235291
    },
    "stat_bonuses": {
      "infantry_attack": 1774.5
    },
    "heroes": ["Wu Ming", "Norah", "Wayne"]
  },
  "right": {}
}
```

## Report Parsing Facts

- Reports and Battle Details pages open at top.
- `wosctl report` merges the main report parse with Battle Details hero data.
- `wosctl reports` starts at visible inbox entry 1, captures `N` consecutive battle reports, skips non-battle items until the next `Battle Overview` screen, and saves each merged report as JSON under `captures/reports/<timestamp>_<tab>/`.
- `wosctl reports` returns `output_dir` plus the saved `files` by default. `--full-json` additionally inlines the parsed report objects as `reports`.
- A short Battle Details scroll of about 300px reveals the third hero pair.
- Hero names are filtered against `data/hero_names.txt`.
- Troop-power sums are cross-checked against total troops, with OCR fallback on mismatch.
- Non-battle reports such as rally cancellations parse as all zeros.

## Visual/Domain Assumptions

- Attacker is shown with red background and crossed swords.
- Defender is shown with blue background and shield.
- The Battle Overview and Stat Bonuses headers are anchored by templates in `templates/`.
- Refine stats are six fixed rows: Infantry, Lancer, Marksman crossed with Lethality and Health.
- `parse_refine_stats(img_bgr)` returns `{stat, current, max, delta}` rows and `delta` may be `None`.

## Relevant Files

- `scripts/report_reader.py`
- `scripts/capture_report_top_bottom.py`
- `scripts/parse_report.py`
- `scripts/parse_battle_details.py`
- `scripts/parse_refine.py`
- `templates/tpl_battle_overview.png`
- `templates/tpl_stat_bonuses.png`
- `data/hero_names.txt`
- `models/wos_ocr.onnx`
