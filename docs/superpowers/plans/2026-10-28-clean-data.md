# HRC Clean Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add exact five-field clean JSON/CSV outputs at capture, daily snapshot, latest and monthly archive levels.

**Architecture:** `collector.py` owns the canonical five-field projection and serialization. `archive.py` reuses those interfaces for deduplicated monthly, daily snapshot and latest views, while the existing full evidence and quality outputs remain unchanged.

**Tech Stack:** Python 3.12 standard library, unittest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-28-clean-data-design.md`

## Global Constraints

- Clean fields, in order: `river`, `station`, `observed_at`, `water_level_value`, `flow_value`.
- Missing and conflicting numeric values remain null/blank; never infer or average them.
- Existing full, raw-evidence and quality files remain available.
- No third-party Python dependency.

## Review Focus

- Missing flow must be JSON null and an empty CSV cell.
- Conflicting station-time values must not leak a selected or averaged value into monthly clean output.
- Repeated captures of the same station-time must produce one monthly clean row.
- Every clean JSON object and CSV header must have exactly the five approved fields in order.
- The workflow must commit and upload all clean output layers.

---

### Task 1: Capture-level clean projection

**Files:**
- Modify: `collector.py`
- Modify: `tests/test_collector.py`

**Interfaces:**
- Consumes: validated records returned by `parse_water_table(html)`.
- Produces: `CLEAN_COLUMNS`, `clean_rows(rows)`, `clean_csv_bytes(rows)`, and capture/data-latest `water_clean.json`/`water_clean.csv`.

- [ ] **Step 1: Write failing tests** asserting exact keys/header order, missing-flow null/blank, and capture/data-latest clean files.
- [ ] **Step 2: Run** `python -m unittest tests.test_collector -v`; expected failure because clean interfaces/files do not exist.
- [ ] **Step 3: Implement** the canonical projection and capture outputs without changing full outputs.
- [ ] **Step 4: Run** `python -m unittest tests.test_collector -v`; expected PASS.
- [ ] **Step 5: Commit** with message `Add capture-level clean water outputs`.

### Task 2: Archive clean views and workflow delivery

**Files:**
- Modify: `archive.py`
- Modify: `tests/test_archive.py`
- Modify: `tests/test_automation.py`
- Modify: `.github/workflows/collect.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: Task 1 `collector.clean_rows(rows)` and `collector.clean_csv_bytes(rows)` plus deduplicated `station_records(root)`.
- Produces: monthly `HRC_clean.csv`, dated `_clean` snapshots, `latest/clean.json`, `latest/clean.csv`, and uploaded clean artifacts.

- [ ] **Step 1: Write failing tests** for exact monthly/latest/snapshot schemas, deduplication, conflict nulls, and workflow artifact paths.
- [ ] **Step 2: Run** `python -m unittest tests.test_archive tests.test_automation -v`; expected failure because archive clean outputs are absent.
- [ ] **Step 3: Implement** archive clean views, workflow paths and README documentation.
- [ ] **Step 4: Run** `python -m unittest discover -s tests -v`; expected PASS.
- [ ] **Step 5: Regenerate current archive and run independent verification.**
- [ ] **Step 6: Commit** with message `Add monthly and latest clean water views`.
- [ ] **Step 7: Push, dispatch the public workflow, and verify remote clean files and artifact status.**
