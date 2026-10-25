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
elif action == 'send' and backend == 'cursor':
    print('delivery unconfirmed; do not resend automatically', file=sys.stderr)
    sys.exit(124)
if os.environ.get('FAIL_BACKEND') == backend: sys.exit(7)
''')
    runner.chmod(0o755)
    (tmp_path / '.functions').write_text('c() { :; }\nds() { :; }\n')
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    for name in ('tmux', 'jq', 'cursor-agent', 'muse'):
        path = bin_dir / name
        path.write_text('#!/bin/sh\nexit 0\n')
        path.chmod(0o755)
    pro = bin_dir / 'gpt-pro'
    pro.write_text(f'''#!{sys.executable}
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
root = Path(os.environ['HOME'])
stdin = '' if '--run-id' in args or '--stop' in args else sys.stdin.read()
with (root / 'pro.jsonl').open('a') as out:
    out.write(json.dumps({{'args': args, 'stdin': stdin}}) + '\\n')
value = lambda flag: args[args.index(flag) + 1]
run_id = 'ask-20261013T000000Z-0f0e0d0c-1111-2222-3333-444455556666'
if '--stop' in args:
    sys.exit(4 if os.environ.get('PRO_STATE') == 'gone' else 0)
if '--send' in args:
    if os.environ.get('PRO_STATE') == 'finished':
        print('{{"event":"send_rejected","reason":"run_finished"}}', file=sys.stderr)
        sys.exit(2)
    if os.environ.get('PRO_STATE') == 'queued':
        print('{{"status":"error","reason":"run_not_ready"}}', file=sys.stderr)
        sys.exit(2)
    sys.exit(0)
if '--run-id' in args:
    if os.environ.get('PRO_STATE') == 'running': sys.exit(124)
    print('PRO:' + value('--run-id'))
    sys.exit(0)
print('gpt-pro: run_id=' + run_id + ' transport=ssh mode=submit', file=sys.stderr)
if value('--max-wait') == '1': sys.exit(int(os.environ.get('PRO_SUBMIT_RC', '124')))
print('PRO ONCE')
''')
    pro.chmod(0o755)
    codex = tmp_path / '.local/bin/codex'
    codex.parent.mkdir(parents=True)
    codex.write_text('#!/bin/sh\nprintf "codex-cli 0.160.1\\n"\n')
    codex.chmod(0o755)
    env = {key: os.environ[key] for key in ('PATH', 'LANG') if key in os.environ}
    env.update(HOME=str(tmp_path), PATH=str(bin_dir) + os.pathsep + env['PATH'],
               CURSOR_AGENT_BIN=str(bin_dir / 'cursor-agent'), DEEPSEEK_API_KEY='test-key')
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
    outcome = run('start', '--backend', 'claude', '--backend', 'gpt', '--backend', 'muse',
                  extra_env={'EXPECTED_STARTS': '3'})
    assert outcome.returncode == 0, outcome.stderr
    manifest = json.loads(outcome.stdout)
    assert manifest['errors'] == []
    assert [item['backend'] for item in manifest['sessions']] == ['claude', 'gpt', 'muse']
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
    outcome = run('start', '--backend', 'claude', '--backend', 'gpt')
    assert outcome.returncode == 1
    manifest = json.loads(outcome.stdout)
    assert len(manifest['sessions']) == 1 and manifest['sessions'][0]['backend'] == 'claude'
    assert manifest['errors'][0]['backend'] == 'gpt'
    calls = [json.loads(line) for line in (root / 'calls.jsonl').read_text().splitlines()]
    assert [item['backend'] for item in calls] == ['claude']


def test_handle_survives_nonzero_exit_after_session_was_created(unified):
    run, _ = unified
    outcome = run('start', '--backend', 'claude', '--backend', 'gpt', extra_env={'FAIL_BACKEND': 'gpt'})
    assert outcome.returncode == 1
    manifest = json.loads(outcome.stdout)
    assert [item['backend'] for item in manifest['sessions']] == ['claude', 'gpt']
    assert manifest['errors'][0]['backend'] == 'gpt'
    assert manifest['errors'][0]['exit_code'] == 7


def test_all_backends_use_one_skill(unified):
    run, _ = unified
    backends = run('backends')
    assert all(item['available'] for item in json.loads(backends.stdout)['backends'])
    outcome = run('--once', '--backend', 'claude', '--backend', 'gpt', '--backend', 'cursor', '--backend', 'muse',
                  '--backend', 'ds', '--backend', 'pro')
    assert outcome.returncode == 0, outcome.stderr
    replies = json.loads(outcome.stdout)['results']
    assert [item['backend'] for item in replies] == ['claude', 'gpt', 'cursor', 'muse', 'ds', 'pro']
    assert all(item['result'] == '结论🙂' for item in replies[:5]) and replies[5]['result'] == 'PRO ONCE'


def test_batch_retains_each_failure_and_cursor_delivery_uncertainty(unified):
    run, _ = unified
    outcome = run('--once', '--backend', 'claude', '--backend', 'gpt', extra_env={'FAIL_BACKEND': 'gpt'})
    assert outcome.returncode == 1
    replies = json.loads(outcome.stdout)['results']
    assert replies[0]['exit_code'] == 0 and replies[1]['exit_code'] == 7
    sent = run('send', 'cursor-review-old', 'claude-review-old')
    assert sent.returncode == 124
    replies = json.loads(sent.stdout)['results']
    assert replies[0]['delivery'] == 'unconfirmed' and replies[1]['delivery'] == 'submitted'


def test_per_instance_prompt_files_start_distinct_assignments_in_one_call(unified):
    run, root = unified
    (root / 'correctness.md').write_text('看正确性')
    (root / 'tests.md').write_text('看测试')
    outcome = run('start', '--backend', f'claude={root / "correctness.md"}', '--backend', 'gpt',
                  '--backend', f'cursor={root / "tests.md"}', prompt='共享任务', extra_env={'EXPECTED_STARTS': '3'})
    assert outcome.returncode == 0, outcome.stderr
    calls = {call['backend']: call['prompt'] for call in
             map(json.loads, (root / 'calls.jsonl').read_text().splitlines())}
    assert calls == {'claude': '看正确性', 'gpt': '共享任务', 'cursor': '看测试'}


def test_prompt_files_make_stdin_optional(unified):
    run, root = unified
    (root / 'a.md').write_text('任务甲')
    outcome = subprocess.run([run.entry, '--once', '--backend', f'gpt={root / "a.md"}'], stdin=subprocess.DEVNULL,
                             capture_output=True, text=True, env=run.env, timeout=12)
    assert outcome.returncode == 0, outcome.stderr
    assert json.loads((root / 'calls.jsonl').read_text())['prompt'] == '任务甲'


@pytest.mark.parametrize('spec', ['gpt=missing.md', 'gpt='])
def test_unreadable_prompt_file_dispatches_nothing(unified, spec):
    run, root = unified
    assert run('start', '--backend', spec).returncode == 2
    assert not (root / 'calls.jsonl').exists()


@pytest.mark.parametrize('action', ['start', '--once'])
@pytest.mark.parametrize('backends', [('claude', 'claude'), ('gpt', 'muse', 'gpt=prompt.md')])
def test_each_backend_runs_at_most_once_per_call(unified, action, backends):
    run, root = unified
    (root / 'prompt.md').write_text('x')
    outcome = subprocess.run([run.entry, action, *(arg for backend in backends for arg in ('--backend', backend))],
                             input='x', capture_output=True, text=True, env=run.env, cwd=root, timeout=12)
    assert outcome.returncode == 2 and 'at most once' in outcome.stderr
    assert not (root / 'calls.jsonl').exists()


@pytest.mark.parametrize('options', [[], ['--backend', 'unknown'], ['--backend', 'gpt', '--effort', 'high'],
                                   ['--backend', 'gpt', '--model', 'gpt-6.1-sol'],
                                   ['--backend', 'cursor', '--mode', 'ask'], ['--backend', 'gemini'], ['--network', '--backend', 'gpt']])
def test_invalid_selection_dispatches_nothing(unified, options):
    run, root = unified
    assert run('start', *options).returncode == 2
    assert not (root / 'calls.jsonl').exists()


def test_former_gemini_backend_names_its_replacement(unified):
    run, _ = unified
    outcome = run('start', '--backend', 'gemini')
    assert outcome.returncode == 2 and 'renamed to cursor' in outcome.stderr


def test_recursion_and_duplicate_target_guard(unified):
    run, root = unified
    assert run('start', '--backend', 'claude', extra_env={'CODEX_REVIEW_SUBAGENT_ACTIVE': '1'}).returncode == 126
    assert run('send', 'gpt-review-old', 'gpt-review-old').returncode == 2
    assert not (root / 'calls.jsonl').exists()


@pytest.mark.parametrize('args', [('start', '--backend', 'claude'),
                                 ('--once', '--backend', 'claude'), ('send', 'claude-review-old')])
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
    args = (['--backend', 'claude', '--backend', 'gpt'] if action == '--once' else
            ['claude-review-old', 'gpt-review-old'])
    reply = run(action, *args, extra_env={'EMPTY_BACKEND': 'gpt'})
    assert reply.returncode == 1
    results = json.loads(reply.stdout)['results']
    assert not results[0]['is_error'] and results[1]['is_error']
    assert 'empty' in results[1]['diagnostics']


def test_once_retains_completed_result_and_times_out_entire_child_tree(unified):
    run, root = unified
    proc = subprocess.Popen([run.entry, '--once', '--backend', 'claude', '--backend', 'gpt', '--timeout', '1'],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, env=run.env | {'HANG_BACKEND': 'gpt'})
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
    proc = subprocess.Popen([run.entry, '--once', '--backend', 'claude', '--backend', 'gpt', '--timeout', '10'],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, env=run.env | {'HANG_BACKEND': 'gpt'})
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
    proc = subprocess.Popen([run.entry, '--once', '--backend', 'claude'], stdin=subprocess.PIPE,
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


def pro_calls(root):
    return [json.loads(line) for line in (root / 'pro.jsonl').read_text().splitlines()]


def test_pro_runs_without_tmux_and_gets_attached_files(unified):
    run, root = unified
    (root / 'bin/tmux').unlink()
    (root / 'notes.md').write_text('x')
    outcome = subprocess.run([run.entry, '--backend', 'pro', '--file', 'notes.md'], input='审查',
                             capture_output=True, text=True, env=run.env, cwd=root, timeout=12)
    assert outcome.returncode == 0, outcome.stderr
    session = outcome.stdout.strip()
    assert session == 'pro-review-ask-20261013T000000Z-0f0e0d0c-1111-2222-3333-444455556666'
    assert pro_calls(root) == [{'args': ['--max-wait', '1', '-f', str(root / 'notes.md')], 'stdin': '审查'}]
    assert run('list').stdout.split() == [session]
    assert run('stop', session).returncode == 0
    assert run('list').stdout.split() == []


def test_file_is_listed_for_tmux_backends_and_inlined_by_pro(unified):
    run, root = unified
    (root / 'a.py').write_text('x')
    outcome = run('start', '--backend', 'claude', '--backend', 'pro', '--file', str(root / 'a.py'), prompt='审查\n')
    assert outcome.returncode == 0, outcome.stderr
    claude = json.loads((root / 'calls.jsonl').read_text())
    assert claude['prompt'] == f'审查\n\nRead these files:\n- {root / "a.py"}\n'
    assert pro_calls(root)[0]['stdin'] == '审查\n'


@pytest.mark.parametrize('path', ['missing.py', '.'])
def test_unreadable_file_dispatches_nothing(unified, path):
    run, root = unified
    assert run('start', '--backend', 'pro', '--file', path).returncode == 2
    assert not (root / 'pro.jsonl').exists()


def test_pro_waits_two_hours_by_default(unified):
    run, root = unified
    session = 'pro-review-ask-1'
    assert run('wait', session).stdout == 'PRO:ask-1\n'
    assert run('wait', session, '--timeout', '8').returncode == 0
    assert run('--once', '--backend', 'pro').stdout == 'PRO ONCE\n'
    assert [call['args'][-2:] for call in pro_calls(root)] == [['--max-wait', '7200'], ['--max-wait', '8'], ['--max-wait', '7200']]
    running = run('status', session, extra_env={'PRO_STATE': 'running'})
    assert running.stdout == f'{session} state=running\n'


def test_pro_send_is_idempotent_and_rejects_finished_runs(unified):
    run, root = unified
    first = run('send', 'pro-review-ask-1', prompt='补充')
    assert json.loads(first.stdout)['delivery'] == 'confirmed'
    run('send', 'pro-review-ask-1', prompt='补充')
    ids = {call['args'][call['args'].index('--message-id') + 1] for call in pro_calls(root)}
    assert len(ids) == 1
    finished = run('send', 'pro-review-ask-1', prompt='再问', extra_env={'PRO_STATE': 'finished'})
    assert finished.returncode == 1 and json.loads(finished.stdout)['delivery'] == 'failed'
    assert 'start a new task' in finished.stderr
    queued = run('send', 'pro-review-ask-1', prompt='再问', extra_env={'PRO_STATE': 'queued'})
    assert queued.returncode == 1 and 'resend the same supplement' in queued.stderr


def test_pro_submission_failure_returns_no_handle(unified):
    run, root = unified
    outcome = run('start', '--backend', 'pro', extra_env={'PRO_SUBMIT_RC': '1'})
    assert outcome.returncode == 1 and json.loads(outcome.stdout)['sessions'] == []
    assert run('list').stdout == ''
    missing = run('backends', extra_env={'GPT_PRO_BIN': str(root / 'none')})
    assert {item['backend']: item['available'] for item in json.loads(missing.stdout)['backends']}['pro'] is False


def test_ds_requires_its_api_key(unified):
    run, root = unified
    backends = run('backends', extra_env={'DEEPSEEK_API_KEY': ''})
    ds = next(item for item in json.loads(backends.stdout)['backends'] if item['backend'] == 'ds')
    assert not ds['available'] and 'DEEPSEEK_API_KEY' in ds['reason']
    assert run('--once', '--backend', 'ds', extra_env={'DEEPSEEK_API_KEY': ''}).returncode == 1
    assert not (root / 'calls.jsonl').exists()
