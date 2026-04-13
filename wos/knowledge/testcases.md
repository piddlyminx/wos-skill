# Testcase Methodology

## Spec vs. Testcase

- A **spec** (`testcases/*.json` in the wos skill) defines the battle setup: which emulator instances, troop compositions, and hero assignments. Specs do NOT contain stats or hero skill levels.
- A **testcase** (`testcases/emulator_verified/*.json` in the simulator repo) is the result: spec + actual stats from the battle report + game results + simulator results.

## Why Testcases Are One-Way

Stats are point-in-time snapshots. If a player researches something, upgrades a facility, or changes buffs, the stats change. You can never re-run a game battle and get the same stats. Every testcase is a **one-shot experiment**. If the data looks bad, the only fix is to run a new battle.

## Testcase Integrity Rules

1. **Never alter testcases.** They are ground truth. If corrupted or outdated, retire and re-run the spec.
2. **Same spec, different results.** If stats or hero skill levels have changed, the spec produces a new testcase.
3. **`_nc` suffix** = deterministic (no chance skills). Single game run is sufficient.
4. **No `_nc` suffix** = RNG-dependent. Multiple game runs needed.

## Designing Good Testcases

- **Signal-to-noise ratio is everything.** The winner should take 50%+ casualties and at least ~100 absolute casualties. Low-casualty battles (5% losses on 600 troops) compress errors into noise.
- **Army size: 200-500 troops.** Large enough for signal, small enough to avoid excessive healing time.
- **Solo hero tests first.** A solo hero test validates ALL of that hero's skills in isolation --- high value, low cost.
- **Single-troop-type tests for mechanic isolation.** When investigating specific skill effects (splash, targeting), use one troop type to eliminate confounding factors.
- **Per-unit-type casualty counts beat aggregate survivors.** Battle detail screens show which troop types took casualties from which skills --- more diagnostic than total survivor counts.
- **Combo tests second.** 2-3 hero combinations catch interaction bugs (stacking, trigger conflicts, order-of-operations).
- **Deterministic when possible.** If a hero has no chance-based skills, a single deterministic test is definitive. Use `_nc` suffix.

## Output Testcase Schema (Enriched Format)

When `run-testcase` completes, the output testcase is richer than the input spec --- it contains captured stats, player names, sim results, and game results:

```json
[{
  "test_id": "hero_solo",
  "description": "...",
  "attacker": {
    "name": "[TAG]PlayerName",
    "heroes": {},
    "troops": { "lancer_t8": 300 },
    "stats": {
      "inf":  { "attack": 66.1, "defense": 61.4, "lethality": 23.3, "health": 26.4 },
      "lanc": { "attack": 68.6, "defense": 62.6, "lethality": 26.3, "health": 21.1 },
      "mark": { "attack": 69.1, "defense": 58.9, "lethality": 25.8, "health": 21.5 }
    },
    "joiner_heroes": {}
  },
  "defender": { "...same structure..." },
  "sim_result": { "attacker": 0, "defender": 186 },
  "game_report_result": [{ "attacker": 0, "defender": 186 }]
}]
```

The stats are **immutable snapshots** captured via OCR from the war report. They are used as-is by the simulator --- never re-derived. For repeat runs, new game results are appended to the `game_report_result` array.

## Specifying Battle Tests for QA (Delegation Checklist)

When creating subtasks for QA Engineer, always include:
1. Which hero(es) to test and on which side (attacker/defender)
2. Which accounts to use
3. Troop composition and count --- aim for 200-500 starting troops with 50%+ expected casualties
4. Whether it is deterministic (single run) or RNG (needs 5+ game battles and `--repeat 100` sim runs)
5. What you are specifically trying to validate (a particular skill effect, interaction, edge case)

## Delegating Fixes to Simulator Engineer

When a testcase shows a confirmed simulator divergence (data quality ruled out), provide:
- The specific hero and skill that diverges
- The observed vs expected behavior
- The testcase data showing the divergence
- Your hypothesis about the root cause
- A reminder: **the core battle physics are correct. Do not rewrite BattleRound logic.** The fix is almost certainly in skill definitions (CSV/JSON) or how a specific skill effect is applied.

## Interpreting Results

- **< 3% average error**: Acceptable for RNG heroes. Mark as passing.
- **3-5% average error**: Borderline. Verify enough game runs were collected. May need more data.
- **> 5% average error**: Investigate. But check testcase data quality FIRST.

## Regression Rule

No change is accepted that increases overall error. Full regression suite must pass before any code change is merged:
```bash
python3 check_testcases.py --matching all --repeat 100
```

---

Part of the WOS Knowledge Base. Update this file when you discover relevant insights. Always update KNOWLEDGE_INDEX.md if you change the scope of this document.
