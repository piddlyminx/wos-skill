# WOS Commands

Use this reference only when you need exact `wosctl` command forms or intent-specific details.

## Canonical Prefix

All commands below use `$WOS_DIR` which should resolve to the `wos/` directory containing this skill's `SKILL.md`:

```bash
WOS_DIR="${WOS_DIR:-/home/paul/projects_wsl/wos/skill/wos}"
```

## Diagnostics

```bash
"$WOS_DIR/scripts/wosctl" --instance <name> status
"$WOS_DIR/scripts/wosctl" --instance <name> --json status
```

## Navigation

```bash
"$WOS_DIR/scripts/wosctl" --instance <name> goto world
"$WOS_DIR/scripts/wosctl" --instance <name> goto city
"$WOS_DIR/scripts/wosctl" --instance <name> goto pets
"$WOS_DIR/scripts/wosctl" --instance <name> goto beast_cage
"$WOS_DIR/scripts/wosctl" --instance <name> goto pet "<pet name>"
"$WOS_DIR/scripts/wosctl" --instance <name> goto pet_refine "<pet name>"
```

### Pet Navigation Notes

- `goto pet` flow: city -> Beast Cage -> Pet List -> first card -> OCR name loop.
- `goto pet_refine` lands on the named pet's Refine tab.
- The pet cycle is right-only and retries blank transition frames without advancing.

Known pet names:

- Cave Hyena
- Arctic Wolf
- Musk Ox
- Giant Tapir
- Titan Roc
- Snow Leopard
- Giant Elk
- Frostscale Chameleon
- Cave Lion
- Snow Ape
- Iron Rhino
- Saber-tooth Tiger
- Mammoth
- Frost Gorilla

## Memories

```bash
"$WOS_DIR/scripts/wosctl" --instance <name> memories ./maps/memories.csv
```

### Memories Command Rules

- The map file may be CSV or JSON.
- CSV must include `Item` or `label`, plus `x` and `y` columns.
- JSON must map labels to `[x, y]` or `{x, y}`.
- OCR runs over the fixed strip from `(20,1112)` to `(700,1260)`.
- Matching is fuzzy, case-insensitive, and whitespace-insensitive.
- When multiple visible labels are recognized, any deterministic order is acceptable; the current implementation uses slot order from the fixed 2x3 strip.

## Screenshots

```bash
"$WOS_DIR/scripts/wosctl" --instance <name> screencap ./captures/current.png
```

## Reports

```bash
"$WOS_DIR/scripts/wosctl" --instance <name> report --tab war --index 1
"$WOS_DIR/scripts/wosctl" --instance <name> report --tab reports --index 2
"$WOS_DIR/scripts/wosctl" --instance <name> report --tab starred --index 1
```

### Report Command Rules

- Supported tabs: `war`, `reports`, `starred`
- Supported indices: `1` through `5`
- `report` is the standard interface for reading battle reports as merged JSON
- If a visible inbox item is not a standard supported battle-report layout, treat it as a missing `wosctl report` variant

## Run Testcase

```bash
"$WOS_DIR/scripts/wosctl" --instance <name> run-testcase ./testcases/<name>.json
"$WOS_DIR/scripts/wosctl" --instance <name> run-testcase ./testcases/<name>.json --dry-run
```

### run-testcase rules
- Spec JSON must include `emulator.attacker.instance`, `emulator.defender.instance`, `attacker.troops`, `defender.troops`.
- Heroes in the spec are optional; if omitted, no heroes are deployed.
- Note spec JSON must *NOT* contain stats or hero skill levels. 
- After the battle, hero names from the report are automatically enriched with skill levels from `data/player_hero_skills.json` before saving the testcase.
- Actual stats are extracted from the battle report.
- Useful testcases must contain all necessary data for the simulator to predict the outcome of an identical battle. The spec cannot tell the emulator what stats to use or dictate what level skills the heroes have, so the simulator must mimic the real battle conditions as closely as possible.
- Testcase is written to the simulator repo under `testcases/emulator_verified/<test_id>.json`.
- Simulator is run automatically and `sim_result` is populated.
- Use `_nc` suffix in the filename for deterministic (≤t6) testcases to avoid 100-repeat mode in `check_testcases.py`.

### Important considerations surrounding testcases:
- Testcases contain results of real battles that occurred in game and the exact army conditions of both sides at the time the battle took place. That last part is important.
- The same spec can produce either a new testcase, or an additional result for an existing testcase depending on whether any stats or other attributes have changed between their execution.
- Testcases MUST NOT be altered. They are a ground truth observation. If they are determined to be corrupted or outdated they may be retired, but replacing them should be done by allowing the spec to run again making a new observation from which to create a new testcase.
- Well designed testcases should have high signal to noise ratio. That means that ideally the result should not be too one sided - aim for the winner to take 50+% casualties and at least 100 in absolute figures. If you have a testcase where the winner takes only 5-10 casualties, it is easy for even quite large errors to be missed as in absolute terms 10% extra casualties is only 1 more injured troop.
- Avoid using thousands of troops in testcases in general just so as to avoid having to spend too much time healing - find a reasonable balance.
- Prioritise first testing all heroes in isolation targeting those with greatest uncertainty first. Covering a wider set of scenarios and getting them "close" is more useful than getting a narrower set perfect. You can always revisit and refine at a later date.
- If you encounter heroes that do not exist in the simulator, do attempt to create them.

## Capture Hero Skills

```bash
"$WOS_DIR/scripts/wosctl" --instance <name> capture-hero-skills
```

Navigates to the Heroes screen, reads all hero skill levels, saves to `data/player_hero_skills.json` under the instance name. Re-run whenever heroes are levelled up.

## Deploy Army

```bash
"$WOS_DIR/scripts/wosctl" --instance <name> deploy-army ./armies/<name>.json --tile-x 120 --tile-y 300
"$WOS_DIR/scripts/wosctl" --instance <name> deploy-army ./armies/<name>.json --tile-x 120 --tile-y 300 --mode attack
```

## Ensure Alliance

```bash
"$WOS_DIR/scripts/wosctl" --instance <name> ensure-alliance ARK
"$WOS_DIR/scripts/wosctl" --instance <name> ensure-alliance BBQ
```

Idempotent — checks the current alliance via OCR and switches only if needed. Returns JSON with `switched: true/false` and the alliance details. Handles three cases: already in target (no-op), in a different alliance (leave + join), not in any alliance (join).

Per-instance battle and heal alliances are configured in `config.json` (under the `instances` key).

## Recall Camp

```bash
"$WOS_DIR/scripts/wosctl" --instance <name> recall-camp
```

Navigates to world map and taps the recall button to recall all encamped/marching troops. Silently succeeds if no troops are encamped (recall button not found). Use after a failed `run-testcase` to clean up the defender army before retrying.

## Heal Troops

```bash
"$WOS_DIR/scripts/wosctl" --instance <name> heal
```

### Heal Command Rules

- Switches to the instance's configured `heal_alliance` (from `config.json` under the `instances` key) for alliance autohelp.
- Heals all wounded troops in batches of 85, using alliance Help for instant completion.
- After healing, returns to `--home-alliance` if provided, otherwise the alliance the player was in before healing.
- Errors if no `heal_alliance` is configured for the instance.

## Shell (last resort)

```bash
"$WOS_DIR/scripts/wosctl" --instance <name> shell input tap 360 640
```

Raw ADB shell passthrough. Use only when no other `wosctl` intent covers the need.

## Runtime Notes

- `scripts/wosctl` carries inline `uv` script metadata and will use `uv run --script` when `uv` is available.
- `.venv/` is only a fallback for environments without `uv`.
- Tesseract is expected at `/home/linuxbrew/.linuxbrew/bin/tesseract`.
