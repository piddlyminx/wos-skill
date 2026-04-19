# Battle Spec Design Patterns

This file captures reusable patterns for authoring battle specs --- the JSON files that drive the spec-to-testcase pipeline.

## Pipeline Continuity (Critical)

The single most important discipline: **always have the next batch of specs ready before the current batch finishes running.** QA idle time = pipeline stall. Design specs while QA Engineer is running battles, not after results come back.

## Pre-Spec Checklist

Before writing a new spec:

1. **Check existing coverage** --- Look in `testcases/emulator_verified/` for `{hero}_solo*.json`. If it exists and passes (<5% error), the solo phase is done; move to combo or skip.
2. **Verify hero availability** --- Confirm the hero is on the intended instance. Use `player_hero_skills.json` as the source of truth. Some heroes are only available on one account; check before writing a spec. Heroes not available on either account should be deprioritized.
3. **Identify skill type** --- Check if the hero has any `skill_is_chance: true` skills. If yes, plan for 5+ game runs (up to 10 if high variance, 3+ chance skills). If none -> single run is definitive; use `_nc` suffix.
4. **Check hero class compatibility** --- For multi-hero specs, confirm no two heroes on the same side share a class (Infantry / Lancer / Marksman). WOS allows at most 1 hero per class per side. Violating this produces an invalid spec the emulator cannot run. See `battle-mechanics.md` for the class list.
5. **Capture fresh skills** --- Confirm `wosctl capture-hero-skills` has been run recently for both accounts before the battle batch starts.
6. **Use t6 troops**. Above t6 troops start to have chance skills. This introduces unnecessary noise that makes the test results less reliable.

## Spec Design Template

Standard solo test: 

```json
{
  "test_id": "hero_solo",
  "description": "Hero solo validation --- all skills isolated",
  "emulator": {
    "attacker": { "instance": "<attacker_instance>" },
    "defender": { "instance": "<defender_instance>" }
  },
  "attacker": {
    "heroes": {},
    "troops": { "infantry_t6": 300, "lancer_t6": 300, "marksman_t6": 300 }
  },
  "defender": {
    "heroes": { "HeroName": {} },
    "troops": { "infantry_t6": 300, "lancer_t6": 300, "marksman_t6": 300 }
  }
}
```

Adjust troop count so the winner takes 50%+ casualties. 

## Spec Naming Conventions

| Pattern | Meaning |
|---|---|
| `hero_solo.json` | Hero alone on one side; no heroes on other side |
| `hero_solo_nc.json` | Same but no chance-based skills -> deterministic, single run |
| `hero1_hero2_combo.json` | Two heroes on one side, testing interactions |
| `hero_s2_inf_only_A.json` | Mechanic-isolation test (specific skill, single troop type) |

Files with `.disabled` extension are broken/retired testcases --- do not use. Files with `.stale_troops` extension have outdated troop data --- retire and re-run.

## Hero Validation Progression

1. **Solo first** --- validates all of a hero's skills in one shot. High value, low cost.
2. **Mechanic isolation** (if needed) --- some skills only have effects either for or vs certain troop types. Running strategic single-troop-type specs is often an effetive way to isolate a certain skill. Particularly useful when it is unclear which skill is causing a divergence.
3. **Combo tests second** --- 2-3 hero combinations. Only run after solo passes cleanly.
4. **Combo triggers**: if a hero has a skill that buffs friendly troop types, test with a complementary hero whose troop type would receive the buff.

## Batch Design Strategy

When designing a batch, aim for:
- 3-5 specs per batch, ordered from most-isolating to most-complex
- Mix of heroes from the Tier 1 priority list with the fewest existing testcases
- At least one `_nc` (deterministic) spec per batch --- these run fast and give quick validation signal

## Account Assignment Shorthand

- Check the available heroes and their skill levels in `data/player_hero_skills.json`. It often makes sense to assign the weaker player to be the one with hero(es) in a test and leave the other with just plain troops.
- Instance names are configured in `config.json` --- do not hardcode them in knowledge docs.

---

Part of the WOS Knowledge Base. Update this file when you discover relevant insights. Always update KNOWLEDGE_INDEX.md if you change the scope of this document.
