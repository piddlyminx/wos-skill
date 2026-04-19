# Battle Mechanics

## Core Physics --- Confirmed Correct

The core battle round-by-round loop is **correct and must not be rewritten**. Deterministic (no-RNG) battles match the game **exactly** down to single survivor counts. RNG battles agree within a few percent (expected bounds of randomness). Given 40+ test suites passing at <2% average error, the core logic is validated.

## Battle Loop

The WOS battle engine runs a turn-based loop (max 1500 rounds). Each round:

1. **Skill activation** --- Each hero's skills are checked against their activation conditions (probability, frequency, troop-type requirements).
2. **Benefit application** --- Active skill effects modify damage/defense coefficients for the round.
3. **Damage calculation** --- Each troop type deals damage to opposing troops based on the modified coefficients.
4. **Casualty resolution** --- Losses are deducted from troop counts. The battle ends when one side is eliminated.

## Troop Types

Three types: **Infantry**, **Lancer**, **Marksman**. Each has independent attack, defense, lethality, and health stats. Troop power per type is tracked separately.

## Hero Class Constraint (CRITICAL for spec design)

**Each side may have at most 1 hero of each class.** WOS enforces this at the game level; the emulator will reject an invalid lineup. The three hero classes are:

- **Infantry**: Ahmose, Flint, Hector, Jeronimo, Logan, Natalia, Sergey, WuMing
- **Lancer**: Jessie, Ling, Lumak, Mia, Molly, Norah, Patrick, Reina, Renee
- **Marksman**: Alonso, Bahiti, Greg, Gwen, Jasser, Lynn, Seo-yoon, Wayne, Zinman

(Source: verified by game emulator runs in WOS-96. Prior list was incorrect — Norah/Greg/Lynn/Zinman were misclassified.)

Before writing any multi-hero combo spec, verify that no two heroes on the same side share a class. This is the single most common source of invalid specs.

## 1v1 Symmetry

In 1v1 battles (what wosctl runs), attacker vs defender role does NOT matter. The result is identical regardless of who attacks and who defends. Winner is whichever team kills the other first --- no positional advantage.

## Stat Bonuses

Each side has stat bonuses (e.g., `infantry_attack: 1774.5`) visible in the Battle Report's Stat Bonuses section. These are **point-in-time snapshots** reflecting the player's exact state at the moment of battle (research + facilities + hero bonuses + buffs). They are captured via OCR and used as-is by the simulator --- never re-derived.

## Stat Stacking Rules

- Buffs of the **same type usually ADD** (e.g., two attack buffs stack additively).
- The "op" codes in skill effect definitions control this. Effects with the same op code add.
- **Different buff types MULTIPLY** (e.g., attack x lethality).
- This means `1.25^4 > 1 + 0.25*4` --- variety of buff types beats stacking one type.
- Common misconception: "high defense when defending, high attack when attacking" --- **FALSE** in WOS.

## Damage Coefficient Formula

Each round, each unit type's damage is multiplied by a coefficient built from three layers:

```
final_coef = base * (extra + normal_only - 1)
```

- **base** --- Standard buffs/debuffs (the default bucket for most hero effects).
- **normal_only** --- Effects flagged `only_normal` in their `special` field. Only affect the normal attack, not extra attacks. Currently only Reina uses this.
- **extra** --- Extra-attack effects (`extra_attack: true`). Bonus attacks on top of the normal hit.

The combination is **additive** between normal_only and extra, not multiplicative. This ensures `only_normal` buffs don't leak into extra-attack damage.

Each layer is computed as:

```
layer_coef = (damageUp x oppDefenseDown) / (defenseUp x oppDamageDown)
```

Each component is a multiplicative product of all active effects of that type, grouped by `effect_op`.

### Extra attacks against non-primary targets

Extra-attack benefits can target enemy types beyond the primary target, controlled by `benefit_vs`:

- `benefit_vs: "target"` --- extra attack hits primary target only (Mia, Molly, Bahiti, etc.)
- `benefit_vs: "all"` --- extra attack fans out to ALL enemy types (Norah S2)
- `benefit_vs: "lancer"` etc. --- extra attack hits that specific type (Wayne S2)

After computing primary-target normal damage, `calc_round_kills` runs a second pass over all enemy types, evaluating extra-attack benefits via the normal `is_valid` check. Benefits with `benefit_vs: "target"` naturally fail for non-primary types.

### Dodge interaction

- `dodging = 2` (full dodge): `coef = 0` (all damage blocked)
- `dodging = 1` (normal-only dodge): `coef = base * (extra - 1)` (normal attack blocked, only extra attacks land)
- `dodging = 0` (no dodge): `coef = base * (extra + normal_only - 1)` (full formula)

## Non-Linear Dynamics (sqrt(troops) Effect)

WOS uses sqrt(troops) to determine the power of a unit_type's remaining toops. In **close/tipping-point battles** (where the winner barely wins), small skill buffs can trigger complete winner flips due to non-linear amplification. This is an inherent property of both the game and the model.

**This is NOT a valid explanation for simulator divergence.** Both the game and simulator implement the same mechanics. If results diverge, the cause is a difference in skill implementation, not the dynamics model itself. Do not use "dynamics amplification" as a root-cause explanation.

---

Part of the WOS Knowledge Base. Update this file when you discover relevant insights. Always update KNOWLEDGE_INDEX.md if you change the scope of this document.
