"""Reject unfinished Cursor turns instead of promoting progress text to success."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


@pytest.fixture
def backend(tmp_path):
    executable = tmp_path / 'cursor-agent'
    capture = tmp_path / 'input.json'
    executable.write_text(f'''#!{sys.executable}
import json, os, sys
from pathlib import Path
Path({str(capture)!r}).write_text(json.dumps({{'args': sys.argv[1:], 'stdin': sys.stdin.read()}}))
print(os.environ['MOCK_EVENTS'])
print(os.environ.get('MOCK_ERROR', ''), file=sys.stderr)
sys.exit(int(os.environ.get('MOCK_EXIT', '0')))
''')
    executable.chmod(0o755)
    env = {key: os.environ[key] for key in ('PATH', 'HOME', 'TMPDIR') if key in os.environ}
    env.update(CURSOR_AGENT_BIN=str(executable), MOCK_EVENTS=json.dumps(
        {'type': 'result', 'subtype': 'success', 'is_error': False,
         'result': 'Finding: the brief omits its acceptance criterion.', 'session_id': 'test-session'}))
    return env, capture


def run(backend, *options):
    env, _ = backend
    return subprocess.run([str(SCRIPTS / 'review-subagent'), 'gemini', '--once', *options],
                          input='Read only this brief.', text=True,
                          capture_output=True, env=env, timeout=10)


@pytest.mark.parametrize('options', [('--mode', 'plan'), ('--mode=plan',), ('--plan',),
                                   ('--mode', 'ask'), ('--mode=ask',)])
def test_mode_selection_is_rejected(backend, options):
    result = run(backend, *options)
    assert result.returncode == 2
    assert not backend[1].exists()


@pytest.mark.parametrize('options', [(), ('--output-format', 'json'), ('--output-format', 'text')])
@pytest.mark.parametrize('exit_code', [0, 1])
def test_opening_without_terminal_result_is_not_success(backend, options, exit_code):
    env, _ = backend
    env.update(MOCK_EVENTS=json.dumps({'type': 'assistant', 'message': {
        'content': [{'type': 'text', 'text': 'I will start by reading the brief.'}]}}),
        MOCK_EXIT=str(exit_code), MOCK_ERROR='WritableIterable is closed' if exit_code else '')
    result = run(backend, *options)
    assert result.returncode != 0
    assert 'I will start' not in result.stdout


@pytest.mark.parametrize('result_text', ['', '  \n '])
def test_empty_terminal_result_is_not_success(backend, result_text):
    env, _ = backend
    env['MOCK_EVENTS'] = json.dumps({'type': 'result', 'is_error': False, 'result': result_text})
    assert run(backend).returncode != 0


def test_complete_result_after_stream_close_is_recoverable(backend):
    env, capture = backend
    env.update(MOCK_EXIT='1', MOCK_ERROR='WritableIterable is closed')
    result = run(backend)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'Finding: the brief omits its acceptance criterion.'
    call = json.loads(capture.read_text())
    assert call['args'][-1].startswith('Read only this brief.')
    assert call['args'][-1].count('Complete the entire read-only assignment in this turn') == 1
    assert call['stdin'] == ''
    assert call['args'][-2] == '--'


@pytest.mark.parametrize('suffix', ['\n{"type":', '\n' + json.dumps({'type': 'result', 'is_error': True})])
def test_truncated_or_failed_terminal_stream_is_not_success(backend, suffix):
    backend[0]['MOCK_EVENTS'] += suffix
    assert run(backend).returncode != 0


def test_json_output_contains_verified_terminal_result(backend):
    result = run(backend, '--output-format', 'json')
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        'result': 'Finding: the brief omits its acceptance criterion.', 'exit_code': 0, 'is_error': False}
    assert 'session_id=test-session' in result.stderr
