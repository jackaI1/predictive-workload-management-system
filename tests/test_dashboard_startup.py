"""The dashboard must remain locked when no local secret file exists."""
import os
from pathlib import Path
import shutil
import subprocess
import sys


def test_missing_secrets_file_shows_setup_error_and_keeps_dashboard_locked(tmp_path):
    # Copy only public source so neither developer secrets nor service-account
    # files can be read by the app under test.
    source = Path(__file__).resolve().parents[1] / "app.py"
    shutil.copy2(source, tmp_path / "app.py")
    env = {key: value for key, value in os.environ.items()
           if key in ("PATH", "LANG", "SYSTEMROOT", "WINDIR")}
    env.update(HOME=str(tmp_path), PYTHONDONTWRITEBYTECODE="1",
               STREAMLIT_BROWSER_GATHER_USAGE_STATS="false")
    script = """
from streamlit.testing.v1 import AppTest
app = AppTest.from_file('app.py').run(timeout=30)
assert not app.exception, 'Missing configuration must not crash the app'
assert len(app.error) == 1
assert 'DASHBOARD_PASSWORD is not set' in app.error[0].value
assert not app.text_input, 'Authentication must stay locked without a secret'
assert not app.dataframe, 'No dashboard data may be displayed'
"""
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path,
                            env=env, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, "Dashboard startup check failed:\n" + result.stderr[-3000:]


def test_non_ascii_password_is_rejected_without_crashing(tmp_path):
    shutil.copy2(Path(__file__).resolve().parents[1] / 'app.py', tmp_path / 'app.py')
    (tmp_path / '.streamlit').mkdir()
    (tmp_path / '.streamlit' / 'secrets.toml').write_text('DASHBOARD_PASSWORD="synthetic-only"\n')
    env = {key: value for key, value in os.environ.items() if key in ('PATH', 'LANG', 'SYSTEMROOT', 'WINDIR')}
    env.update(HOME=str(tmp_path), PYTHONDONTWRITEBYTECODE='1')
    script = '''
from streamlit.testing.v1 import AppTest
app = AppTest.from_file('app.py').run(timeout=30)
app.text_input[0].input('密碼').run()
assert not app.exception
assert any('Invalid credentials' in e.value for e in app.error)
assert not app.dataframe
'''
    result = subprocess.run([sys.executable, '-c', script], cwd=tmp_path,
                            env=env, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stderr[-2500:]
