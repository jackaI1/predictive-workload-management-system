# Predictive Workload Management System

https://github.com/user-attachments/assets/a83487d5-7723-4faf-907a-2a4d003acbea

Work arrives as short, hand-typed entries in a project tracker — a line of text
and a due date — which says nothing about how much work any of them actually is.
This tool reads those entries, finds each one's matching project files, works
out how large and complex the job really is, and turns a list of tickets into a
picture of how much work is coming and when each piece can start.

The point is that ten easy jobs and ten hard ones look identical in a tracker,
and a schedule built on that count is wrong before anyone starts.

The public forecast planner computes dates and daily allocations from editable,
generated inputs. It uses no credentials or project records. The separate KPI
history view supports generated demo data or a configured Google Sheet.

---

## The interesting problems

### Free text is the input format, and it cannot be changed

The entries are typed by people under time pressure, so the same intent arrives
many ways: `BLOCK 1 TO 3`, `BLK 2`, `LOT 5, 7 AND 9`, `BBs (1, to 4, 6 to 8)`,
plus a long tail of spacing and punctuation variants. Nothing downstream can run
until each of these becomes an explicit set.

Rather than rejecting malformed input — which just moves the work back to the
person who was in a hurry — the parser expands what it can and reports what it
cannot. Ranges, comma lists, the connecting words `TO` and `AND`, parenthesised
groups and plural forms are all handled, and a title with no recognisable
project code returns empty sets so the caller skips it rather than guessing.

### Counting tickets is the wrong measure, so it scores complexity instead

Each entry is matched to its schedule workbook, and complexity is computed from
what is actually in it:

```
base difficulty   from a square-footage tier    (thresholds loaded from config)
elevation bonus   (number of elevations - 1) x 0.1
difficulty        base + bonus
```

Tier thresholds live in a remote configuration sheet rather than in the source,
so the scoring can be retuned without a deploy — with documented fallback values
if that sheet is unreachable or empty: below 2,500 ft² is 1.0; 2,500–3,999 ft²
is 1.5; 4,000 ft² and above is 2.0. The resulting KPI is `difficulty / duration in
business days`, which means a hard job finished slowly and an easy one finished
fast stop reading the same.

### A job is not startable when it is created

This is the part that makes the system forward-looking rather than a report of
what already happened. A model cannot begin until *all* of its input drawings
have landed, so the startable date is derived, not entered:

```python
startable = max(architectural_date, floor_date, truss_date) + 1 day
```

Blocks roll up: a block's date is bounded by its architecture/truss inputs and
the latest receipt-derived date of every model in its parent scope. If any model
is missing a receipt, the block stays waiting. The scenario planner additionally
waits for explicit predecessor tasks to finish.
That turns a set of scattered input dates into a view of when load actually
arrives.

### The pipeline can run on a schedule, so expansion has to converge

The workflow is manual by default; uncomment its hourly cron only after configuring
your own resources and credentials. The expander reconciles repeated snapshots:

- **Scope changes are detected, not accumulated.** Models that no longer match a
  parent entry have their rows purged rather than left behind as orphans.
- **Contested ownership resolves deterministically.** When two entries share a
  project code and both claim the same model, the later-dated parent wins and
  the loser's rows are removed — so two runs in either order reach the same
  state. Equal dates use task ID and row content as deterministic tie breakers.
- **Rate limits are assumed, not hoped against.** Both the tracker API and the
  spreadsheet writes use exponential backoff with jitter. KPI writes and deletions
  are batched; KPI indices are refreshed after deletions. Some initial reads are
  direct API calls and can still fail on transient errors.

---

## Try it without credentials

The parsing and scoring layer is pure — no network, no spreadsheet — so it runs
on its own:

```bash
# Requires Python 3.12 or newer (use a virtual environment).
pip install -r requirements.txt
python examples/parse_demo.py
```
To explore the dashboard with generated data and no credentials:

```sh
WORKLOAD_DEMO=1 python -m streamlit run app.py
```

Demo mode opens **Forecast**; use the sidebar to switch to **KPI history**.
The parsing command prints synthetic title expansions. Leave `WORKLOAD_DEMO`
unset when using the password-protected, credentialed KPI dashboard.

In Forecast, parse `D12345 AA1 TO 3 AND BLOCK 1`, then open **Edit scenario**
to change receipt dates, duration, difficulty, priority, due date and predecessors.
Use `PROJECT/TASK` for predecessors (comma-separated for multiple dependencies).
**Fill missing receipt** sets missing floor receipt dates to the planning date.
Receipt changes and dependencies immediately recompute the plan.

- A startable date is the latest receipt plus one calendar day; actual allocation
  uses weekdays and begins after all predecessors finish. Cycles, unknown
  predecessors and missing dates produce waiting explanations.
- Lower priority numbers go first, then earlier due dates and task names. Total
  work is difficulty in weighted mode or one unit in equal mode. The requested
  daily rate is total work divided by duration in business days.
- **Daily capacity** caps total allocated work across all scenario projects.
  Unused fractions can be shared across projects on the same day. Low capacity
  extends tasks; the forecast marks unfinished work at the horizon and late finishes.
- The scope box filters the view; every scenario task still competes for capacity.
  Charts, per-task explanations and a downloadable allocation CSV expose the result.
  Edits last for the browser session and do not write to ClickUp or Google Sheets.

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```

The suite covers title parsing, workbook matching, tier scoring, receipt dates,
capacity planning, dependency errors, Streamlit controls, retries and in-memory
pipeline convergence. All fixtures are synthetic. No tracker token, Google
credentials or external network is used by the tests.

## Running it against real data

The live jobs need credentials, read from the environment and never committed:

| Name | Where | Purpose |
|---|---|---|
| `CLICKUP_TOKEN` | env var / CI secret | tracker API token |
| `CLICKUP_WORKSPACE_ID` | env var / CI secret | workspace to query |
| `LIST_ID` | env var | ClickUp list to query |
| `PROGRESSION_STATUS_FIELD_ID` | env var | workflow status custom field |
| `GOOGLE_SHEET_URL` | env var | master workbook shared with the service account |
| `DRIVE_FOLDER_ID` | env var | schedule folder (expander) |
| `DIFFICULTY_LOOKUP_URL` | env var | optional remote difficulty tiers |
| `creds.json` | file, gitignored | Google service-account key |
| `DASHBOARD_PASSWORD` | `st.secrets` | dashboard access |

Export these environment variables before local live runs. In CI, map the same
names to your own repository variables/secrets in the workflow before enabling
its cron. No live resource is configured in the public checkout.

```bash
python ClickUpQA.py       # consistency checks, creates QA subtasks
python snapshotter.py     # snapshot task state to the sheet
python expander.py        # match workbooks, derive dates and write KPIs
streamlit run app.py      # dashboard
```

## What was changed for public release

This began as an internal tool with the firm's own resource identifiers compiled
into it. Preparing it to be published was not only a matter of deleting things:

- **Every resource identifier is now configuration**, read from an environment
  variable with an obviously-fake default, instead of a literal in the source.
- **The domain vocabulary is now a named constants block.** The project-code
  pattern and the keywords for groups and units are grouped near the top of
  `expander.py`. These are adaptation entry points; canonical workbook labels
  still use BLOCK and LOT, so other vocabularies also need matching logic changes.
- **Two direct imports were undeclared** and worked only because other packages
  pulled them in. They are declared and the dependency set is pinned.
- **The dashboard's authentication was rebuilt.** It previously accepted the
  password as a URL query parameter and fell back to a default when the secret
  was unset. It now reads the secret only, refuses to start if it is missing,
  and compares in constant time.

[`ADAPTING.md`](ADAPTING.md) walks through what is genuinely specific to this
domain, what is one constant away from being general, and what would have to be
replaced to point it at a different tracker.

## Scope and limitations

- **The tracker and spreadsheet backends are not abstracted.** It talks to the
  ClickUp and Google Sheets/Drive APIs directly. Swapping either means writing a
  new module, not changing a setting — see `ADAPTING.md`.
- **The schedule parser expects a particular column layout** (series, model,
  elevations, square footage, then dated columns found by header). A differently
  shaped workbook needs `load_and_parse_schedule` adjusted.
- **`extract_allowed_targets` is intricate.** Seven overlapping regex handlers
  build the model-name variants, and that section is deliberately the least
  test-covered part of the suite — asserting behaviour there without real inputs
  risked encoding a misreading as a passing test. It is the first place to add
  coverage.
- **Difficulty is a heuristic, not a model.** It is a tiered lookup plus a linear
  elevation term, chosen because it is explainable to the people it schedules.
  It is not fitted to outcome data.
- **No assignment or dispatch.** The planner allocates work units to days, not
  to people. Its synthetic scenarios are independent of the live KPI sheets.
- Forecasts use weekdays without holiday calendars and assume no prior completed
  work. A block must list its member models as predecessors in the scenario.
- Remote sync is not transactional: an interrupted run can leave partial writes;
  rerun after resolving the cause. Live service behavior needs your own account
  validation; the automated integration tests use in-memory services.
- Tracker timestamps use America/New_York; the local planner uses the server's
  current date unless you change **Plan from**.

## Layout

```
expander.py       parsing, schedule matching, difficulty, derived dates
snapshotter.py    tracker -> sheet state snapshots
ClickUpQA.py      consistency checks and QA subtask creation
app.py            dashboard entrypoint and KPI history (Streamlit)
planner.py        pure receipt, dependency and capacity scheduling
planner_ui.py     generated scenario editor and forecast charts
examples/         credential-free parsing demo
tests/            pytest suite over the parsers
```

## Provenance

Developed for an engineering workflow and published with written permission. Client information, firm documents, internal resource identifiers
and proprietary data are excluded — every workspace, sheet and folder identifier
in this repository is a placeholder.
## License

MIT, see LICENSE. Third-party components are listed in THIRD_PARTY_NOTICES.md.

