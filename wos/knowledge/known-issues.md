# Known Issues & Resolved Investigations

Keep this file current. When an issue is resolved, move it to Resolved with a summary. When a new divergence is found, add it here.

## Active Issues

- **Wayne s1 solo (every-4-turns timing fix side effect)** --- 5.16% error (threshold ❌). Wayne S1 (`Thunder Strike`, every 4 turns, no `skill_first_round`) was previously firing at turns 1,5,9 (old `_start=0` bug). After fixing the systematic modulo-0 bug in `Skill.py` (WOS-92), it now correctly fires at turns 4,8,12. Error moved from 4.96% (just passing) to 5.16% (just failing). Root cause of the 5% residual is unknown — may be battle dynamics similar to Alonso TC1, or may need richer game data. **Do not revert the `Skill.py` fix; the timing correction is correct.**

- **Alonso TC1 dynamics** --- 15.85% error. Non-linear sqrt(troops) battle dynamics over-amplify chance skills in close battles. When Onslaught, Iron Strength, and Poison Harpoon all fire simultaneously (~17% chance/round), combined effect is 2.37x advantage; non-linearity magnifies this in close battles. Fix would require adjusting the sqrt(troops) model --- high risk affecting all testcases. **Not a skill definition error.**
- **Alonso solo** --- 7.29% error but statistically inconclusive (p=0.26, needs 40+ game runs).
- **Reina** --- ~3.2% error, borderline. May need more game data.
- **Attack-frequency timing** (`frequency_type: 'attack'`) --- The current `trigger_condition` check fires when `cumul_attacks[ut] % N == 0`, which also fires at cumul=0 (before any attacks have occurred). This means `every-N-attacks` skills trigger one round too early. Affects Lynn's Oonai Cadenza (every 3 marksman attacks) and similar attack-gated skills. A fix was attempted (commit `a348b48`) and reverted (commit `2c46307`) because the architecture was wrong --- the check belongs in `trigger_condition` not `r_skill_condition`. Correct fix: gate on `cumul_attacks[ut] > 0 and cumul_attacks[ut] % N == 0`. **Open --- any developer touching attack-frequency skills must be aware of this.** lynn_solo is at ~5.55% error partly due to this.

## Resolved (Reference Only)

- **Modulo-0 bug in every-N-turns skill timing (WOS-92)** --- `Skill.py` used `_start = 0` as the default for skills without `skill_first_round`, making `(_round - 0) % N == 0` always fire at round 0 (turn 1), one turn too early. Fixed in `Skill.py`: default `_start` is now `frequency_value - 1`, so skills fire at turns N, 2N, 3N, ... Affected: Renee Dreamslice (every 2 turns), Jeronimo E Xpert swordsmanship (every 4 turns), Wayne Thunder Strike (every 4 turns). Skills that already had `skill_first_round` set (Renee skills 1&2) were unaffected. Overall error improved from ~1.48% → ~1.32%.



- **High power-space delta on lopsided testcases (WOS-88)** --- `renee_solo_nc` (17%), `norah_s2_splash_A` (10%), `reina_logan_combo_v3` (8%), `norah_solo` (6%) all have high power-space delta with low survivor error. Root cause: mathematical artifact of `atanh` amplification near ±1 when the winning side retains >80% of initial troops. **Not a composition error, not a simulator bug.** Game reports don't include per-troop-type survivor data anyway. See debugging.md for full analysis.

- **Norah S2 93% error (WOS-53/54)** --- Root cause was **corrupted testcase metadata**, not a simulator bug. `wosctl` defaulted Norah's skill levels to S1=5/S2=5/S3=5 (former fallback for unknown heroes) while actual game battles used S1=1/S2=1/S3=0. With correct skill levels, testcase passes at ~0.47%. **EXPUNGED THEORY: Any claim that the 93% error was caused by "dynamics amplification" or a "stacking bug" is WRONG. Do not reference these theories.**
- **Norah S2 extra_vs_all targeting (WOS-27)** --- Fully confirmed: Sneak Strike hits ALL enemy troop types simultaneously when it procs (primary and non-primary). The `extra_vs_all` implementation is correct.
- **Alonso benefit_for bug (WOS-28)** --- `benefit_for: "trigger"` should have been `benefit_for: "all"` for Onslaught. Only infantry was receiving the Lethality buff. Fixed.
- **Alonso Iron Strength regression (WOS-24)** --- Commit `a59b136` incorrectly changed `trigger_for` from `marksmen` to `all`, tripling effective proc rate. Four fields in `Alonso.json` were corrected.
- **Lynn solo (WOS-3)** --- Not a simulator bug. Methodology artifact from insufficient repeats + single game data point. With `--repeat 100+`, error is ~4.27%.
- **Jessie S1 (WOS-50)** --- Reported as 38.7% error using wrong metric. Correct framework metric: 3.33% (within tolerance). `effect_op=101` DamageUp applied correctly.

---

Part of the WOS Knowledge Base. Update this file when you discover relevant insights. Always update KNOWLEDGE_INDEX.md if you change the scope of this document.
