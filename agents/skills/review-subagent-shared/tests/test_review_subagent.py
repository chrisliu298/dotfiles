"""Exercise the installed entrypoints against fake harnesses and an isolated tmux."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time
import uuid

import pytest

SKILLS = Path(__file__).resolve().parents[2]


@pytest.fixture(params=['claude', 'gpt'])
def harness(request, tmp_path):
    name = request.param
    env = dict(os.environ, HOME=str(tmp_path), CAPTURE=str(tmp_path / 'call.json'))
    env.pop('CODEX_REVIEW_SUBAGENT_ACTIVE', None)
    env.pop('REVIEW_SUBAGENT_NETWORK', None)
    env.pop('TMUX', None)
    backend = tmp_path / 'backend'
    backend.write_text(f'''#!{sys.executable}
import json, os, sys
from pathlib import Path
if '--version' in sys.argv:
    print('codex-cli ' + os.environ.get('MOCK_CODEX_VERSION', '0.159.2'))
    sys.exit(0)
Path(os.environ['CAPTURE']).write_text(json.dumps({{'args': sys.argv[1:], 'sentinel': os.environ.get('CODEX_REVIEW_SUBAGENT_ACTIVE')}}))
if '-p' in sys.argv or 'exec' in sys.argv:
    sys.stdin.read()
    print(os.environ.get('MOCK_RESULT', 'review result'))
    sys.exit(int(os.environ.get('MOCK_EXIT', '0')))
print('\\x1b[?2004hMOCK_READY', flush=True)
for line in sys.stdin:
    print('RECEIVED:' + line.strip(), flush=True)
    if 'EXIT_NOW' in line: sys.exit(7)
''')
    backend.chmod(0o755)
    (tmp_path / '.functions').write_text(f'c() {{ "{backend}" "$@"; }}\n')
    (tmp_path / 'codex').symlink_to(backend)
    canonical = tmp_path / '.local' / 'bin' / 'codex'
    canonical.parent.mkdir(parents=True)
    canonical.symlink_to(backend)
    tmux = shutil.which('tmux')
    socket = 'review-test-' + uuid.uuid4().hex
    if tmux:
        shim = tmp_path / 'tmux'
        shim.write_text(f'#!/bin/sh\nexec "{tmux}" -L {socket} -f /dev/null "$@"\n')
        shim.chmod(0o755)
    env['PATH'] = str(tmp_path) + os.pathsep + env['PATH']
    # Run through a symlink, just like the installed skill path.
    installed = tmp_path / 'installed'
    installed.symlink_to(SKILLS / f'{name}-subagent', target_is_directory=True)
    def run(*args, prompt='assignment', extra_env=None, alias=False):
        entry = installed / 'scripts' / (f'{name}-subagent' + ('-tmux' if alias else ''))
        return subprocess.run([str(entry), *args], input=prompt, text=True,
                              capture_output=True, env=env | (extra_env or {}), timeout=15)
    yield name, run, tmp_path
    if tmux:
        subprocess.run([tmux, '-L', socket, 'kill-server'], capture_output=True)


def test_once_pins_and_json(harness):
    name, run, tmp = harness
    result = run('--once', '--output-format', 'json')
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {'result': 'review result', 'exit_code': 0, 'is_error': False}
    call = json.loads((tmp / 'call.json').read_text())
    args = call['args']
    assert args[args.index('--model') + 1] == ('opus' if name == 'claude' else 'gpt-6.1-sol')
    assert call['sentinel'] == '1'
    if name == 'claude':
        assert args[args.index('--effort') + 1] == 'high'
    else:
        assert 'model_reasoning_effort="high"' in args
        assert args[args.index('--sandbox') + 1] == 'read-only'


@pytest.mark.parametrize('mode', ['--once', 'start'])
@pytest.mark.parametrize('network', ['0', '1'])
def test_gpt_network_sandbox_scope(harness, mode, network):
    name, run, tmp = harness
    if name != 'gpt':
        pytest.skip('GPT-only sandbox selection')
    if mode == 'start' and not shutil.which('tmux'):
        pytest.skip('tmux is required for network propagation checks')
    result = run(mode, extra_env={'REVIEW_SUBAGENT_NETWORK': network})
    assert result.returncode == 0, result.stderr
    session = result.stdout.strip() if mode == 'start' else None
    try:
        if session:
            wait_for(run, session, 'capture', 'MOCK_READY')
        args = json.loads((tmp / 'call.json').read_text())['args']
        assert args[args.index('--ask-for-approval') + 1] == 'never'
        assert args[args.index('--sandbox') + 1] == ('workspace-write' if network == '1' else 'read-only')
        assert ('sandbox_workspace_write.network_access=true' in args) == (network == '1')
        assert ('sandbox_workspace_write.writable_roots=[]' in args) == (network == '1')
    finally:
        if session:
            assert run('stop', session).returncode == 0


def test_gpt_ignores_other_codex_on_path(harness):
    name, run, tmp = harness
    if name != 'gpt':
        pytest.skip('GPT-only CLI selection')
    (tmp / 'codex').unlink()
    (tmp / 'codex').write_text('#!/bin/sh\necho wrong-cli >&2\nexit 99\n')
    (tmp / 'codex').chmod(0o755)
    result = run('--once')
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'review result'


@pytest.mark.parametrize('mode', ['--once', 'start'])
def test_gpt_rejects_old_cli_before_dispatch(harness, mode):
    name, run, tmp = harness
    if name != 'gpt':
        pytest.skip('GPT-only version requirement')
    result = run(mode, extra_env={'MOCK_CODEX_VERSION': '0.157.1'})
    assert result.returncode == 2
    assert '0.159.2' in result.stderr
    assert 'xu' in result.stderr
    assert not (tmp / 'call.json').exists()
    assert not run('list').stdout.strip()


def test_gpt_missing_canonical_cli_does_not_fall_back(harness):
    name, run, tmp = harness
    if name != 'gpt':
        pytest.skip('GPT-only CLI selection')
    (tmp / '.local' / 'bin' / 'codex').unlink()
    result = run('--once')
    assert result.returncode == 127
    assert 'dotfiles.sh' in result.stderr
    assert not (tmp / 'call.json').exists()


def test_codex_setup_repairs_old_link_and_updates_only_when_needed(tmp_path):
    prefix = tmp_path / 'npm-global'
    package_bin = prefix / 'lib' / 'node_modules' / '@openai' / 'codex' / 'bin' / 'codex.js'
    package_bin.parent.mkdir(parents=True)
    version = tmp_path / 'version'
    version.write_text('0.157.1')
    package_bin.write_text(f'#!/bin/sh\necho "codex-cli $(cat {shlex.quote(str(version))})"\n')
    package_bin.chmod(0o755)
    npm = tmp_path / 'npm'
    receipt = tmp_path / 'npm-update'
    npm.write_text(f'''#!/bin/sh
if [ "$1" = prefix ]; then
    echo {shlex.quote(str(prefix))}
else
    echo "$*" >> {shlex.quote(str(receipt))}
    echo 0.159.2 > {shlex.quote(str(version))}
fi
''')
    npm.chmod(0o755)
    canonical = tmp_path / '.local' / 'bin' / 'codex'
    canonical.parent.mkdir(parents=True)
    canonical.symlink_to(tmp_path / 'old-standalone')
    env = dict(os.environ, HOME=str(tmp_path), PATH=str(tmp_path) + os.pathsep + os.environ['PATH'])
    script = SKILLS.parents[1] / 'dotfiles.sh'
    command = f'source {shlex.quote(str(script))}; setup_codex_cli'
    for _ in range(2):
        result = subprocess.run(['bash', '-c', command], env=env, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        assert canonical.resolve() == package_bin
    assert receipt.read_text().splitlines() == ['install -g @openai/codex@latest']


@pytest.mark.parametrize('args', [('--model', 'other'), ('--effort', 'xhigh'), ('--settings', '{}')])
def test_override_rejected(harness, args):
    _, run, tmp = harness
    assert run('--once', *args).returncode == 2
    assert not (tmp / 'call.json').exists()


def test_failures_and_empty_result(harness):
    _, run, _ = harness
    r = run('--once', '--output-format', 'json', extra_env={'MOCK_EXIT': '9'})
    assert r.returncode == 9
    assert json.loads(r.stdout)['is_error'] is True
    r = run('--once', extra_env={'MOCK_RESULT': ''})
    assert r.returncode == 1
    assert 'empty response' in r.stderr
    assert run('--once', prompt=' \n ').returncode == 2
    assert run('--once', extra_env={'CODEX_REVIEW_SUBAGENT_ACTIVE': '1'}).returncode == 126


def wait_for(run, session, command, text):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        r = run(command, session)
        if text in r.stdout:
            return r.stdout
        time.sleep(.1)
    pytest.fail(f'{command}: missing {text!r}; last response: {r.stdout!r} {r.stderr!r}')


def test_default_tmux_lifecycle(harness):
    if not shutil.which('tmux'):
        pytest.skip('tmux is required for lifecycle checks')
    name, run, tmp = harness
    r = run()  # No mode flag must start a persistent session, not return a review.
    assert r.returncode == 0, r.stderr
    session = r.stdout.strip()
    assert session.startswith(name + '-review-')
    wait_for(run, session, 'capture', 'MOCK_READY')
    wait_for(run, session, 'status', 'input_ready=1')
    assert session in run('list').stdout
    assert run('send', session, prompt='FOLLOWUP_123').returncode == 0
    wait_for(run, session, 'capture', 'RECEIVED:')
    assert 'FOLLOWUP_123' in run('capture', session, alias=True).stdout
    assert run('interrupt', session).returncode == 0
    assert run('send', session, prompt='EXIT_NOW').returncode == 0
    wait_for(run, session, 'status', 'dead=1 exit_code=7')
    assert run('send', session).returncode == 1
    assert run('stop', session).returncode == 0
    assert session not in run('list').stdout
    assert run('status', session).returncode == 1
    assert run('stop', 'unrelated-session').returncode == 2


def test_paste_mode_tracker(tmp_path):
    state = tmp_path / 'state'
    proc = subprocess.Popen([str(SKILLS / 'review-subagent-shared' / 'paste-mode-tracker'), str(state)],
                            stdin=subprocess.PIPE)
    def feed(data, expected):
        proc.stdin.write(data)
        proc.stdin.flush()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if state.exists() and state.read_text().strip() == expected:
                return
            time.sleep(.02)
        pytest.fail(f'after {data!r}: expected {expected}, got {state.read_text() if state.exists() else None!r}')
    feed(b'plain output', '0')
    feed(b'\x1b[?1049;20', '0')  # Combined DECSET split across reads.
    feed(b'04h prompt', '1')
    feed(b'\x1b[?25l', '1')  # Unrelated private modes are ignored.
    feed(b'\x1b[?2004l', '0')
    feed(b'\x1b[?2004h', '1')
    proc.stdin.close()
    assert proc.wait(timeout=5) == 0
    assert not state.exists()


def test_cursor_tmux_lifecycle(tmp_path):
    tmux = shutil.which('tmux')
    if not tmux:
        pytest.skip('tmux is required for lifecycle checks')
    backend = tmp_path / 'cursor-agent'
    backend.write_text(f'''#!{sys.executable}
import sys
print('\\x1b[?2004hMOCK_READY', flush=True)
for line in sys.stdin:
    print('RECEIVED:' + line.strip(), flush=True)
''')
    backend.chmod(0o755)
    socket = 'review-test-' + uuid.uuid4().hex
    shim = tmp_path / 'tmux'
    shim.write_text(f'#!/bin/sh\nexec "{tmux}" -L {socket} -f /dev/null "$@"\n')
    shim.chmod(0o755)
    env = dict(os.environ, PATH=str(tmp_path) + os.pathsep + os.environ['PATH'], CURSOR_AGENT_BIN=str(backend))
    env.pop('CODEX_REVIEW_SUBAGENT_ACTIVE', None)
    env.pop('TMUX', None)
    installed = tmp_path / 'installed'
    installed.symlink_to(SKILLS / 'cursor-subagent', target_is_directory=True)
    def run(*args, prompt='assignment'):
        return subprocess.run([str(installed / 'scripts' / 'cursor-subagent-tmux'), *args], input=prompt,
                              text=True, capture_output=True, env=env, timeout=15)
    try:
        r = run('start')
        assert r.returncode == 0, r.stderr
        session = r.stdout.strip()
        wait_for(run, session, 'status', 'input_ready=1')
        assert run('send', session, prompt='FOLLOWUP_456').returncode == 0
        wait_for(run, session, 'capture', 'RECEIVED:FOLLOWUP_456')
        assert run('stop', session).returncode == 0
    finally:
        subprocess.run([tmux, '-L', socket, 'kill-server'], capture_output=True)
