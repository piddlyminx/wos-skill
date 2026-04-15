# Hero Skills

## Structure

Each hero has **2 or 3 skills** (S1, S2, S3), each with levels 1-5. Skills are defined in:
- **CSV master registry**: `skills/Fitz_hero_skills.csv` (semicolon-delimited)
- **Per-hero JSON**: `assets/hero_skills/<HeroName>.json`

## Skill Properties

| Property | Meaning |
|---|---|
| `skill_permanent` | `true` = activates once at battle start, lasts forever. `false` = conditional, re-checks each round. |
| `skill_is_chance` | Whether the skill has a base probability check before activating. |
| `skill_probability` | Activation chance (0-100). Only relevant if `skill_is_chance` is true. |
| `skill_troop_type` | The troop type associated with the skill. **If that troop type is eliminated, the skill deactivates.** |
| `skill_round_stackable` | Whether multiple instances can activate in the same round. |
| `skill_frequency` | Timing: `frequency_type` (`turn`/`attack`/`NONE`) + `frequency_value` (skip pattern). |

## Skill Frequency Types

- **`turn`** --- Checked once per battle round. `frequency_value` = N means activates every Nth round.
- **`attack`** --- Checked once per attack action within a round. `frequency_value` = N means every Nth attack.
- **`NONE`** --- No frequency constraint (permanent skills typically).

## Effect Properties

Each skill contains one or more **effects**:

| Property | Meaning |
|---|---|
| `trigger_for` | Who triggers: `once`, `all`, `first`, `inf`, `lanc`, `mark`, `friendly` |
| `trigger_vs` | Against whom: `all`, `inf`, `lanc`, `mark` |
| `benefit_for` | Who benefits: `all`, `trigger`, `inf`, `lanc`, `mark`, `friendly` |
| `benefit_vs` | Against whom the benefit applies |
| `effect_type` | `DamageUp`, `DefenseUp`, `OppDamageDown`, `OppDefenseDown`, `Dodge` |
| `effect_op` | Operation code (see below) |
| `extra_attack` | If `true`, generates an additional attack roll |
| `effect_values` | Per-level modifier values (array indexed by skill level) |
| `effect_duration` | How long the effect lasts: `type` (`turn`/`attack`/`-1` for permanent), `value`, `lag` |

## Targeting Keywords (Critical)

- **"All"** = all your troops (infantry + lancers + marksmen)
- **"Friendly"** = all your troops EXCEPT the triggering unit's troop type
- Always verify `benefit_for` targets the right scope --- `"trigger"` means only the triggering unit's type, `"all"` means all troop types

## `trigger_for` Subtle Values

- **`all`** --- Effect triggers for each unit type independently. Each creates its own benefit. Preferred over `once` for skills that buff all troops --- use with `benefit_for: "trigger"` so each unit type gets a correctly-scoped benefit.
- **`first`** --- Effect can only be ATTEMPTED once per round; stops all further checks after the very first attempt regardless of whether it activates. Use when the skill itself should fire at most once per round no matter how many unit types attack.
- **`once`** --- **Deprecated; replaced with `"all"` + `benefit_for: "trigger"`.** Previously, `once` created a single shared benefit for all unit types. This caused `benefit_vs: "target"` to lock `vs_units` to one enemy type at creation time, breaking targeting for other unit types. The replacement creates per-unit benefits with correctly scoped `vs_units`.

## Effect Operation Codes (`effect_op`)

The `effect_op` value is an **opaque grouping key** used in the damage coefficient calculation. It controls how effects stack with each other:

- Effects with the **same `effect_op` AND same `effect_type`** are **combined** (added together for non-chance effects, max for chance-based effects).
- Effects with **different `effect_op` values** remain in separate groups and are **multiplied** together in the final coefficient.

This is the only thing `effect_op` controls. It does NOT control extra_attack behavior, duration, or any other mechanic --- those are handled by their own explicit fields (`extra_attack`, `effect_duration`, `special`, etc.).

Common values in use: `101` (35 effects), `111` (13), `102` (8), `201` (5), `113` (4), `202` (3).

## Extra Attack Targeting (`benefit_vs`)

Extra-attack fan-out is controlled by the standard `benefit_vs` field, not a special flag. The `benefit_vs` value determines which enemy types the extra attack hits:

- `"target"` --- hit primary target only (e.g. Mia S2, Molly S2, Bahiti S2, Alonso S3)
- `"all"` --- hit ALL enemy types simultaneously (e.g. Norah S2, Gwen S3)
- specific type (`"lancer"`, `"marksmen"`, etc.) --- hit that type only (e.g. Wayne S2)

Fan-out to all enemy types has been **confirmed correct** via in-game battle detail analysis:
- Primary target IS hit by extra damage (confirmed: Norah S2 in infantry-only scenario attributed S2 kills to infantry --- the only target available)
- Non-primary types ARE also hit (confirmed: marksmen took casualties from lancer-based S2 while infantry line was still standing --- impossible without fan-out)

**Important:** When an extra attack should only hit whoever the unit is already fighting, use `benefit_vs: "target"`, NOT `"all"`. Using `"all"` causes the extra attack to fan out to all enemy types.

## `benefit_vs` Semantics for Regular Effects

For non-extra-attack effects, `benefit_vs` controls which enemy types the benefit is valid against:

- **Offensive effects** (`DamageUp`, `OppDefenseDown`): use `"target"` --- the buff applies to damage against whichever enemy you're fighting.
- **Defensive effects** (`DefenseUp`, `OppDamageDown`, `Dodge`, `StatBonus`): use `"all"` --- the defense works regardless of which enemy is attacking you.
- **Exception: Alonso S2 (Iron Strength)** uses `"target"` despite being `OppDamageDown` --- empirically verified (WOS-99). Using `"all"` produces 184% error.

## `special` Field Mechanisms

The `special` dict on an effect enables advanced behaviors not covered by the standard fields. All are optional; absent keys are ignored.

| Key | Meaning |
|---|---|
| `hp_threshold` | `{"above": N}` or `{"below": N}` --- skill only fires when own army HP% is above/below N |
| `only_normal` | If present, benefit applies to normal attacks only --- extra attacks bypass it. Used to limit dodge vs. extra-attack interaction |
| `onDefense` | If `true`, skill triggers on the opponent's attack phase (defensive timing) rather than your attack phase |
| `role` | `"attacker"` or `"defender"` --- gate the skill by the fighter's battle role (used by widget/stat-bonus skills) |
| `effect_evolution` | Decaying benefit: `category` = `effect_decrease` with sub-types `pct_value_fixed_decrease` (fixed reduction per attack/round) or `pct_value_pct_decrease` (percentage reduction per attack/round). Also `effect_is_total_damage` (subtracts 100 from value to get bonus-over-baseline). |

## Skill Activation --- Two-Phase Check

Each round, skill activation is evaluated in two sequential passes:

1. **`r_skill_condition` (once per skill per round)** --- Checks stackability, troop-type presence, round frequency, first/last round limits, and the skill-level probability roll. If this fails, the skill is not armed for this round.

2. **`r_effect_condition` + `trigger_condition` (per unit-type per round)** --- For each attacking unit type, checks whether the armed effect can actually trigger: unit type still alive, target unit type alive, attack-frequency gate, `trig_for_unit` match, and any per-effect probability roll.

Debugging tip: if a skill fires less than expected, check phase 1 first. If it fires but for wrong unit types, check phase 2.

## Chance-Based Effect Deduplication (Multi-Hero Scenarios)

When multiple chance-based benefits from the **same skill** are active in the same round (can occur with repeated-fire or multi-hero combos), the simulator takes the **MAX value** rather than summing them. This prevents the same chance proc from double-counting in the damage formula. Non-chance effects stack normally (additive within op-group).

## Dodge Mechanism

Two dodge levels are tracked:
- `dodging = 1` (`only_normal` dodge) --- Blocks the normal-attack component only; extra attacks still land.
- `dodging = 2` (full dodge) --- Blocks all damage (normal + extra) for that unit-vs-unit pairing.

If the opponent's dodge effect has `only_normal` set, it grants level-1 dodge; otherwise level-2.

## Hero Skill CSV Format

The file `Fitz_hero_skills.csv` is semicolon-delimited. Key fields:
- Hero name, skill number, description text
- Troop type (which troop type the skill applies to)
- Timing (when the skill triggers: per_round, per_attack, battle_start, etc.)
- Frequency (how often: every_round, once, etc.)
- Probability (chance-based skills: 0.0 to 1.0)
- Effect type and values (by skill level 1-5)

## Implementing a New Hero

When adding a hero that has no skill definitions yet:

1. Source skill parameters from the game (captured screenshots, in-game skill descriptions).
2. Cross-reference with `Fitz_hero_skills.csv` if the hero exists there.
3. Create `assets/hero_skills/<HeroName>.json` with skill definitions.
4. Add entries to the CSV if missing.
5. Create at least one unit test in `testcases/heroes_unittests/`.
6. Request emulator verification from QA (via Battle Spec Engineer) before considering the hero "supported."

## Skill Implementation Principles

1. **Follow literal skill text.** When the game says "20% extra damage vs all enemies," implement exactly that. No arbitrary scale factors or "balance adjustments."
2. **Chance rolls are per-unit-type, not per-troop.** A 20% chance skill rolls once per unit type per round, not once per individual troop. This was a critical misunderstanding in the Norah S2 investigation.
3. **Experiment iteratively.** Skill mechanics are reverse-engineered by trial and error. If the first interpretation doesn't match, try alternative readings.

---

Part of the WOS Knowledge Base. Update this file when you discover relevant insights. Always update KNOWLEDGE_INDEX.md if you change the scope of this document.
