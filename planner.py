"""Credential-free, deterministic business-day capacity planning.

A task's total work is its difficulty (weighted) or one unit (equal). Its
unconstrained daily rate is total work / duration. Lower priority numbers and
then earlier due dates consume capacity first. Predecessors finish on an earlier
business day. Missing inputs propagate; no forecast substitutes a receipt.
"""
from dataclasses import dataclass
from datetime import date, timedelta
import math
from expander import compute_matched_model_names, extract_allowed_targets


@dataclass(frozen=True)
class Task:
    project: str
    name: str
    duration: int
    difficulty: float
    architecture: date | None
    floor: date | None
    truss: date | None
    priority: int = 2
    due: date | None = None
    predecessors: tuple[str, ...] = ()

    @property
    def key(self):
        return f'{self.project}/{self.name}'


@dataclass(frozen=True)
class Allocation:
    day: date
    task: str
    units: float


@dataclass(frozen=True)
class Result:
    status: str
    startable: date | None
    start: date | None
    finish: date | None
    explanation: str


@dataclass(frozen=True)
class Plan:
    results: dict[str, Result]
    allocations: tuple[Allocation, ...]


def select_tasks(title, tasks):
    """Resolve title scope against an explicit schedule, without inventing tasks."""
    project, _, _, _ = extract_allowed_targets(title)
    candidates = [t for t in tasks if t.project == project]
    # The schedule parser uses model column C and skips its second header row.
    schedule = [['', '', 'MODEL', '', ''], ['', '', '', '', '']]
    schedule += [['', '', t.name, 'A', '1000'] for t in candidates]
    matched = compute_matched_model_names(title, schedule)
    return [t for t in candidates if t.name.upper() in matched]


def forecast(tasks, today, capacity=1.0, method='Weighted by complexity', horizon=366):
    """Return a new plan; never mutate input tasks or reuse a previous forecast."""
    if not math.isfinite(capacity) or capacity <= 0:
        raise ValueError('Daily capacity must be positive and finite.')
    if not isinstance(horizon, int) or horizon < 1 or horizon > 3660:
        raise ValueError('Forecast horizon must be between 1 and 3660 calendar days.')
    if method not in ('Weighted by complexity', 'Equal per task'):
        raise ValueError('Unknown allocation method.')
    tasks = sorted(tasks, key=lambda t: (t.priority, t.due or date.max, t.key))
    by_key = {t.key: t for t in tasks}
    if len(by_key) != len(tasks):
        raise ValueError('Duplicate project/task names are not allowed.')
    releases, issues = {}, {}
    for t in tasks:
        if (not isinstance(t.duration, int) or t.duration <= 0 or
                not math.isfinite(t.difficulty) or t.difficulty <= 0):
            raise ValueError('Duration must be a positive integer and difficulty positive and finite.')
        dates = [('Architecture', t.architecture), ('Floor', t.floor), ('Truss', t.truss)]
        missing = [label for label, value in dates if value is None]
        unknown = [key for key in t.predecessors if key not in by_key]
        if missing:
            issues[t.key] = 'Missing information: ' + ', '.join(missing)
        elif unknown:
            issues[t.key] = 'Unknown predecessor: ' + ', '.join(unknown)
        else:
            releases[t.key] = max(value for _, value in dates) + timedelta(days=1)

    # DFS catches cycles as well as descendants of unavailable/cyclic tasks.
    visiting, visited = set(), set()

    def check(key):
        if key in visiting:
            issues[key] = 'Dependency cycle'
            return False
        if key in visited:
            return key not in issues
        visiting.add(key)
        for predecessor in by_key[key].predecessors:
            if predecessor in by_key and not check(predecessor):
                issues.setdefault(key, 'Waiting for predecessor: ' + predecessor +
                                  ' (' + issues[predecessor] + ')')
        visiting.remove(key)
        visited.add(key)
        return key not in issues

    for t in tasks:
        check(t.key)
    total = {t.key: t.difficulty if method == 'Weighted by complexity' else 1.0 for t in tasks}
    remaining = dict(total)
    starts, finishes, allocations = {}, {}, []
    for offset in range(horizon):
        day = today + timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        available = capacity
        for t in tasks:
            key = t.key
            if (key in issues or key in finishes or releases[key] > day or
                    any(p not in finishes or finishes[p] >= day for p in t.predecessors)):
                continue
            amount = min(remaining[key], total[key] / t.duration, available)
            if amount <= 1e-12:
                continue
            starts.setdefault(key, day)
            allocations.append(Allocation(day, key, amount))
            remaining[key] -= amount
            available -= amount
            if remaining[key] <= max(1e-12, total[key] * 1e-12):
                finishes[key] = day
        if len(finishes) + len(issues) == len(tasks):
            break
    results = {}
    for t in tasks:
        key = t.key
        if key in issues:
            results[key] = Result('Waiting', releases.get(key), None, None, issues[key])
            continue
        start, finish = starts.get(key), finishes.get(key)
        status = 'Ready' if start == today else 'Scheduled' if start else 'Waiting'
        explanation = (f'Latest receipt + 1 calendar day = {releases[key]}. '
                       f'{total[key]:g} / {t.duration} = {total[key] / t.duration:g} units per business day; '
                       f'priority {t.priority}; daily capacity {capacity:g}.')
        if t.predecessors:
            explanation += ' Starts after predecessors finish: ' + ', '.join(t.predecessors) + '.'
        if finish is None:
            explanation += ' Incomplete within forecast horizon; increase capacity or horizon.'
        elif t.due and finish > t.due:
            explanation += f' Late: finishes {finish}, due {t.due}.'
        results[key] = Result(status, releases[key], start, finish, explanation)
    return Plan(results, tuple(allocations))
