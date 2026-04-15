# Known Issues & Resolved Investigations

Keep this file current. When an issue is resolved, move it to Resolved with a summary. When a new divergence is found, add it here.

## Active Issues

- **Alonso solo** --- Apparent ~8–13% error (10 game runs, extreme variance: 282–1550 attacker survivors, std≈424). **Statistically inconclusive** — 95% CI on game mean: (842, 1367), sim prediction of ~1253 is within the CI. Needs 40+ runs to determine if divergence is real. S2 config confirmed correct (WOS-99). OppDamageDown confirmed correct in chance-free cases (Ling/Lumak both pass at 0.03%). S3 (Poison Harpoon, `extra_attack: true`) is the main driver of variance: disabling it reduces sim std from ~327 to ~94. If a real divergence is confirmed with more runs, the investigation should focus on S3 and the multi-skill interaction.
- **Reina** --- ~3.2% error, borderline. May need more game data.
## Resolved (Reference Only)

- **Wayne Fleet benefit_for bug (WOS-113)** --- Fleet (S3) used `benefit_for: "all"` with `duration: {type: "attack", value: 1}`. In mixed-troop battles, the benefit was consumed by the first unit type in iteration order (infantry), stealing crits from lancers/marksmen. Since infantry had ~3.4x weaker attack than marksmen, this drastically reduced Fleet's effective damage contribution. Fixed: changed `benefit_for` from `"all"` to `"trigger"` in Wayne.json so each type's crit is scoped to itself. Also cleaned testcase data: removed 1 corrupt entry (defender inf lethality OCR'd as 7.0), merged 2 identical-stats entries. Final result: wayne_mixed_solo **4.85% ✅** (11 game runs across 2 entries). No effect on single-type battles (wayne_s1_solo stays at ~1.1%). **Pattern to watch for: any skill with `benefit_for: "all"` + `duration: attack, 1` + `trigger_for: "all"` will have the same benefit-stealing bug in mixed-troop scenarios.**

- **Wayne s1 solo (every-4-turns timing fix side effect, WOS-92)** --- Was 5.16% error after the modulo-0 bug fix in `Skill.py`. Re-tested 2026-04-14 (WOS-111 regression): error is now **1.06% ✅**, well within threshold. Likely resolved by subsequent code changes (uncommitted Skill.py edits visible in git status at the time of re-test). Keep monitoring; if it regresses, the root cause was the 5% residual noted in WOS-92.

- **Attack-frequency timing (WOS-106)** --- `trigger_condition` fired when `cumul_attacks[ut] % N == 0`, which is true at cumul=0 (before any attacks). Added `cumul_attacks[ut] > 0` guard. lynn_solo improved from ~4.4% to ~3.5%. Affects Lynn S3 (every 3 marksmen attacks), Norah S3 (every 5 lancer attacks), Gwen S2/S3 (every 5/4 marksmen attacks). No regressions.

- **Hector Rampant S2 geometric decay (WOS-94)** --- `pct_value_pct_decrease` formula in `Skill.py.correct_value()` was computing linear decay (`value * (1 - counter * pct/100)`) but the game description says "each attack's boost being 85% of the previous" (geometric). Linear formula went NEGATIVE for uses 7–9, actively reducing defender damage. Fixed in `Skill.py`: formula changed to `value * ((1 - pct/100) ** counter)`. hector_solo improved from 6.08% → ~2.7% ✅. Overall average improved from ~1.48% → ~1.26%.

- **Wu Ming S1 `only_non_normal` regression (WOS-94)** --- A prior session incorrectly changed Shadow's Evasion from `special: {}` (applies to all attacks) to `only_non_normal: true` (applies only to extra attacks). In the wu_ming_solo testcase there are no extra attacks, so S1 provided zero benefit, giving 9.56% error (sim 1781 vs game 1392). Reverted to `special: {}`. wu_ming_solo now passes at 0.69%.

- **Modulo-0 bug in every-N-turns skill timing (WOS-92)** --- `Skill.py` used `_start = 0` as the default for skills without `skill_first_round`, making `(_round - 0) % N == 0` always fire at round 0 (turn 1), one turn too early. Fixed in `Skill.py`: default `_start` is now `frequency_value - 1`, so skills fire at turns N, 2N, 3N, ... Affected: Renee Dreamslice (every 2 turns), Jeronimo E Xpert swordsmanship (every 4 turns), Wayne Thunder Strike (every 4 turns). Skills that already had `skill_first_round` set (Renee skills 1&2) were unaffected. Overall error improved from ~1.48% → ~1.32%.



- **High power-space delta on lopsided testcases (WOS-88)** --- `renee_solo_nc` (17%), `norah_s2_splash_A` (10%), `reina_logan_combo_v3` (8%), `norah_solo` (6%) all have high power-space delta with low survivor error. Root cause: mathematical artifact of `atanh` amplification near ±1 when the winning side retains >80% of initial troops. **Not a composition error, not a simulator bug.** Game reports don't include per-troop-type survivor data anyway. See debugging.md for full analysis.

- **Norah S2 93% error (WOS-53/54)** --- Root cause was **corrupted testcase metadata**, not a simulator bug. `wosctl` defaulted Norah's skill levels to S1=5/S2=5/S3=5 (former fallback for unknown heroes) while actual game battles used S1=1/S2=1/S3=0. With correct skill levels, testcase passes at ~0.47%. **EXPUNGED THEORY: Any claim that the 93% error was caused by "dynamics amplification" or a "stacking bug" is WRONG. Do not reference these theories.**
- **Norah S2 fan-out targeting (WOS-27)** --- Fully confirmed: Sneak Strike hits ALL enemy troop types simultaneously when it procs (primary and non-primary). Now implemented via `benefit_vs: "all"` on the extra-attack effect, which the non-primary loop picks up naturally through `is_valid`. The old `extra_vs_all` special field and post-processing hack have been removed.
- **Alonso S2 (Iron Strength) config confirmed (WOS-99)** --- `benefit_vs: "target"` is correct despite skill description saying "all enemies". Tested all four combinations of `benefit_vs` (target/all) × `skill_round_stackable` (true/false) with 200-repeat simulations. `benefit_vs: "all"` produces catastrophic error on `alonso_solo` (8% → 184%). `skill_round_stackable` has negligible impact (1.82% vs 1.82% on `alonso_attacker_600_all`). Keep current config: `benefit_vs: "target"`, `skill_round_stackable: true`. The remaining ~8% error on `alonso_solo` is not attributable to S2 config.
- **Alonso benefit_for bug (WOS-28)** --- `benefit_for: "trigger"` should have been `benefit_for: "all"` for Onslaught. Only infantry was receiving the Lethality buff. Fixed.
- **Alonso Iron Strength regression (WOS-24)** --- Commit `a59b136` incorrectly changed `trigger_for` from `marksmen` to `all`, tripling effective proc rate. Four fields in `Alonso.json` were corrected.
- **Lynn solo (WOS-3)** --- Not a simulator bug. Methodology artifact from insufficient repeats + single game data point. With `--repeat 100+`, error is ~4.27%.
- **Jessie S1 (WOS-50)** --- Reported as 38.7% error using wrong metric. Correct framework metric: 3.33% (within tolerance). `effect_op=101` DamageUp applied correctly.

---

Part of the WOS Knowledge Base. Update this file when you discover relevant insights. Always update KNOWLEDGE_INDEX.md if you change the scope of this document.
