# WOS Knowledge Base Index

Load this index at the start of every work session. Read the topic files relevant to your current task. When you update any knowledge file, you MUST also update this index if the scope or summary has changed.

## Project Goal

Build a battle simulator that perfectly replicates the WOS in-game battle engine for 1v1 battles. Allow accurate prediction of outcome distributions for any army/hero combination.

## Key Paths

| Resource | Path |
|---|---|
| wosctl | `scripts/wosctl` (relative to this file) |
| wosctl skill | `.` (this directory) |
| Simulator code | `{config.simulator_dir}` |
| Per-hero skill JSON | `{config.simulator_dir}/assets/hero_skills/` |
| Captured hero skills | `data/player_hero_skills.json` (relative to this file) |
| Battle specs | `testcase_spec/` (relative to this file). **Write all hand-authored battle specs here** — do NOT write to the simulator repo's `testcases/` (that directory is reserved for emulator-captured ground truth). |
| Emulator-verified testcases | `{config.simulator_dir}/testcases/emulator_verified/` |
| Testcase runner | `{config.simulator_dir}/check_testcases.py` |

## Current Baseline

- Overall average error: ~1.42% across 137 testcases (flags drop from 7 → 5 after WOS-136 accept-residual waiver)
- Failing testcases: lynn_solo (+0.85% t=+3.17), Mia_tc daut_viper_2 (-1.37% t=-2.28, borderline), norah_s2_inf_only_A (-0.66% t=-2.73, small N_game=4)
- Waived (documented in known-issues.md): Alonso_tc daut_viper_1 (-1.67% t=-16.79), Alonso_tc daut_viper_2 (+0.88% t=+5.48) — CEO accept-residual 2026-04-18; regressions still surface via waiver-lapse tolerance in `check_testcases.py`.
- Resolved 2026-04-18: Attack-frequency off-by-one (WOS-153) — alonso_solo#0 bias +19.52% → +2.64%, flag count 8 → 7.
- wayne_mixed_solo: resolved — RNG-borderline at N=100, passes robustly at `--repeat 300` ✅ (WOS-140)
- wayne_s1_solo: resolved, now ~1% ✅
- Tier 1 meta heroes: Gwen, Hector, Norah, Mia, Lynn, Logan, Reina, Greg, Alonso, Philly, Flint, Jeronimo, Zinman, Molly
- Tier 2: Renee, Wayne, Wu Ming

## Knowledge Topics

Read the files relevant to your current task. The summary tells you what each covers.

| File | Summary | Read when... |
|---|---|---|
| [battle-mechanics.md](knowledge/battle-mechanics.md) | Core battle loop, troop types, **hero class constraint (1 per class per side)**, stat stacking rules, **damage coefficient formula (base/extra/normal_only layers, additive combination, dodge interaction)**, extra-attack non-primary targeting, non-linear dynamics | You need to understand how battles work or why results look the way they do; **always check before writing multi-hero specs** |
| [hero-skills.md](knowledge/hero-skills.md) | Skill properties, effect_op grouping, targeting keywords (`benefit_vs` controls extra-attack fan-out + regular effect scope), `trigger_for: "once"` deprecated, special field mechanisms, two-phase activation, dodge, CSV format, implementing new heroes | You are implementing, debugging, or reviewing hero skill definitions |
| [known-issues.md](knowledge/known-issues.md) | Active divergences and resolved investigations with root causes. **Active now: Alonso solo stats, Wayne mixed troops, Reina borderline.** | **Check FIRST before writing any code** to investigate a divergence — it may already be known and documented |
| [debugging.md](knowledge/debugging.md) | Data-before-code methodology, bug location priority, error metrics, statistical significance checklist | You are investigating a failing testcase or unexpected results |
| [testcases.md](knowledge/testcases.md) | Spec vs testcase distinction, one-way nature, integrity rules, **mandatory pre-retirement checklist (valid/invalid reasons, divergence triage)**, good testcase design, output schema, delegation checklists, interpreting results, regression rule | You are creating, running, or interpreting testcases — **read before retiring any testcase** |
| [wosctl-operations.md](knowledge/wosctl-operations.md) | Golden rules, run-testcase automation, instance config, common workflows, hero template registration, troubleshooting | You are running emulator commands or diagnosing wosctl issues |
| [spec-design.md](knowledge/spec-design.md) | Pipeline continuity, pre-spec checklist (incl. hero class compatibility check), spec template, naming conventions, validation progression, batch strategy | You are designing battle specs for the test pipeline |
| [anti-patterns.md](knowledge/anti-patterns.md) | 12 hard-won lessons on what NOT to do --- data assumptions, metric mistakes, architecture traps | Before starting any task (quick scan) and when debugging unexpected behavior |
| [accuracy_dashboard.md](knowledge/accuracy_dashboard.md) | Local Next.js dashboard that records every `check_testcases.py` run to `test_results/dashboard.sqlite`; schema overview, coverage report, dirty-run diff viewer, adding new charts | You need to run, understand, extend, or debug the accuracy dashboard |

## Rate Limits

- LLM usage is rate-limited on the provider plan. Limits renew every 5 hours.
- If hitting limits after 2hrs: slow down. If reaching 4+ hrs: good utilization.
- Use cheaper models (sonnet, haiku) where appropriate.

## Maintaining This Knowledge Base

When you complete a task that yields reusable insights:

1. **Identify the right topic file.** Read the summaries above and pick the file where the insight belongs.
2. **Update the topic file.** Add the insight in the appropriate section. Keep entries concise, factual, and actionable.
3. **Update this index if needed.** If your change alters the scope of a topic file (e.g., it now covers something new), update the summary in the table above. If you create a new topic file, add a row to the table.
4. **Never let the index go stale.** The index is the entry point for all agents. If it doesn't accurately describe what's in each file, agents will miss relevant information or waste time reading irrelevant files. Treat index accuracy as a first-class responsibility --- as important as the knowledge itself.

*Last updated: 2026-04-19 (WOS-162 follow-up: renamed `testcases/` → `testcase_spec/` in this skill to disambiguate from the simulator repo's ground-truth `testcases/` directory).*
