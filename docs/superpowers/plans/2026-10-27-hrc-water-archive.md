# HRC Realtime Water Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy a public daily archive for the HRC homepage realtime water table.

**Architecture:** A standard-library HTML parser extracts the table by exact headers. The collector saves immutable evidence and validated rows; a separate archive builder deduplicates station-times into monthly station files and status views.

**Tech Stack:** Python 3.12 standard library, GitHub Actions, CSV/JSON.

**Spec:** `docs/superpowers/specs/2026-10-27-hrc-water-archive-design.md`

## Global Constraints

- Source: `http://www.hrc.gov.cn/swj/`.
- Daily schedule: 17:00 Asia/Shanghai / 09:00 UTC.
- Public GitHub repository under `Dpasang` so runs and archived data can be inspected without authentication.
- Preserve source evidence, observation time, missing values, raw mixed-semantics column and conflicts.
- Failed runs never replace latest successful data.

## Review Focus

- Target-table selection when unrelated tables appear before it.
- Empty flow cells remain missing instead of zero.
- Mixed last-column semantics stay explicit.
- Same-time conflicting values are not averaged.
- Failed capture and stale observations remain visible without overwriting success.

### Task 1: Parser and validated current capture

**Files:** Create `collector.py`, `tests/test_collector.py`, `tests/fixtures/current.html`.

**Interfaces:** Produces `parse_water_table(html: str) -> list[dict]`, `classify_limit_value(row: dict) -> dict`, and `collect(root: Path) -> dict`.

- [ ] Write tests for exact table selection, eight current rows, empty flow, observation timestamps and mixed last-column semantics.
- [ ] Run tests and verify missing module/function failures.
- [ ] Implement the minimal parser, validation and atomic snapshot/latest update.
- [ ] Run the collector tests and full suite.
- [ ] Commit.

### Task 2: Monthly station archive and quality reports

**Files:** Create `archive.py`, `tests/test_archive.py`.

**Interfaces:** Consumes validated daily JSON; produces station-time series, `data/YYYY-MM`, `snapshots`, `latest`, and status reports.

- [ ] Write tests for repeated captures, conflicts, fixed CSV headers, observation-month grouping and failed-run preservation.
- [ ] Run tests and verify expected failures.
- [ ] Implement deduplication, monthly statistics and daily/latest views.
- [ ] Run the archive tests and full suite.
- [ ] Commit.

### Task 3: Historical snapshot recovery and automation

**Files:** Create `recover_history.py`, `tests/test_history.py`, `.github/workflows/collect.yml`, `README.md`, `.gitignore`, `.gitattributes`.

**Interfaces:** Consumes Wayback CDX/replay pages and the Task 1/2 APIs; produces verified history files and runs the whole pipeline daily.

- [ ] Write tests for CDX parsing, duplicate digest removal, no-table exclusion and source/capture time separation.
- [ ] Run tests and verify expected failures.
- [ ] Implement historical recovery and evidence manifest.
- [ ] Add workflow and user documentation; run current collection, archive build and full verification.
- [x] Commit, create/push the public repository, dispatch a cloud run, and verify remote artifacts.

