# Accuracy Dashboard

The simulator accuracy dashboard is a local Next.js web app that records every `check_testcases.py` run to a git-committed SQLite database and visualises accuracy trends, coverage gaps, and dirty-run diffs.

## Quick Start

```bash
# Start the web server (runs on http://localhost:3000)
cd ~/projects_wsl/wos/battle_sim/lib/wos-simulator/dashboard/web
npm run dev
```

Runs are ingested automatically whenever `check_testcases.py` finishes — `ingest.py` is called by that script. No manual step is needed.

## How Runs Are Recorded

`dashboard/ingest.py` is invoked by `check_testcases.py` at the end of every run. It:

1. Collects `git rev-parse HEAD` and `git diff HEAD --binary` to capture code provenance.
2. Compresses any dirty-tree patch and/or untracked-file manifest into gzip blobs in the `blobs` table.
3. Writes one row to `runs` (run-level summary).
4. Writes one row per testcase to `run_testcases`.
5. Writes one row per testcase file (with SHA-256) to `run_testcase_files`.
6. Calls `coverage.py` to snapshot hero × skill coverage into `coverage_snapshots`.

The SQLite database lives at `test_results/dashboard.sqlite` and is committed to git. Migrations are in `dashboard/migrations/`.

## Schema Overview

| Table | Purpose |
|---|---|
| `runs` | One row per invocation: git SHA, dirty flag, `overall_avg_error_pct`, `bh_sig_count`, `summary_json` |
| `run_testcases` | Per-testcase results: `bias_pct`, `t`, `q`, `passes`, `waived_bool`, `stat_type` |
| `run_testcase_files` | SHA-256 of each testcase file — detects file drift across runs |
| `blobs` | Gzip-compressed patch / untracked-manifest content (present for dirty runs only) |
| `coverage_snapshots` | Hero × skill coverage per run: `covered_bool`, `testcase_count`, `battle_outcome_count` |

Full column docs: `dashboard/README.md`.

## Routes

| URL | Description |
|---|---|
| `/runs` | Run list with trend sparkline (overall avg error over time) |
| `/runs/[id]` | Run detail: testcase table, BH-flag list, dirty-run diff viewer |
| `/coverage` | Hero × skill coverage matrix with gap warnings |
| `/heroes/[name]` | Per-hero skill coverage + testcase error history |

## Reading the Coverage Report

The `/coverage` page shows a matrix of heroes vs skill slots. A cell is **red** when `covered_bool = 0` in the latest run — meaning no testcase exercised that skill in that run. Use this to identify heroes or skills that need new testcases.

`coverage.py` computes coverage by joining the `hero_skills/` catalogue against the testcase run results. A skill is considered covered if at least one testcase in the run activates it (tracked via `battle_outcome_count > 0`).

## Inspecting a Dirty-Run Patch

When a run is tagged `dirty = 1`, the run-detail page (`/runs/[id]`) shows an inline unified-diff viewer. The raw patch is stored as a gzip blob; the page decompresses and renders it.

### Incremental delta vs cumulative patch

The page automatically computes the most useful diff to display:

- **Previous run also dirty (same OR different git SHA)**: the page shows the *incremental delta* under the label **"Code Changes Since Previous Run"**. For each file referenced in either patch, `computeCrossShaDiff` (see `dashboard/web/lib/diff.ts`) reads the file at the recorded SHA via `git show <sha>:<file>`, applies that run's patch, and emits a per-file reconciled diff between the two reconstructed states. The same-SHA case reduces to the old `reconstructBefore` path.
- **Dangling SHA (rebased/amended away)**: per-file `git show` fails, so the helper falls back to same-baseline reconstruction from the patch alone and surfaces a yellow banner: *"Baseline commits X and Y no longer in git history — N files reconstructed without baseline; results are best-effort."* Results are approximate but still useful.
- **Previous run dirty but has no stored patch**: falls back to cumulative patch with a warning: *"Previous run has no stored patch — showing full cumulative patch."*
- **Previous run is clean, or there is no previous run**: shows the full stored patch behind a `Show Raw Dirty State Patch (vs Clean Baseline)` collapsible.

The `/compare/[a]/[b]` page follows the same reconstruction under a single `Code Changes (Run A → Run B)` header. Raw per-run patches are preserved for forensic inspection under a `Show raw per-run patches` collapsible.

### Manually extracting the raw stored blob

The SQL/bash extraction instructions below always yield the raw cumulative patch, regardless of what the UI displays.

```sql
SELECT b.content_gzip
FROM runs r
JOIN blobs b ON r.patch_blob_id = b.id
WHERE r.id = '<run-id>';
```

Then decompress:

```bash
python3 -c "import gzip,sys; sys.stdout.buffer.write(gzip.decompress(sys.stdin.buffer.read()))" < patch.bin > patch.diff
```

## Adding a New Chart

All charts use **Recharts** (board-approved). Add new visualisations in `dashboard/web/components/`. Data is fetched server-side from `test_results/dashboard.sqlite` via `better-sqlite3` in `dashboard/web/lib/db.ts`. Type contracts live in `dashboard/web/types/dashboard.ts`.

Steps:
1. Add a query function to `lib/db.ts` returning a typed result.
2. Add or extend a type in `types/dashboard.ts`.
3. Create a Recharts component in `components/` and import it in the relevant page.
4. Verify: `npm run build` and `npm run lint` must both pass clean.

## Backfill Historical Runs

To populate the DB from existing run JSON files (e.g., after a fresh clone):

```bash
cd ~/projects_wsl/wos/battle_sim/lib/wos-simulator
.venv/bin/python dashboard/backfill.py
```
