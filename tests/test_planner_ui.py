"""Exercise the public Streamlit entrypoint without credentials or sockets."""
from pathlib import Path
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


from datetime import date


class FixedDate(date):
    @classmethod
    def today(cls):
        return date(2026, 10, 19)


def demo(monkeypatch):
    monkeypatch.setattr('planner_ui.date', FixedDate)
    monkeypatch.setenv('WORKLOAD_DEMO', '1')
    return AppTest.from_file(str(ROOT / 'app.py')).run(timeout=30)


def test_demo_opens_forecast_and_updates_receipts_allocation_and_scope(monkeypatch):
    app = demo(monkeypatch)
    assert not app.exception
    assert any(t.value == 'Workload forecast' for t in app.title)
    assert [m.value for m in app.metric][:3] == ['4', '1', '1']
    app.selectbox(key='explain_task').set_value('D12345/BLOCK 1').run()
    assert any('Missing information: Floor' in e.value for e in app.info)
    app.button(key='fill_receipt').click().run()
    assert not app.exception
    assert app.metric[2].value == '0'
    app.radio(key='allocation_method').set_value('Equal per task').run()
    assert not app.exception
    app.text_input(key='scope_title').set_value('D12345 AA1 TO 3').run()
    assert app.metric[0].value == '3'
    app.text_input(key='scope_title').set_value('no project').run()
    assert app.metric[0].value == '0'
    assert not app.exception
    app.radio(key='dashboard_page').set_value('KPI history').run()
    assert not app.exception
    assert len(app.get('plotly_chart')) == 3


def test_dependency_edits_and_missing_dates_replan(monkeypatch):
    app = demo(monkeypatch)
    # Streamlit's data editor transmits edited_rows; use its public session state
    # representation because AppTest does not yet expose an editor input widget.
    app.session_state['scenario_editor'] = {'edited_rows': {0: {'Floor received': None}},
                                             'added_rows': [], 'deleted_rows': []}
    app.run()
    assert not app.exception
    assert int(app.metric[2].value) >= 3


def test_fill_receipt_preserves_pending_date_and_duration_edits(monkeypatch):
    app = demo(monkeypatch)
    app.session_state['scenario_editor'] = {
        'edited_rows': {0: {'Floor received': '2026-12-01', 'Duration': 1}},
        'added_rows': [], 'deleted_rows': []}
    app.run()
    app.button(key='fill_receipt').click().run()
    assert not app.exception
    assert app.session_state['scenario_base'].iloc[0]['Duration'] == 1
    assert str(app.session_state['scenario_base'].iloc[0]['Floor received']) == '2026-12-01'


def test_cleared_predecessors_are_empty_not_unknown():
    import pandas as pd
    from datetime import date
    from planner_ui import generated_scenario, tasks_from_frame
    for empty in (None, float('nan'), pd.NA, ''):
        frame = generated_scenario(date(2026, 10, 19))
        frame.at[1, 'Predecessor'] = empty
        assert tasks_from_frame(frame)[1].predecessors == ()


def test_scenario_edits_survive_navigation_to_kpi_history(monkeypatch):
    app = demo(monkeypatch)
    app.session_state['scenario_editor'] = {
        'edited_rows': {0: {'Duration': 1}}, 'added_rows': [], 'deleted_rows': []}
    app.run()
    assert app.session_state['scenario_current'].iloc[0]['Duration'] == 1
    app.radio(key='dashboard_page').set_value('KPI history').run()
    app.radio(key='dashboard_page').set_value('Forecast').run()
    assert not app.exception
    assert app.session_state['scenario_current'].iloc[0]['Duration'] == 1
