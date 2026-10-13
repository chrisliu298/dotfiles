"""Cursor reviews must start in their authorized workspace without a trust retry."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


@pytest.fixture
def cursor_backend(tmp_path):
    capture = tmp_path / 'args.json'
    backend = tmp_path / 'cursor-agent'
    backend.write_text(f'''#!{sys.executable}
import json, sys
from pathlib import Path
Path({str(capture)!r}).write_text(json.dumps(sys.argv[1:]))
if '--trust' not in sys.argv:
    print('Workspace trust required', file=sys.stderr)
    sys.exit(9)
print(json.dumps({{'type': 'result', 'is_error': False, 'result': 'review complete'}}))
''')
    backend.chmod(0o755)
    env = {key: os.environ[key] for key in ('PATH', 'HOME', 'TMPDIR') if key in os.environ}
    env['CURSOR_AGENT_BIN'] = str(backend)
    return env, capture


@pytest.mark.parametrize('options', [[], ['--output-format', 'json']])
def test_one_shot_trusts_authorized_workspace(cursor_backend, options):
    env, capture = cursor_backend
    result = subprocess.run([str(SCRIPTS / 'review-subagent'), 'cursor', '--once', *options],
                            input='Read only this brief.', text=True,
                            capture_output=True, env=env, timeout=10)
    assert result.returncode == 0, result.stderr
    args = json.loads(capture.read_text())
    assert args.count('--trust') == 1
    assert '--mode' not in args
    assert args[args.index('--model') + 1] == 'claude-opus-5-5-high'
