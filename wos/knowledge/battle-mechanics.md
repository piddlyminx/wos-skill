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

- **Infantry** (e.g. Hector, Sergey, Norah, Philly, Greg)
- **Lancer** (e.g. Mia, Lynn, Alonso, Reina, Flint, Zinman, Molly)
- **Marksman** (e.g. Bahiti, Logan, Gwen, Jeronimo, Wu Ming, Wayne)

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

```
damage_coefficient = (damageUp x oppDefenseDown) / (defenseUp x oppDamageDown)
```

Each component is a multiplicative product of all active effects of that type.

## Non-Linear Dynamics (sqrt(troops) Effect)

The simulator uses a sqrt(troops) approximation model. In **close/tipping-point battles** (where the winner barely wins), small skill buffs can trigger complete winner flips due to non-linear amplification. This is an inherent property of the model, not a bug, but it means:
- Tipping-point scenarios amplify errors dramatically
- Small percentage changes in skill effects can cause disproportionate changes in outcomes
- This is the root cause of the Alonso TC1 issue (see known-issues.md)

---

Part of the WOS Knowledge Base. Update this file when you discover relevant insights. Always update KNOWLEDGE_INDEX.md if you change the scope of this document.
