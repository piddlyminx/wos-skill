# Anti-Patterns --- What NOT to Do

Hard-won lessons from past mistakes. Read these before starting work.

1. **Don't blame the simulator before checking the data.** The #1 source of false divergences is stale hero skill levels, not simulator bugs. The Norah S2 "93% error" turned out to be entirely caused by wrong skill level metadata.

2. **Don't use `--repeat 10` for RNG testcases.** It gives misleading results for chance-based skills. Always use `--repeat 100` minimum.

3. **Don't rely on single game data points for RNG heroes.** One battle run is not statistically meaningful. Collect 5+ minimum, 40+ for high-variance skills.

4. **Don't rewrite core battle physics.** The round-by-round loop, damage formula, and fight orchestration are proven correct. If you find yourself rewriting `BattleRound.py` or `Fight.py`, stop. The fix is in skill definitions.

5. **Don't use the wrong error metric.** Always use `|sim - game| / winner_initial_count`. Alternative denominators produce inflated numbers that trigger false alarms.

6. **Don't design tipping-point testcases.** Battles where the winner barely wins amplify errors non-linearly via sqrt(troops) dynamics. Design testcases where the winner takes 50%+ casualties but clearly wins.

7. **Don't test multi-effect skills with mixed armies.** Different unit types kill at different rates, confounding the results. Use single-troop-type armies to isolate specific skill mechanics.

8. **Don't assume chance rolls are per-troop.** A 20% chance skill rolls once per unit type per round, not once per individual troop.

9. **Don't run raw adb commands or scripts directly.** All emulator interaction goes through `wosctl`. If you think it can't do something, check the docs first.

10. **Don't fix data problems with code changes.** If testcase data is bad (stale skills, OCR errors), the fix is re-running the battle, not changing the simulator.

11. **Don't move attack-frequency checks into `r_skill_condition`.** The correct place for attack-frequency gates is `trigger_condition` (per unit-type per round). `r_skill_condition` is called once per skill per round --- putting the attack-frequency gate there breaks multi-unit-type interactions. The failed fix in commit `a348b48` (reverted in `2c46307`) is the cautionary example.

12. **Don't confuse `once` and `first` for `trigger_for`.** `once` allows attempts from all unit types but caps activations at one per round. `first` stops ALL checking after the very first attempt. Wrong choice silently over- or under-triggers the skill.

---

Part of the WOS Knowledge Base. Update this file when you discover relevant insights. Always update KNOWLEDGE_INDEX.md if you change the scope of this document.
