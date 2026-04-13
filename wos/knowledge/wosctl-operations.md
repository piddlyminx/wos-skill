# Operational Guide: Using wosctl

## Golden Rules

1. **Always use `wosctl`.** Never run raw `adb` commands or `scripts/*.py` directly.
2. **Always specify `--instance <name>`.

## What `run-testcase` Does Automatically

You do NOT need to do these manually:
- **Healing**: If deploy fails due to insufficient troops, auto-heals and retries.
- **Alliance management**: Ensures both players are in their correct `battle_alliance` before the fight.
- **Hero skill enrichment**: Auto-runs `capture-hero-skills` and retries if a hero is missing from `player_hero_skills.json`. Hard-fails if still missing after capture attempt.

## wosctl Design Principles

1. **Actions are self-contained**: Each command establishes its own preconditions. There is no need to prepare the game state before running testcases.
2. **Actions are idempotent**: Running `ensure-alliance ARK` when already in ARK is fine.
3. **Actions self-verify**: Commands check completion visually. Don't add your own verification unless debugging.

## Common Workflows

### Running a Testcase End-to-End

```bash
wosctl --instance <name> run-testcase ./testcases/hero_solo.json  # full pipeline
```

### Reading Battle Reports

```bash
wosctl --instance <name> report --tab war --index 1      # single report
wosctl --instance <name> reports --tab reports --count 5  # batch capture
```

### Validating with the Simulator

```bash
cd ~/projects_wsl/wos/battle_sim/lib/wos-simulator/
python3 check_testcases.py --matching "hero_name*" --repeat 100 --combine-repeats
python3 check_testcases.py --matching all --repeat 100   # full regression
```

## Adding a New Hero (Template Registration)

When `run-testcase` fails because wosctl can't locate a hero in the Select Heroes popup, you need to register a portrait template:

1. **Capture the hero portrait PNG** (90x40px) from the Select Heroes popup at the correct crop coordinates. The grid layout in 720x1280 screen space: `row1_y=[645,685]`, `col1_x=[90,180]` (adjust row/col offsets per the hero's position in the grid).
2. **Save** to `templates/heroes/<HeroName>.png`. The filename must match the name in `data/hero_names.txt` (with spaces replaced by underscores).
3. **Add the name** to `data/hero_names.txt` if not already present (controls OCR name filtering).
4. Re-run `capture-hero-skills` on both instances to populate `player_hero_skills.json`.

Only do this when wosctl reports a template-not-found error. Do not create templates preemptively.

## Troubleshooting

- **Emulator not responding:** Check `wosctl status`. MuMuPlayer may need restarting on Windows side.
- **OCR misreads:** Hero names are filtered against `data/hero_names.txt`. Update if a new hero is added.
- **Stale skill levels:** Re-run `capture-hero-skills` after leveling up any hero.
- **Failed testcase mid-battle:** Run `recall-camp` on both instances, `heal`, then retry.
- **Non-standard report layout:** Treat as a missing `wosctl report` capability. Don't improvise.

---

Part of the WOS Knowledge Base. Update this file when you discover relevant insights. Always update KNOWLEDGE_INDEX.md if you change the scope of this document.
