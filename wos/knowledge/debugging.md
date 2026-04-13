# Debugging Methodology --- Check Data Before Code

When a testcase fails, there are exactly TWO possible causes:

## 1. Testcase Data is Bad (More Common Than You Think)

Check these FIRST, in order:

1. **Stale hero skill levels** --- Were skills refreshed with `wosctl capture-hero-skills` before the battle? Compare testcase skill levels against `player_hero_skills.json`. This is the **#1 cause of false divergences**.
2. **Troops in infirmary** --- Did the army actually deploy the specified number? Injured troops reduce the army.
3. **OCR errors** --- Screenshot parsing misread a number. Inspect captured screenshots with vision analysis.
4. **Battle spec mismatch** --- Did the correct heroes and troops actually fight? Check the battle report matches the spec.
5. **Insufficient sim repeats** --- For RNG battles, `--repeat 10` is NOT enough. Always use `--repeat 100` minimum.
6. **Insufficient game data** --- A single game battle is not statistically meaningful for RNG heroes. Need 5+ minimum, 40+ for reliable 5% validation on high-variance skills.
7. **Game update** --- Sometimes changes certain skills/mechanics, making old testcases no longer relevant.

## 2. Simulator is Inaccurate (Fix the Sim)

Only after ruling out ALL data issues, check these locations **in order of likelihood**:

1. **Hero skill CSV definitions** (`Fitz_hero_skills.csv`) --- Wrong timing, probability, effect values, troop type targeting. This is the **#1 source of divergences**.
2. **Per-hero skill JSON** (`assets/hero_skills/`) --- Incorrect skill level scaling, missing skills, wrong effect types.
3. **Skill effect application** (`Skill.py`) --- How a specific effect type is applied (e.g., `extra_vs_all` mechanism).
4. **Stat composition** (`StatsBonus.py`, `Fighter.py`) --- How buffs/debuffs stack and interact.
5. **Core battle loop** --- Almost never the problem. **NEVER rewrite `BattleRound.py` or `Fight.py`** --- they are proven correct.

## Error Metric Consistency

**Always use the framework's standard error metric**: `|sim - game| / winner_initial_count`. Do NOT use alternative denominators (like `|diff| / sim_result`). Using the wrong metric has caused false alarm escalations (WOS-50: reported as 38.7% error, actually 3.33%).

## Power-Space Delta: Expected Behavior for Lopsided Battles

The power-space delta metric uses `atanh((att_surv_ratio)^2 - (def_surv_ratio)^2)`. The `atanh` function has steep slopes near ±1, so **lopsided battles produce high power deltas even when the survivor error is small**.

Rule of thumb: If the winning side retains >80% of its initial troops, expect power-space delta to be 5–20% even for well-calibrated testcases. This is not a bug.

Verified examples (WOS-88):
- `renee_solo_nc`: 2.17% error → 17.13% power delta (def survival = 92.3%)
- `norah_s2_splash_A`: 1.97% error → 10.35% power delta (att survival = 89%)
- `reina_logan_combo_v3`: 1.18% error → 8.47% power delta (def survival = 92%)
- `norah_solo`: 3.16% error → 5.69% power delta (att survival = 67.7%)

Sensitivity: the same 13-troop absolute difference gives 2.25% power delta in a balanced battle vs 17.13% for a lopsided one.

**Power-space delta does NOT measure troop composition.** The testcase format only stores total survivor counts (no per-type breakdown), so composition errors cannot be detected with this metric. If you see high power delta, first check if the battle is lopsided before investigating a code bug.

## Statistical Significance Checklist

- 10 game runs -> std error ~ 134 troops -> barely detectable bias of 150 troops
- 40+ game runs -> reliable 5% validation for RNG battles
- 3+ chance skills -> expect ~400 troops standard deviation
- Error metric is inflated when sim occasionally picks a different winner than game (~207% for those rare runs)
- When sample sizes are small (<20), note that observed errors may be due to variance, not bugs

---

Part of the WOS Knowledge Base. Update this file when you discover relevant insights. Always update KNOWLEDGE_INDEX.md if you change the scope of this document.
