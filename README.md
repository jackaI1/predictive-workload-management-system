# Predictive Workload Management System

A Python workflow that expands tracker entries into model-level work, derives receipt-based start dates and forecasts weekday allocations under a shared daily capacity.

https://github.com/user-attachments/assets/74bed0e6-629f-4761-99cf-799c48bd05d1

## Overview

A tracker entry describes a scope and due date, but a ticket count does not say
how much work is inside that scope or whether the necessary drawings have arrived.
Hand-entered titles and schedule workbooks also use different naming conventions.

The live pipeline parses titles, matches schedule rows and calculates difficulty
and daily KPI values. A separate, credential-free scenario planner uses editable
receipts, durations, priorities and dependencies to allocate work across days.
Its forecasts do not write to the live tracker or KPI sheets.

Built during an engineering co-op, this release replaces internal resource
identifiers with configuration and provides generated demo data. The public
examples and automated integration fixtures contain no project records.

## How it works

1. **Parse scope.** [`expander.py`](expander.py) implements
   `extract_allowed_targets`, numeric ranges, compound suffixes and model-name
   matching. It recognises project codes, blocks/lots, lists, `TO`/`AND` and
   parenthesised groups. Titles without a project code return empty targets.
   Schedule matching checks numeric boundaries so `BLOCK 1` does not select
   `BLOCK 10`. See [`tests/test_expander_parsing.py`](tests/test_expander_parsing.py).
2. **Snapshot and reconcile.** [`snapshotter.py`](snapshotter.py) reads ClickUp
   state into a configured Google workbook. `expander.py` downloads matching
   schedule workbooks, expands merged cells and reconciles model rows against
   parent scope. Removed targets are purged. Competing parents resolve by later
   start date, then deterministic task/content tie breakers.
3. **Calculate difficulty and receipt dates.** In `expander.py`,
   `parse_sq_ft_and_difficulty` applies configured square-footage tiers plus
   `0.1 × max(0, elevations - 1)`. Fallback tiers are 1.0 below 2,500 ft², 1.5 below
   4,000 ft² and 2.0 above that. `derive_start_dates` uses the latest required
   receipt plus one calendar day. Missing receipts keep work waiting; blocks
   also depend on the latest model receipt date in their parent scope.
4. **Write KPI histories.** `expander.py` distributes difficulty/duration and
   equal-weight `1/duration` values over business days. It batches writes and
   history deletions. [`ClickUpQA.py`](ClickUpQA.py) performs consistency checks
   and can create QA subtasks. Retry helpers use exponential backoff with jitter;
   some initial reads still call APIs directly.
5. **Forecast a scenario.** [`planner.py`](planner.py), `forecast`, sorts tasks
   by ascending priority number, due date and project/task key. A dependency DFS
   detects cycles, unknown predecessors and downstream blocked work. Each valid
   task is released after its latest receipt plus one day and only starts on a
   weekday after every predecessor has finished on an earlier day.
6. **Allocate capacity.** A task's total work is its difficulty in weighted mode
   or one unit in equal mode. Its requested daily rate is total work/duration.
   Each weekday assigns `min(remaining work, requested rate, remaining capacity)`
   in priority order. Fractions can be shared across projects; low capacity
   extends completion. Unfinished tasks at the horizon and late finishes receive
   explanations. Sorting is O(T log T), dependency validation O(T + E), and the
   day/task scan O(HT + HE) in the worst case for T tasks, E dependency edges and
   H horizon days. Stored allocations can grow to O(HT).
7. **Inspect and edit.** [`planner_ui.py`](planner_ui.py) provides the synthetic
   editor, timeline, daily allocations, explanations and CSV download.
   [`app.py`](app.py) hosts Forecast and KPI history. Scope filters change the
   view; all scenario tasks still compete for the shared capacity.

## Design decisions and trade-offs

- Explainable difficulty tiers are a heuristic, not a fitted effort predictor.
  Their meaning depends on local work and schedule conventions.
- Receipt completeness gates work rather than substituting an assumed arrival.
  This exposes missing information but can leave much of a plan waiting.
- Fixed priority ordering is deterministic and inspectable. It is a greedy
  allocation, not an optimisation for minimum lateness or staffing cost.
- Reconciliation is designed to converge on reruns. Remote operations are not a
  transaction, so interrupted writes can leave partial state until a later run.
- Forecast scenarios stay separate from live sheets. This makes the demo usable
  without accounts, but edits last only in the Streamlit session.
- The live KPI dashboard requires a configured secret, fails closed when missing
  and compares passwords in constant time. Demo mode serves generated data.

## Results and evaluation

Reproducible here: the synthetic fixture in
[`tests/test_planner.py`](tests/test_planner.py),
`test_ready_waiting_priority_due_dates_and_split_capacity`, gives two tasks a
0.5-unit daily request and sets capacity to 0.75. The first weekday allocates
0.5 to the higher-priority task and 0.25 to the other. The test checks every
day stays within capacity and excludes weekends:

```sh
python -m pytest tests/test_planner.py -q
```

`test_weighted_equal_and_live_replanning_conserve_work` checks total allocations
of 3 weighted units versus 2 equal units for its two-task fixture. These are
algorithm outputs under stated assumptions, not measured productivity gains.

[`tests/test_pipeline.py`](tests/test_pipeline.py) runs the live reconciliation
logic against in-memory sheets and synthetic workbooks, checks repeat-run
convergence and resolves competing parent scopes in either order. No live-account
performance or forecast-accuracy study is claimed.

## Getting started

Use CPython 3.12; fresh-copy verification used 3.12.14 on macOS arm64.
Pinned direct dependencies are in [`requirements.txt`](requirements.txt), with
transitive constraints in [`requirements-lock.txt`](requirements-lock.txt).
From the repository root:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python examples/parse_demo.py
WORKLOAD_DEMO=1 python -m streamlit run app.py --server.address=127.0.0.1 --server.port=8501 --server.headless=true --browser.gatherUsageStats=false
```

The parser prints generated range and title expansions, including `1 TO 5`
becoming `[1, 2, 3, 4, 5]`. The server prints its local URL. Open
`http://127.0.0.1:8501`; demo mode starts on Forecast and needs no credentials.
Stop it with Ctrl-C.

In Forecast, parse `P12345 AA1 TO 3 AND BLOCK 1`, then open Edit scenario.
Change receipts, duration, difficulty, priority, due dates or predecessors.
Predecessors use `PROJECT/TASK`, comma-separated. Fill missing receipt supplies
missing floor receipts using the planning date. The charts and explanations
recompute; the CSV contains daily task allocations. KPI history is available
from the sidebar with generated demo data.

### Configuring live services

[`ADAPTING.md`](ADAPTING.md) describes the workbook schema, vocabulary and
backend coupling. Live jobs require your own ClickUp token, workspace/list/status
identifiers, Google service account, master sheet and Drive schedule folder.
Configuration includes `CLICKUP_TOKEN`, `CLICKUP_WORKSPACE_ID`, `LIST_ID`,
`PROGRESSION_STATUS_FIELD_ID`, `GOOGLE_SHEET_URL`, `DRIVE_FOLDER_ID`, optional
`DIFFICULTY_LOOKUP_URL`, and an ignored `creds.json`. The dashboard password is
`DASHBOARD_PASSWORD` in `.streamlit/secrets.toml`.

The entry points are `ClickUpQA.py`, `snapshotter.py` and `expander.py`; they
perform remote writes and need account-specific validation. They are not part
of the credential-free startup above. The
[scheduled workflow](.github/workflows/schedule.yml) is manual by default;
configure resources before enabling its commented cron.

## Testing

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The current suite has 71 passing tests:

- [`tests/test_expander_parsing.py`](tests/test_expander_parsing.py): range and
  suffix expansion, exact project/number matching and schedule-row selection.
- [`tests/test_pipeline.py`](tests/test_pipeline.py): difficulty, dates,
  workbook reads, rerun convergence, scope deletion, ownership and retry helpers.
- [`tests/test_planner.py`](tests/test_planner.py): capacity conservation,
  weighted/equal work, priority, receipt gating, dependencies and horizon errors.
- [`tests/test_planner_ui.py`](tests/test_planner_ui.py): editor state,
  receipt fill, navigation and recomputed plans using Streamlit AppTest.
- [`tests/test_dashboard_startup.py`](tests/test_dashboard_startup.py): demo
  startup, missing-secret refusal and configured password handling.

These tests use synthetic or in-memory services. They do not authenticate to
ClickUp or Google, and do not establish live API reliability.

## Project structure

```text
expander.py                  title/workbook matching, reconciliation and KPIs
snapshotter.py               tracker snapshots
ClickUpQA.py                 QA checks and tracker writes
planner.py                   pure receipt/dependency/capacity forecast
planner_ui.py                scenario editor and forecast charts
app.py                       Streamlit dashboard and authentication
examples/parse_demo.py       credential-free parser example
tests/                      parser, service-double, planner and UI tests
.github/workflows/schedule.yml  opt-in automation entry point
ADAPTING.md                  deployment and domain adaptation notes
```

## Limitations and known issues

- Work is assigned to days, not people. There are no skill constraints, holidays
  or prior-progress model. Scenario blocks need explicit model predecessors.
- Weekday capacity and difficulty are assumptions; actual effort must be
  calibrated independently. A higher-priority stream can delay other work.
- Schedule workbooks need the expected columns and receipt headers. New naming
  conventions need parsing/matching changes, beyond editing vocabulary constants.
- Regex parsing handles tested forms, not arbitrary language. Extend fixtures
  before using an unfamiliar title format.
- ClickUp and Google backends are directly coupled to the modules. Replacing a
  backend requires code, not only configuration.
- Tracker timestamps use `America/New_York`; scenario dates use the server's
  current date unless Plan from is changed. Remote sync is not transactional.
- Fresh-copy checks cover macOS and generated data; live accounts and unattended
  scheduled execution were not exercised.

## License

Developed at D.L. Engineering Inc. and published with the firm's written
permission. Client information, firm documents, internal resource identifiers and
proprietary data are excluded.

Original project source is MIT; see [`LICENSE`](LICENSE). Dependency terms,
including certifi's MPL-2.0 and the Streamlit font licences, are recorded in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md); MIT does not replace them.
