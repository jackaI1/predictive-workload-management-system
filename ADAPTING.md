# Adapting this to your own work

This was built for one firm's workflow, so an honest map of what is general and
what is not is more useful than pretending it is a framework. Three tiers, from
"change a constant" to "write a new module".

---

## Tier 1: configuration, no code change

Every resource identifier is read from an environment variable with an
obviously-fake default. Nothing needs editing to point the tool at your own
resources:

```bash
export GOOGLE_SHEET_URL="https://docs.google.com/spreadsheets/d/<your-id>/edit"
export DRIVE_FOLDER_ID="<your-folder-id>"
export DIFFICULTY_LOOKUP_URL="https://docs.google.com/spreadsheets/d/<your-id>/edit"
export CLICKUP_TOKEN="<your-token>"
export CLICKUP_WORKSPACE_ID="<your-workspace-id>"
```

**The difficulty scoring is also configuration.** Tier thresholds are read from
the sheet at `DIFFICULTY_LOOKUP_URL` at runtime, as `(threshold, difficulty)`
rows. Retuning how work is scored means editing a spreadsheet, not deploying.
If that sheet is unreachable the documented fallback tiers are used.

## Tier 2: one named constant

The vocabulary of the domain is declared in one block at the top of
`expander.py` and referenced everywhere else:

```python
PROJECT_CODE_PATTERN = r"(P\d{5,6})"      # job identifier, e.g. P10001
GROUP_KEYWORDS = r"BLOCK|BLK\.?"          # a cluster of units sharing drawings
UNIT_KEYWORDS = r"LOT|LTS|LOTS"           # an individual unit inside a group
LIST_CHARS = r"[\d\s,&\-TOANDtoand]+"     # what can appear inside a number list
```

The structure this encodes (*a job identifier, groups, and units inside those
groups*) is not specific to construction. A print shop has jobs, runs and
copies. A lab has studies, batches and samples. A field service team has
contracts, sites and assets.

Retargeting is mechanical:

```python
PROJECT_CODE_PATTERN = r"(JOB-\d{4})"
GROUP_KEYWORDS = r"RUN|BATCH"
UNIT_KEYWORDS = r"UNIT|SAMPLE|SAMPLES"
```

`JOB-2041 RUN 3 UNIT 5, 7 AND 9` then parses exactly the way the construction
titles do. The parsing tests in `tests/test_expander_parsing.py` are written
against behaviour rather than against the specific keywords, so they are a
reasonable safety net while you change these.

**What you will also want to change:** `allowed_blocks` is populated as
`f"BLOCK {num}"`, so the emitted label still says BLOCK. Change that f-string to
match your vocabulary; it is one line, in `extract_allowed_targets`.

## Tier 3: needs a new module

These are genuinely coupled and there is no configuration that will save you.

### The tracker

`ClickUpQA.py` and `snapshotter.py` call the ClickUp REST API directly for task
retrieval, custom fields, subtask creation and doc creation. Swapping to Jira,
Linear or Asana means writing a replacement for the request layer. What is worth
keeping is the shape around it: `clickup_request()` wraps every call in
exponential backoff with jitter over the retryable status codes, and every
consumer is written to tolerate a `None` response rather than assuming success.

### The spreadsheet backend

Reading and writing go through `gspread` and the Google Drive API. The schedule
parser additionally assumes a particular workbook layout:

| Column | Contents |
|---|---|
| 1 | series |
| 2 | model name |
| 3 | elevations |
| 4 | square footage |
| dated columns | located by header text, not by position |

If your source data is a database rather than a spreadsheet, the natural seam is
`load_and_parse_schedule()`: give it the same return shape
(`schedule_data, arch_idx, floor_idx, truss_idx`) and everything downstream is
unchanged.

### The complexity model

`parse_sq_ft_and_difficulty()` is a tiered lookup on one quantity plus a linear
bonus on a second. If your work is not sized by area, this is the function to
replace: it is 30 lines, pure, and has a single call site.

The design choice worth preserving: it is *explainable*. Anyone whose work is
being scheduled by it can be shown why their job scored what it scored. A fitted
model would likely be more accurate and much harder to defend in the room.

---

## What is worth stealing even if none of it fits

Three ideas here are independent of the domain:

1. **Expand free text into explicit sets at the boundary.** Everything
   downstream gets structured data and never has to re-parse. The parsers are
   pure functions, which is why they are the part that is properly tested.

2. **Derive readiness dates instead of storing them.** `max(inputs) + 1 day` is
   trivial arithmetic, but it converts a pile of scattered dates into a forward
   view, and it cannot drift out of date the way a manually-entered field does.

3. **Make repeated runs converge.** A scheduled job that is not idempotent
   accumulates garbage. Detecting removals, resolving contested ownership
   deterministically, and batching writes are what make an hourly job safe to
   leave running.
