"""Synthetic scenarios for the public forecast planner."""
from dataclasses import replace
from datetime import date, timedelta
import math
import pytest
from planner import Task, forecast, select_tasks

DAY = date(2026, 10, 19)  # Monday


def task(name='AA1', **kwargs):
    values = dict(project='D12345', name=name, duration=2, difficulty=1.0,
                  architecture=DAY-timedelta(days=3), floor=DAY-timedelta(days=3),
                  truss=DAY-timedelta(days=3))
    values.update(kwargs)
    return Task(**values)


def test_title_expansion_selects_models_blocks_and_project_exactly():
    tasks = [task('AA1'), task('AA2'), task('AA3'), task('BLOCK 1'),
             task('BLOCK 10'), task('AA1', project='D123456')]
    assert [t.name for t in select_tasks('D12345 AA1 TO 3 AND BLOCK 1', tasks)] == [
        'AA1', 'AA2', 'AA3', 'BLOCK 1']
    assert select_tasks('no project', tasks) == []


def test_receipt_sets_start_date_and_missing_information_blocks_descendants():
    a = task(floor=None)
    b = task('AA2', predecessors=(a.key,))
    plan = forecast([a, b], DAY)
    assert plan.results[a.key].status == 'Waiting'
    assert 'Floor' in plan.results[a.key].explanation
    assert plan.results[b.key].start is None
    a = replace(a, floor=DAY)
    plan = forecast([a, b], DAY)
    assert plan.results[a.key].start == DAY + timedelta(days=1)
    assert plan.results[b.key].start > plan.results[a.key].finish
    assert plan.results[a.key].status == 'Scheduled'


def test_ready_waiting_priority_due_dates_and_split_capacity():
    low = task('AA1', priority=3)
    high = task('AA2', priority=1)
    plan = forecast([low, high], DAY, capacity=.75)
    allocations = [x for x in plan.allocations if x.day == DAY]
    assert [(x.task, x.units) for x in allocations] == [(high.key, .5), (low.key, .25)]
    assert plan.results[high.key].status == 'Ready'
    assert plan.results[high.key].finish < plan.results[low.key].finish
    for day in {x.day for x in plan.allocations}:
        assert sum(x.units for x in plan.allocations if x.day == day) <= .75 + 1e-9
        assert day.weekday() < 5
    early = replace(low, priority=1, due=DAY)
    assert forecast([high, early], DAY, capacity=.5).allocations[0].task == early.key


def test_weighted_equal_and_live_replanning_conserve_work():
    tasks = [task('AA1', difficulty=2), task('AA2')]
    weighted = forecast(tasks, DAY, capacity=1)
    equal = forecast(tasks, DAY, capacity=1, method='Equal per task')
    assert sum(x.units for x in weighted.allocations) == pytest.approx(3)
    assert sum(x.units for x in equal.allocations) == pytest.approx(2)
    assert weighted.allocations != equal.allocations
    changed = forecast([replace(tasks[0], truss=DAY+timedelta(days=3)), tasks[1]], DAY)
    assert changed.results[tasks[0].key].start == DAY+timedelta(days=4)
    assert '2 / 2' in weighted.results[tasks[0].key].explanation
    assert weighted == forecast(list(reversed(tasks)), DAY, capacity=1)


def test_block_waits_for_all_members_and_weekend_receipt():
    a = task(truss=date(2026, 10, 23))
    block = task('BLOCK 1', predecessors=(a.key,))
    plan = forecast([a, block], DAY)
    assert plan.results[a.key].start == date(2026, 10, 26)
    assert plan.results[block.key].start > plan.results[a.key].finish


@pytest.mark.parametrize('kwargs', [{'capacity':0}, {'capacity':math.nan}, {'horizon':0}, {'method':'bogus'}])
def test_invalid_settings_are_rejected(kwargs):
    with pytest.raises(ValueError):
        forecast([task()], DAY, **kwargs)


@pytest.mark.parametrize('change', [{'duration':0}, {'difficulty':math.inf}, {'difficulty':-1}])
def test_invalid_work_is_rejected(change):
    with pytest.raises(ValueError):
        forecast([task(**change)], DAY)


def test_duplicate_unknown_cycle_and_horizon_do_not_silently_schedule():
    a = task()
    with pytest.raises(ValueError, match='Duplicate'):
        forecast([a, a], DAY)
    unknown = forecast([replace(a, predecessors=('D12345/UNKNOWN',))], DAY)
    assert 'Unknown predecessor' in unknown.results[a.key].explanation
    b = task('AA2', predecessors=(a.key,))
    cycle = forecast([replace(a, predecessors=(b.key,)), b], DAY)
    assert all('cycle' in r.explanation for r in cycle.results.values())
    short = forecast([a], DAY, horizon=1)
    assert short.results[a.key].finish is None
    assert 'horizon' in short.results[a.key].explanation


def test_capacity_can_split_a_day_across_projects():
    a, b = task(duration=2), task('BB1', project='D12346', duration=2)
    plan = forecast([a, b], DAY, capacity=1)
    assert {x.task for x in plan.allocations if x.day == DAY} == {a.key, b.key}
    assert sum(x.units for x in plan.allocations if x.day == DAY) == 1
