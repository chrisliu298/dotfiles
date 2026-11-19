"""Routing, parallel startup, partial failures, and output preservation."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import signal

import pytest


SOURCE = Path(__file__).resolve().parents[1]


@pytest.fixture
def unified(tmp_path):
    skills = tmp_path / 'skills'
    target = skills / 'agent-team'
    shutil.copytree(SOURCE / 'scripts', target / 'scripts')
    # Replace the copied session runner with a recording fake.
    runner = target / 'scripts' / 'review-subagent'
    runner.unlink()
    runner.write_text(f'''#!{sys.executable}
import json, os, sys, time
from pathlib import Path
backend, action, *args = sys.argv[1:]
root = Path(os.environ['HOME'])
prompt = sys.stdin.read()
with (root / 'calls.jsonl').open('a') as out:
    out.write(json.dumps({{'backend': backend, 'action': action, 'args': args, 'prompt': prompt}}) + '\\n')
if action == 'start':
    started = root / 'started'
    started.mkdir(exist_ok=True)
    (started / str(os.getpid())).touch()
    deadline = time.monotonic() + 3
    while len(list(started.iterdir())) < int(os.environ.get('EXPECTED_STARTS', '1')):
        if time.monotonic() >= deadline:
            print('startup was serialized', file=sys.stderr)
            sys.exit(9)
        time.sleep(.02)
    print(backend + '-review-' + str(os.getpid()))
elif action == '--once':
    if os.environ.get('HANG_BACKEND') == backend:
        import signal, subprocess
        (root / 'runner.pid').write_text(str(os.getpid()))
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        descendant = subprocess.Popen([sys.executable, '-c', 'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)'])
        (root / 'descendant.pid').write_text(str(descendant.pid))
        while True: time.sleep(1)
    if os.environ.get('EMPTY_BACKEND') == backend: sys.exit(0)
    # Split multi-byte characters across writes, like a streamed CLI reply.
    for byte in '结论🙂'.encode('utf8'):
        os.write(1, bytes([byte]))
        time.sleep(.003)
    print()
elif action == 'wait':
    if os.environ.get('EMPTY_BACKEND') == backend: sys.exit(0)
    print('ANSWER:' + backend + ':' + args[0])
elif action == 'send' and backend in ('carbon', 'neon'):
    print('delivery unconfirmed; do not resend automatically', file=sys.stderr)
    sys.exit(124)
if os.environ.get('FAIL_BACKEND') == backend: sys.exit(7)
''')
    runner.chmod(0o755)
    (tmp_path / '.functions').write_text('c() { :; }\n')
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    for name in ('tmux', 'jq', 'cursor-agent'):
        path = bin_dir / name
        path.write_text('#!/bin/sh\nexit 0\n')
        path.chmod(0o755)
    codex = tmp_path / '.local/bin/codex'
    codex.parent.mkdir(parents=True)
    codex.write_text('#!/bin/sh\nprintf "codex-cli 0.160.1\\n"\n')
    codex.chmod(0o755)
    ark = codex.parent / 'codex-ark'
    ark.write_text('#!/bin/sh\n')
    ark.chmod(0o755)
    env = {key: os.environ[key] for key in ('PATH', 'LANG') if key in os.environ}
    env.update(HOME=str(tmp_path), PATH=str(bin_dir) + os.pathsep + env['PATH'],
               CURSOR_AGENT_BIN=str(bin_dir / 'cursor-agent'),
               ARK_API_KEY='test-key', ARK_OPERATOR_ID='0', ARK_OPERATOR_EMAIL='test@example.com')
    # No legacy manual-enabled file or per-caller version: both use this one skill.
    entry = tmp_path / 'installed-review'
    entry.symlink_to(target, target_is_directory=True)
    def run(*args, prompt='审查同一任务 $() `literal`', extra_env=None):
        return subprocess.run([str(entry / 'scripts/agent-team'), *args], input=prompt,
                              capture_output=True, text=True, env=env | (extra_env or {}), timeout=12)
    run.entry = str(entry / 'scripts/agent-team')
    run.env = env
    return run, tmp_path


def test_backends_start_concurrently_with_same_assignment(unified):
    run, root = unified
    outcome = run('start', '--effort', 'high', '--backend', 'claude', '--backend', 'sol', '--backend', 'neon',
                  extra_env={'EXPECTED_STARTS': '3'})
    assert outcome.returncode == 0, outcome.stderr
    manifest = json.loads(outcome.stdout)
    assert manifest['errors'] == []
    assert [item['backend'] for item in manifest['sessions']] == ['claude', 'sol', 'neon']
    assert all('instance' not in item for item in manifest['sessions'])
    handles = [item['session'] for item in manifest['sessions']]
    assert len(set(handles)) == 3
    calls = [json.loads(line) for line in (root / 'calls.jsonl').read_text().splitlines()]
    assert all(call['prompt'] == '审查同一任务 $() `literal`' for call in calls)
    replies = run('wait', *handles, '--timeout', '8')
    assert replies.returncode == 0, replies.stderr
    assert [item['session'] for item in json.loads(replies.stdout)['results']] == handles
    assert all(item['args'][-2:] == ['--timeout', '8'] for item in
               map(json.loads, (root / 'calls.jsonl').read_text().splitlines()) if item['action'] == 'wait')


def test_unavailable_backend_preserves_successful_handles_without_fallback(unified):
    run, root = unified
    (root / '.local/bin/codex').unlink()
    outcome = run('start', '--effort', 'high', '--backend', 'claude', '--backend', 'sol')
    assert outcome.returncode == 1
    manifest = json.loads(outcome.stdout)
    assert len(manifest['sessions']) == 1 and manifest['sessions'][0]['backend'] == 'claude'
    assert manifest['errors'][0]['backend'] == 'sol'
    calls = [json.loads(line) for line in (root / 'calls.jsonl').read_text().splitlines()]
    assert [item['backend'] for item in calls] == ['claude']


def test_handle_survives_nonzero_exit_after_session_was_created(unified):
    run, _ = unified
    outcome = run('start', '--effort', 'high', '--backend', 'claude', '--backend', 'sol', extra_env={'FAIL_BACKEND': 'sol'})
    assert outcome.returncode == 1
    manifest = json.loads(outcome.stdout)
    assert [item['backend'] for item in manifest['sessions']] == ['claude', 'sol']
    assert manifest['errors'][0]['backend'] == 'sol'
    assert manifest['errors'][0]['exit_code'] == 7


def test_all_backends_use_one_skill(unified):
    run, _ = unified
    backends = run('backends')
    assert [item['backend'] for item in json.loads(backends.stdout)['backends']] == ['claude', 'sol', 'astra', 'carbon', 'neon']
    assert all(item['available'] for item in json.loads(backends.stdout)['backends'])
    outcome = run('--once', '--effort', 'high', '--backend', 'claude', '--backend', 'sol', '--backend', 'astra', '--backend', 'carbon',
                  '--backend', 'neon')
    assert outcome.returncode == 0, outcome.stderr
    replies = json.loads(outcome.stdout)['results']
    assert [item['backend'] for item in replies] == ['claude', 'sol', 'astra', 'carbon', 'neon']
    assert all(item['result'] == '结论🙂' for item in replies)


def test_astra_requires_credentials(unified):
    run, _ = unified
    backends = run('backends', extra_env={'ARK_API_KEY': ''})
    astra = next(item for item in json.loads(backends.stdout)['backends'] if item['backend'] == 'astra')
    assert not astra['available'] and 'ARK_API_KEY' in astra['reason']
    sol = next(item for item in json.loads(backends.stdout)['backends'] if item['backend'] == 'sol')
    assert sol['available']


def test_batch_retains_each_failure_and_cursor_delivery_uncertainty(unified):
    run, _ = unified
    outcome = run('--once', '--effort', 'high', '--backend', 'claude', '--backend', 'sol', extra_env={'FAIL_BACKEND': 'sol'})
    assert outcome.returncode == 1
    replies = json.loads(outcome.stdout)['results']
    assert replies[0]['exit_code'] == 0 and replies[1]['exit_code'] == 7
    sent = run('send', 'neon-review-old', 'cursor-review-old', 'claude-review-old')
    assert sent.returncode == 124
    replies = json.loads(sent.stdout)['results']
    # A session started under the former cursor name is a carbon session.
    assert [item['backend'] for item in replies] == ['neon', 'carbon', 'claude']
    assert [item['delivery'] for item in replies] == ['unconfirmed', 'unconfirmed', 'submitted']


def test_per_instance_prompt_files_start_distinct_assignments_in_one_call(unified):
    run, root = unified
    (root / 'correctness.md').write_text('看正确性')
    (root / 'tests.md').write_text('看测试')
    outcome = run('start', '--effort', 'high', '--backend', f'claude={root / "correctness.md"}', '--backend', 'sol',
                  '--backend', f'carbon={root / "tests.md"}', prompt='共享任务', extra_env={'EXPECTED_STARTS': '3'})
    assert outcome.returncode == 0, outcome.stderr
    calls = {call['backend']: call['prompt'] for call in
             map(json.loads, (root / 'calls.jsonl').read_text().splitlines())}
    assert calls == {'claude': '看正确性', 'sol': '共享任务', 'carbon': '看测试'}


def test_prompt_files_make_stdin_optional(unified):
    run, root = unified
    (root / 'a.md').write_text('任务甲')
    outcome = subprocess.run([run.entry, '--once', '--effort', 'high', '--backend', f'sol={root / "a.md"}'], stdin=subprocess.DEVNULL,
                             capture_output=True, text=True, env=run.env, timeout=12)
    assert outcome.returncode == 0, outcome.stderr
    assert json.loads((root / 'calls.jsonl').read_text())['prompt'] == '任务甲'


@pytest.mark.parametrize('spec', ['sol=missing.md', 'sol='])
def test_unreadable_prompt_file_dispatches_nothing(unified, spec):
    run, root = unified
    assert run('start', '--effort', 'high', '--backend', spec).returncode == 2
    assert not (root / 'calls.jsonl').exists()


@pytest.mark.parametrize('action', ['start', '--once'])
@pytest.mark.parametrize('backends', [('claude', 'claude'), ('sol', 'neon', 'sol=prompt.md')])
def test_each_backend_runs_at_most_once_per_call(unified, action, backends):
    run, root = unified
    (root / 'prompt.md').write_text('x')
    outcome = subprocess.run([run.entry, action, '--effort', 'high', *(arg for backend in backends for arg in ('--backend', backend))],
                             input='x', capture_output=True, text=True, env=run.env, cwd=root, timeout=12)
    assert outcome.returncode == 2 and 'at most once' in outcome.stderr
    assert not (root / 'calls.jsonl').exists()


@pytest.mark.parametrize('options', [[], ['--backend', 'unknown'], ['--backend', 'muse'], ['--backend', 'sol'], ['--backend', 'sol', '--effort', 'low'], ['--backend', 'sol', '--effort'],
                                   ['--backend', 'sol', '--model', 'gpt-6.2-sol'],
                                   ['--backend', 'carbon', '--mode', 'ask'], ['--backend', 'cursor'], ['--backend', 'gemini'], ['--network', '--backend', 'sol']])
def test_invalid_selection_dispatches_nothing(unified, options):
    run, root = unified
    assert run('start', *options).returncode == 2
    assert not (root / 'calls.jsonl').exists()


@pytest.mark.parametrize('former, hint', [('cursor', 'renamed to carbon'), ('gemini', 'renamed to carbon'),
                                          ('gpt', 'renamed to sol'), ('ark', 'renamed to astra'),
                                          ('ark-sol', 'removed'), ('pro', 'ChatGPT Pro is not available'),
                                          ('hydro', 'replaced by neon')])
def test_former_backend_names_dispatch_nothing_and_name_the_replacement(unified, former, hint):
    run, root = unified
    outcome = run('start', '--effort', 'high', '--backend', former)
    assert outcome.returncode == 2 and hint in outcome.stderr
    assert not (root / 'calls.jsonl').exists()


def test_sessions_under_former_names_reach_the_renamed_backend(unified):
    run, root = unified
    replies = run('wait', 'gpt-review-old', 'ark-review-old', 'cursor-review-old')
    assert replies.returncode == 0, replies.stderr
    assert [item['backend'] for item in json.loads(replies.stdout)['results']] == ['sol', 'astra', 'carbon']
    calls = [json.loads(line) for line in (root / 'calls.jsonl').read_text().splitlines()]
    assert {(item['backend'], item['args'][0]) for item in calls} == {
        ('sol', 'gpt-review-old'), ('astra', 'ark-review-old'), ('carbon', 'cursor-review-old')}
    assert run('stop', 'pro-review-old').returncode == 2


def test_recursion_and_duplicate_target_guard(unified):
    run, root = unified
    assert run('start', '--effort', 'high', '--backend', 'claude', extra_env={'CODEX_REVIEW_SUBAGENT_ACTIVE': '1'}).returncode == 126
    assert run('send', 'sol-review-old', 'sol-review-old').returncode == 2
    assert not (root / 'calls.jsonl').exists()


@pytest.mark.parametrize('args', [('start', '--effort', 'high', '--backend', 'claude'),
                                 ('--once', '--effort', 'high', '--backend', 'claude'), ('send', 'claude-review-old')])
def test_slow_pipe_reads_complete_prompt(unified, args):
    run, root = unified
    proc = subprocess.Popen([run.entry, *args], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, env=run.env)
    try:
        time.sleep(.2)
        proc.stdin.write('第一部分\n')
        proc.stdin.flush()
        time.sleep(.2)
        stdout, stderr = proc.communicate('第二部分🙂', timeout=10)
        assert proc.returncode == 0, (stdout, stderr)
        calls = [json.loads(line) for line in (root / 'calls.jsonl').read_text().splitlines()]
        assert calls[0]['prompt'] == '第一部分\n第二部分🙂'
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()


@pytest.mark.parametrize('action', ['--once', 'wait'])
def test_empty_reply_is_failure_in_batch(unified, action):
    run, _ = unified
    args = (['--effort', 'high', '--backend', 'claude', '--backend', 'sol'] if action == '--once' else
            ['claude-review-old', 'sol-review-old'])
    reply = run(action, *args, extra_env={'EMPTY_BACKEND': 'sol'})
    assert reply.returncode == 1
    results = json.loads(reply.stdout)['results']
    assert not results[0]['is_error'] and results[1]['is_error']
    assert 'empty' in results[1]['diagnostics']


def test_once_retains_completed_result_and_times_out_entire_child_tree(unified):
    run, root = unified
    proc = subprocess.Popen([run.entry, '--once', '--effort', 'high', '--backend', 'claude', '--backend', 'sol', '--timeout', '1'],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, env=run.env | {'HANG_BACKEND': 'sol'})
    proc.stdin.write('任务')
    proc.stdin.close()
    proc.stdin = None
    try:
        # This record must arrive while GPT is still running, before the final manifest.
        event = json.loads(proc.stderr.readline())
        assert event['event'] == 'completed' and event['backend'] == 'claude'
        assert event['result'] == '结论🙂' and not event['is_error']
        assert proc.poll() is None
        stdout, stderr = proc.communicate(timeout=6)
        assert proc.returncode == 124, (stdout, stderr)
        replies = json.loads(stdout)['results']
        assert replies[0]['result'] == '结论🙂' and replies[1]['exit_code'] == 124
        descendant = int((root / 'descendant.pid').read_text())
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            try: os.kill(descendant, 0)
            except ProcessLookupError: break
            time.sleep(.02)
        with pytest.raises(ProcessLookupError): os.kill(descendant, 0)
    finally:
        if (root / 'runner.pid').exists():
            try: os.killpg(int((root / 'runner.pid').read_text()), signal.SIGKILL)
            except ProcessLookupError: pass
        if proc.poll() is None:
            proc.kill()
            proc.communicate()
        if (root / 'descendant.pid').exists():
            try: os.kill(int((root / 'descendant.pid').read_text()), signal.SIGKILL)
            except ProcessLookupError: pass


@pytest.mark.parametrize('termination, code', [(signal.SIGINT, 130), (signal.SIGTERM, 143)])
def test_once_interruption_preserves_completed_reply_and_stops_children(unified, termination, code):
    run, root = unified
    proc = subprocess.Popen([run.entry, '--once', '--effort', 'high', '--backend', 'claude', '--backend', 'sol', '--timeout', '10'],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, env=run.env | {'HANG_BACKEND': 'sol'})
    proc.stdin.write('任务')
    proc.stdin.close()
    proc.stdin = None
    try:
        event = json.loads(proc.stderr.readline())
        assert event['backend'] == 'claude' and event['result'] == '结论🙂'
        deadline = time.monotonic() + 2
        while not (root / 'descendant.pid').exists() and time.monotonic() < deadline:
            time.sleep(.02)
        assert (root / 'descendant.pid').exists()
        proc.send_signal(termination)
        stdout, stderr = proc.communicate(timeout=6)
        assert proc.returncode == code, (stdout, stderr)
        results = json.loads(stdout)['results']
        assert results[0]['result'] == '结论🙂' and not results[0]['is_error']
        assert results[1]['exit_code'] == code
        descendant = int((root / 'descendant.pid').read_text())
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            try: os.kill(descendant, 0)
            except ProcessLookupError: break
            time.sleep(.02)
        with pytest.raises(ProcessLookupError): os.kill(descendant, 0)
    finally:
        if (root / 'runner.pid').exists():
            try: os.killpg(int((root / 'runner.pid').read_text()), signal.SIGKILL)
            except ProcessLookupError: pass
        if proc.poll() is None:
            proc.kill()
            proc.communicate()


def test_once_can_be_cancelled_while_waiting_for_stdin(unified):
    run, root = unified
    proc = subprocess.Popen([run.entry, '--once', '--effort', 'high', '--backend', 'claude'], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=run.env)
    try:
        time.sleep(1)
        proc.terminate()
        stdout, stderr = proc.communicate(timeout=4)
        # If scheduling delays startup, SIGTERM can precede the Node handler.
        # Either path must promptly exit without dispatching a backend.
        assert proc.returncode in (143, -signal.SIGTERM), (stdout, stderr)
        assert not (root / 'calls.jsonl').exists()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()


def test_effort_is_required_and_reaches_every_backend(unified):
    run, root = unified
    # The caller picks the tier each time; a missing one dispatches nothing.
    outcome = run('start', '--backend', 'sol')
    assert outcome.returncode == 2 and '--effort' in outcome.stderr
    assert not (root / 'calls.jsonl').exists()
    assert run('--once', '--effort', 'medium', '--backend', 'claude', '--backend', 'carbon').returncode == 0
    calls = [json.loads(line) for line in (root / 'calls.jsonl').read_text().splitlines()]
    assert sorted(item['backend'] for item in calls) == ['carbon', 'claude']
    assert all(item['args'][:2] == ['--effort', 'medium'] for item in calls)


def test_file_paths_are_listed_for_every_backend(unified):
    run, root = unified
    (root / 'a.py').write_text('x')
    outcome = run('start', '--effort', 'high', '--backend', 'claude', '--file', str(root / 'a.py'), prompt='审查\n')
    assert outcome.returncode == 0, outcome.stderr
    claude = json.loads((root / 'calls.jsonl').read_text())
    assert claude['prompt'] == f'审查\n\nRead these files:\n- {root / "a.py"}\n'


@pytest.mark.parametrize('path', ['missing.py', '.'])
def test_unreadable_file_dispatches_nothing(unified, path):
    run, root = unified
    assert run('start', '--effort', 'high', '--backend', 'claude', '--file', path).returncode == 2
    assert not (root / 'calls.jsonl').exists()


def test_persistent_backends_learn_how_to_ask_a_registered_caller(unified):
    run, root = unified
    fake = root / 'bin' / 'agent-msg'
    fake.write_text('#!/bin/sh\n[ "$1" = whoami ] && printf \'{"name":"lead","identity":"claude:x","kind":"claude"}\\n\'\n')
    fake.chmod(0o755)
    outcome = run('start', '--effort', 'high', '--backend', 'carbon')
    assert outcome.returncode == 0, outcome.stderr
    calls = [json.loads(line) for line in (root / 'calls.jsonl').read_text().splitlines()]
    assert calls[0]['prompt'].startswith('审查同一任务 $() `literal`\n\n## Questions for the caller')
    assert '`agent-msg send lead --file FILE`' in calls[0]['prompt']
    # A one-shot has no session to answer into.
    (root / 'calls.jsonl').unlink()
    assert run('--once', '--effort', 'high', '--backend', 'sol').returncode == 0
    assert 'agent-msg' not in (root / 'calls.jsonl').read_text()
    # An unregistered caller gets replies only.
    fake.write_text('#!/bin/sh\nexit 1\n')
    (root / 'calls.jsonl').unlink()
    assert run('start', '--effort', 'high', '--backend', 'sol').returncode == 0
    assert 'agent-msg' not in (root / 'calls.jsonl').read_text()
