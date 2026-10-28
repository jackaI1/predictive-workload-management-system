"""Streamlit scenario editor; all example rows are generated, never fetched."""
from datetime import date, timedelta
import pandas as pd
import plotly.express as px
import streamlit as st
from planner import Task, forecast, select_tasks


def generated_scenario(today):
    received = today - timedelta(days=3)
    return pd.DataFrame([
        {'Project': project, 'Task': name, 'Duration': duration, 'Difficulty': difficulty,
         'Priority': priority, 'Due': today + timedelta(days=14),
         'Architecture received': received, 'Floor received': floor,
         'Truss received': received, 'Predecessor': predecessor}
        for project, name, duration, difficulty, priority, floor, predecessor in [
            ('P12345', 'AA1', 3, 1.2, 1, received, ''),
            ('P12345', 'AA2', 3, 1.6, 2, received, 'P12345/AA1'),
            ('P12345', 'AA3', 3, 2.0, 3, received, 'P12345/AA2'),
            ('P12345', 'BLOCK 1', 2, 1.0, 4, None, 'P12345/AA3'),
            ('P12346', 'BB1', 2, 1.4, 2, received, ''),
        ]
    ])


def optional_date(value):
    return None if pd.isna(value) else pd.Timestamp(value).date()


def tasks_from_frame(frame):
    tasks = []
    for row in frame.to_dict('records'):
        if pd.isna(row['Duration']) or float(row['Duration']) != int(row['Duration']):
            raise ValueError('Duration must be a whole number of business days.')
        if pd.isna(row['Priority']) or float(row['Priority']) != int(row['Priority']):
            raise ValueError('Priority must be a whole number (lower numbers go first).')
        predecessor = row['Predecessor']
        predecessor = '' if pd.isna(predecessor) else str(predecessor)
        tasks.append(Task(
            project=str(row['Project']).strip().upper(), name=str(row['Task']).strip().upper(),
            duration=int(row['Duration']), difficulty=float(row['Difficulty']),
            priority=int(row['Priority']), due=optional_date(row['Due']),
            architecture=optional_date(row['Architecture received']),
            floor=optional_date(row['Floor received']), truss=optional_date(row['Truss received']),
            predecessors=tuple(p.strip().upper() for p in predecessor.split(',') if p.strip()),
        ))
    return tasks


def render_planner():
    st.title('Workload forecast')
    st.caption('Plan a synthetic scenario. Edit inputs to recalculate start dates and daily capacity.')
    if 'scenario_base' not in st.session_state:
        st.session_state.scenario_base = generated_scenario(date.today())
    with st.sidebar:
        today = st.date_input('Plan from', value=date.today(), key='plan_from')
        capacity = st.number_input('Daily capacity (work units)', min_value=0.05, value=1.0, step=0.05)
        horizon = st.number_input('Forecast horizon (calendar days)', min_value=1, max_value=3660, value=366)
        st.caption('Lower priority numbers go first, then earlier due dates. Weekends have no capacity.')
        if st.button('Fill missing receipt', key='fill_receipt',
                     help='Set missing Floor received values to the planning date.'):
            # Apply pending table edits before replacing the editor baseline.
            base = st.session_state.get('scenario_current', st.session_state.scenario_base).copy()
            edits = st.session_state.get('scenario_editor', {}).get('edited_rows', {})
            for row, changes in edits.items():
                for column, value in changes.items():
                    base.at[int(row), column] = value
            for column in ('Due', 'Architecture received', 'Floor received', 'Truss received'):
                base[column] = base[column].map(optional_date)
            base['Floor received'] = base['Floor received'].fillna(today)
            st.session_state.scenario_base = base
            st.session_state.scenario_current = base.copy()
            st.session_state.pop('scenario_editor', None)
        st.caption('Scenario changes last for this browser session; no tracker or sheet is modified.')
    title = st.text_input('Task title to parse', value='P12345 AA1 TO 3 AND BLOCK 1', key='scope_title')
    forecast_tab, edit_tab, rules_tab = st.tabs(['Forecast', 'Edit scenario', 'How it works'])
    with edit_tab:
        st.caption('Predecessors use PROJECT/TASK; separate multiple predecessors with commas. Clear a receipt to mark it missing.')
        if 'scenario_editor' not in st.session_state and 'scenario_current' in st.session_state:
            st.session_state.scenario_base = st.session_state.scenario_current.copy()
        edited = st.data_editor(st.session_state.scenario_base, key='scenario_editor', hide_index=True,
                               width='stretch', disabled=['Project', 'Task'], column_config={
            'Duration': st.column_config.NumberColumn(min_value=1, step=1),
            'Difficulty': st.column_config.NumberColumn(min_value=0.01),
            'Priority': st.column_config.NumberColumn(step=1),
            **{column: st.column_config.DateColumn(format='YYYY-MM-DD') for column in
               ('Due', 'Architecture received', 'Floor received', 'Truss received')},
        })
    st.session_state.scenario_current = edited.copy()
    method = forecast_tab.radio('Allocation method', ['Weighted by complexity', 'Equal per task'],
                                horizontal=True, key='allocation_method')
    try:
        tasks = tasks_from_frame(edited)
        selected = select_tasks(title, tasks)
        plan = forecast(tasks, today, capacity=float(capacity), horizon=int(horizon), method=method)
    except (ValueError, TypeError, OverflowError) as error:
        st.error(str(error))
        return
    keys = {t.key for t in selected}
    rows = [{'Task': t.name, 'Project': t.project, 'Status': plan.results[t.key].status,
             'Startable after receipts': plan.results[t.key].startable,
             'Start': plan.results[t.key].start, 'Finish': plan.results[t.key].finish,
             'Explanation': plan.results[t.key].explanation} for t in selected]
    daily = pd.DataFrame([{'Business day': a.day, 'Task': a.task, 'Work units': a.units}
                          for a in plan.allocations if a.task in keys])
    with forecast_tab:
        metrics = st.columns(4)
        metrics[0].metric('Selected tasks', len(selected))
        metrics[1].metric('Ready in this scenario', sum(r['Status'] == 'Ready' for r in rows))
        metrics[2].metric('Waiting for inputs / task', sum(r['Status'] == 'Waiting' for r in rows))
        peak = daily.groupby('Business day')['Work units'].sum().max() if not daily.empty else 0
        metrics[3].metric('Peak allocated load / day', f'{peak:.2f}')
        with st.expander('Parsed scope'):
            st.write([t.key for t in selected])
        if not selected:
            st.info('No matching tasks. Enter a project code and models, blocks or lots from Edit scenario.')
        else:
            st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')
            explain = st.selectbox('Explain task', [t.key for t in selected], key='explain_task')
            st.info(plan.results[explain].explanation)
            timeline = [dict(Task=f"{r['Project']}/{r['Task']}", Start=r['Start'],
                             Finish=r['Finish'] + timedelta(days=1), Status=r['Status'])
                        for r in rows if r['Start'] and r['Finish']]
            st.subheader('When work becomes startable')
            if timeline:
                fig = px.timeline(pd.DataFrame(timeline), x_start='Start', x_end='Finish', y='Task', color='Status')
                fig.update_yaxes(autorange='reversed')
                st.plotly_chart(fig, width='stretch')
            else:
                st.info('No complete tasks in this forecast. Check missing receipts, dependencies and horizon.')
            st.subheader('Daily allocation across the forecast')
            if not daily.empty:
                fig = px.bar(daily, x='Business day', y='Work units', color='Task', barmode='stack')
                fig.add_hline(y=capacity, line_dash='dot', annotation_text='Daily capacity (all tasks)')
                st.plotly_chart(fig, width='stretch')
                st.download_button('Download allocations (CSV)', daily.to_csv(index=False), 'allocations.csv', 'text/csv')
    with rules_tab:
        st.write('Startability is one calendar day after the latest receipt. Allocation begins on a business day, '
                 'after all predecessors finish. A block can depend on every model it contains.')
        st.write('Weighted work = difficulty; equal work = 1 per task. Daily requested work = work / duration. '
                 'Capacity is shared in priority, due-date and task-name order; unused fractions can go to another project. '
                 'Reduced capacity may extend a task. All scenario tasks compete for capacity, even outside the parsed scope.')
        st.write('Ready means allocated on the planning date. Scheduled means allocated later. Waiting means '
                 'missing information, invalid dependencies, or no capacity within the horizon. Explanations include '
                 'receipt dates, rates, priority, capacity, predecessors, horizon limits and late finishes.')
        st.caption('Synthetic planning scenario. No people are assigned or dispatched. No holiday calendar is applied.')
