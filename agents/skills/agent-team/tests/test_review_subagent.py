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

CURSOR_NATIVE_MOCK = r'''
import codecs, json, os, select, sys, time, tty
from pathlib import Path
root = Path(os.environ['HOME'])
state = Path(os.environ['REVIEW_SUBAGENT_TURN_DIR'])
transcript = state / 'mock-transcript.jsonl'
(state / 'transcript-paths.json').write_text(json.dumps([str(transcript)]))
records = []
current = sys.argv[-1].split('\n\nComplete the entire')[0]
pasted = False
pending = ''
input_text = ''
busy = False
blocked = []
steering = False
queued = None
settle = 0
steer_until = 0

def record(role, text): return {'role': role, 'message': {'content': [{'type': 'text', 'text': text}]}}
crashes = int(os.environ.get('MOCK_CURSOR_CRASHES', '0'))
def flush(status=None):
    global crashes
    end = {'type': 'turn_ended', 'status': status}
    if status == 'success' and (os.environ.get('MOCK_CURSOR_CRASH') or crashes > 0):
        crashes -= 1
        end = {'type': 'turn_ended', 'status': 'error', 'error': 'WritableIterable is closed'}
    transcript.write_text(''.join(json.dumps(item) + '\n' for item in records + ([end] if status else [])))
def frame():
    history = '\n'.join(item['message']['content'][0]['text'] for item in records if item['role'] == 'assistant')
    more = max(0, len(queued.splitlines()) - 2) if queued is not None else 0
    prefix = f'+{more} more lines · ' if more else ''
    footer = '\n│ ' + prefix + 'enter steer · select/edit │' if queued is not None else ''
    if steering: footer = '\n│ enter interrupt and send · select/edit │'
    if os.environ.get('MOCK_CURSOR_HIDE_FOOTER'): footer = ''
    draft = f'[Pasted text #1 +{len(input_text.splitlines())} lines]' if input_text and not pasted else 'Add a follow-up'
    print('\x1b[2J\x1b[HMOCK_READY\n' + history + footer + '\n  → ' + draft + '\n ▀▀▀▀', flush=True)
def accept(text):
    global current, busy, steering
    current = text
    steering = False
    records.append(record('user', text))
    flush()
    if text == 'EXIT_NOW': sys.exit(7)
    if text in ('BUSY_INITIAL', 'BUSY_FOLLOWUP'):
        (root / (text + '.started')).touch()
        blocked.append(root / (text + '.release'))
    busy = text == 'SILENT' or any(not path.exists() for path in blocked)
    if not busy: finish()
    else: frame()
def finish():
    global busy
    records.append(record('assistant', 'ANSWER:' + current))
    flush('success')
    busy = False
    frame()

tty.setraw(sys.stdin.fileno())
print('\x1b[?2004h', flush=True)
if 'MOCK_CURSOR_EVENTS' in os.environ:
    records.append(record('user', current))
    records.append(record('assistant', 'opening only'))
    flush()
    sys.exit(1)
accept(current)
decoder = codecs.getincrementaldecoder('utf8')()
while True:
    if busy and current != 'SILENT' and all(path.exists() for path in blocked): finish()
    if steering and time.monotonic() >= steer_until: steering = False; frame()
    if not select.select([sys.stdin], [], [], .05)[0]: continue
    chunk = os.read(sys.stdin.fileno(), 65536)
    if not chunk: break
    pending += decoder.decode(chunk)
    while pending:
        token = '\x1b[201~' if pasted else '\x1b[200~'
        if token.startswith(pending) and len(pending) < len(token): break
        if pending.startswith(token):
            pasted = not pasted; pending = pending[len(token):]
            # Like Cursor, render the paste at once but ignore Enter shortly after it.
            if not pasted:
                settle = time.monotonic() + float(os.environ.get('MOCK_CURSOR_PASTE_DELAY', '0'))
                frame()
            continue
        char = pending[0]; pending = pending[1:]
        if char == '\x03':
            busy = False
            flush('aborted')
            blocked.clear()
            frame()
        elif pasted: input_text += char
        elif char in '\r\n':
            if time.monotonic() < settle: continue
            if input_text:
                text = input_text; input_text = ''
                if busy:
                    queued = text
                    time.sleep(float(os.environ.get('MOCK_CURSOR_FOOTER_DELAY', '0')))
                    frame()
                else: accept(text)
            elif queued is not None:
                if os.environ.get('MOCK_CURSOR_IGNORE_STEER'): continue
                text = queued; queued = None
                accept(text)
                steering = busy
                steer_until = time.monotonic() + float(os.environ.get('MOCK_CURSOR_STEER_SECONDS', 'inf'))
                with open(root / 'steering.started', 'a') as log: log.write(text + '\n')
                frame()
        else: input_text += char
'''

MUSE_NATIVE_MOCK = r'''
import codecs, json, os, select, subprocess, sys, tty
from pathlib import Path
root = Path(os.environ['HOME'])
args = sys.argv[1:]
Path(os.environ['CAPTURE']).write_text(json.dumps({'args': args, 'sentinel': os.environ.get('CODEX_REVIEW_SUBAGENT_ACTIVE'),
                                                   'tmp_files': sorted(os.listdir(os.environ.get('TMPDIR', '/tmp')))}))
if args and args[0] == 'exec':
    print(os.environ.get('MOCK_RESULT', 'review result'))
    sys.exit(int(os.environ.get('MOCK_EXIT', '0')))
hooks = json.loads(next(value for value in args if value.startswith('hooks='))[len('hooks='):])
def fire(event, **payload):
    # Muse scrubs the hook environment down to basics such as PATH and HOME.
    for entry in hooks.get(event, []):
        for hook in entry['hooks']:
            subprocess.run(hook['command'], shell=True, input=json.dumps({'hook_event_name': event, **payload}), text=True,
                           env={key: os.environ[key] for key in ('PATH', 'HOME')})
running, queue, draft, armed = None, [], '', False
net_failures = int(os.environ.get('MOCK_MUSE_NET_FAILURES', '0'))
def frame():
    body = '◈ Thinking (1s · esc to interrupt)\r\n' if running is not None else ''
    if queue: body += '◆ Queued input · ↑ to edit\r\n' + ''.join('├ ' + item + '\r\n' for item in queue)
    lines = draft.split('\n')
    box = '❯ ' + lines[0] + ''.join('\n  ' + line for line in lines[1:])
    sys.stdout.write('\x1b[2J\x1b[H' + body + '── Voice input ──\r\n' + box.replace('\n', '\r\n') + '\r\n────\r\n')
    sys.stdout.flush()
def start(text):
    global running, net_failures
    running = text
    if text == 'FAIL':
        running = None
        fire('StopFailure', error_details={'message': 'overloaded'}, last_assistant_message='partial')
        frame()
    elif net_failures > 0:
        net_failures -= 1
        running = None
        fire('StopFailure', error_details={'message': 'model failed after 2 attempts: transport error [net-timeout]'},
             last_assistant_message='partial')
        frame()
    elif not text.startswith('SLOW'): finish()
    else: frame()
def finish():
    global running
    text, running = running, None
    fire('Stop', last_assistant_message='ANSWER:' + text)
    if queue: start(queue.pop(0))
    else: frame()
def cancel():
    # Escape cancels the turn without a Stop and restores it and every queued input as the draft.
    global running, draft
    if running is not None:
        draft = '\n'.join([running] + queue) + draft
        running = None
        queue.clear()
    frame()
tty.setraw(sys.stdin.fileno())
print('\x1b[?2004h', end='', flush=True)
start(args[-1])
decoder = codecs.getincrementaldecoder('utf8')()
pending, pasted = '', False
while True:
    if running and running.startswith('SLOW') and (root / (running + '.release')).exists(): finish()
    if not select.select([sys.stdin], [], [], .05)[0]:
        if pending == '\x1b': cancel(); pending = ''  # A lone ESC byte, not the start of a paste marker.
        continue
    chunk = os.read(sys.stdin.fileno(), 65536)
    if not chunk: break
    pending += decoder.decode(chunk)
    while pending:
        token = '\x1b[201~' if pasted else '\x1b[200~'
        if pending.startswith(token): pasted = not pasted; pending = pending[len(token):]; frame(); continue
        if token.startswith(pending): break
        char, pending = pending[0], pending[1:]
        if pasted: draft += char.replace('\r', '\n'); continue
        if char == '\x03':
            if draft: draft, armed = '', False
            elif armed: sys.exit(0)
            else: armed = True
            frame()
        elif char in '\r\n':
            if draft:
                text, draft = draft, ''
                if running is not None: queue.append(text); frame()
                else: start(text)
        else: draft += char
'''


@pytest.fixture(params=['claude', 'gpt', 'cursor', 'ds'])
def harness(request, tmp_path):
    name = request.param
    env = {key: os.environ[key] for key in ('PATH', 'LANG') if key in os.environ}
    env.update(HOME=str(tmp_path), TMPDIR=str(tmp_path), CAPTURE=str(tmp_path / 'call.json'))
    env.pop('CODEX_REVIEW_SUBAGENT_ACTIVE', None)
    env.pop('TMUX', None)
    native = tmp_path / 'native.py'
    native.write_text(CURSOR_NATIVE_MOCK)
    backend = tmp_path / 'backend'
    backend.write_text(f'''#!{sys.executable}
import json, os, subprocess, sys
from pathlib import Path
if '--version' in sys.argv:
    print('codex-cli ' + os.environ.get('MOCK_CODEX_VERSION', '0.159.2'))
    sys.exit(0)
config_path = Path(os.environ.get('CURSOR_CONFIG_DIR', '/nonexistent'), 'cli-config.json')
config = json.loads(config_path.read_text()) if config_path.exists() else None
prompt_file = sys.argv[sys.argv.index('--prompt-file') + 1] if '--prompt-file' in sys.argv else None
Path(os.environ['CAPTURE']).write_text(json.dumps({{'args': sys.argv[1:], 'sentinel': os.environ.get('CODEX_REVIEW_SUBAGENT_ACTIVE'), 'config': config, 'launcher': os.environ.get('LAUNCHER'),
                                                   'prompt_file': prompt_file, 'prompt': Path(prompt_file).read_text() if prompt_file else None}}))
if 'create-chat' in sys.argv:
    print('cursor-main')
    sys.exit(0)
if '-p' in sys.argv or '--print' in sys.argv or 'exec' in sys.argv:
    sys.stdin.read()
    text = os.environ.get('MOCK_RESULT', 'review result')
    if '--print' in sys.argv:
        import time
        if 'MOCK_CURSOR_EVENTS' in os.environ:
            print(os.environ['MOCK_CURSOR_EVENTS'])
            sys.exit(0)
        prompt = sys.argv[-1].split('\\n\\nComplete the entire')[0]
        if prompt in ('BUSY_INITIAL', 'BUSY_FOLLOWUP'):
            root = Path(os.environ['HOME'])
            (root / (prompt + '.started')).touch()
            while not (root / (prompt + '.release')).exists(): time.sleep(.05)
        if prompt == 'SILENT': time.sleep(60)
        if prompt == 'EXIT_NOW': sys.exit(7)
        if os.environ.get('REVIEW_SUBAGENT_TURN_DIR'):
            text = 'ANSWER:' + prompt
        chat = sys.argv[sys.argv.index('--resume') + 1] if '--resume' in sys.argv else 'cursor-main'
        print(json.dumps({{'type': 'result', 'is_error': False, 'result': text, 'session_id': chat}}))
    else:
        print(text)
    sys.exit(int(os.environ.get('MOCK_EXIT', '0')))
if '--resume' in sys.argv:
    os.execv(sys.executable, [sys.executable, {str(native)!r}, *sys.argv[1:]])
trust = Path(os.environ['HOME'], 'trust-prompt')
if trust.exists():
    # Claude Code's workspace trust dialog blocks before the first turn starts; Down selects Yes.
    import termios, time, tty
    saved = termios.tcgetattr(0)
    tty.setcbreak(0)
    choice = 0
    while True:
        marks = ['❯' if choice == i else ' ' for i in (0, 1)]
        print('\\x1b[2J\\x1b[HQuick safety check: Is this a project you created or one you trust?\\n'
              + marks[0] + ' No, exit\\n' + marks[1] + ' Yes, I trust this folder', flush=True)
        if trust.read_text() == 'stuck': time.sleep(60)
        key = os.read(0, 8)
        if key == b'\\x1b[B': choice = 1
        elif key in (b'\\r', b'\\n'):
            if not choice: sys.exit(1)
            break
    termios.tcsetattr(0, termios.TCSADRAIN, saved)
inputs = [sys.argv[-1]]
sessions = Path(os.environ['HOME'], '.codex', 'sessions', '2026', '10', '07')
def rollout(thread, *records):
    sessions.mkdir(parents=True, exist_ok=True)
    with open(sessions / f'rollout-2026-10-07T10-57-47-{{thread}}.jsonl', 'a') as f:
        for record in records: f.write(json.dumps(record) + '\\n')
def final(text): return {{'type': 'response_item', 'payload': {{'type': 'message', 'role': 'assistant', 'phase': 'final_answer', 'content': [{{'type': 'output_text', 'text': text}}]}}}}
started = {{'type': 'event_msg', 'payload': {{'type': 'task_started'}}}}
def turn_done(text, thread='main'):
    # Fire the turn-complete hook the way each harness does.
    args = sys.argv[1:]
    if '--settings' in args:
        command = json.loads(args[args.index('--settings') + 1])['hooks']['Stop'][0]['hooks'][0]['command']
        subprocess.run(command, shell=True, input=json.dumps({{'last_assistant_message': text}}), text=True)
    for value in args:
        if value.startswith('hooks='):  # Muse takes Claude-style hooks through `-c`.
            command = json.loads(value[len('hooks='):])['Stop'][0]['hooks'][0]['command']
            # Muse scrubs the hook environment down to basics such as PATH and HOME.
            subprocess.run(command, shell=True, input=json.dumps({{'hook_event_name': 'Stop', 'last_assistant_message': text}}), text=True,
                           env={{key: os.environ[key] for key in ('PATH', 'HOME')}})
    for value in args:
        if value.startswith('notify='):
            event = {{'type': 'agent-turn-complete', 'thread-id': thread, 'last-assistant-message': text,
                     'input-messages': inputs if thread != 'title' else ['Generate a title. User prompt:\\n' + inputs[0]]}}
            subprocess.run(json.loads(value[len('notify='):]) + [json.dumps(event)])
print('\\x1b[?2004hMOCK_READY', flush=True)
if '--settings' in sys.argv or any(value.startswith('hooks=') for value in sys.argv):
    turn_done('ANSWER:' + inputs[0].split('\\n\\nComplete the entire')[0])
elif any(value.startswith('notify=') for value in sys.argv):
    turn_done('TITLE', thread='title')  # Codex side threads must not count as review turns.
    # A forked subagent inherits the start prompt as its first input; its rollout names the parent.
    rollout('fork', {{'type': 'session_meta', 'payload': {{'id': 'fork', 'parent_thread_id': 'main'}}}})
    turn_done('FORK', thread='fork')
    # Input sent mid-turn is steered into it; notify reports only the turn's last answer.
    rollout('main', {{'type': 'session_meta', 'payload': {{'id': 'main'}}}}, started, final('DRAFT:' + inputs[0]),
            {{'type': 'response_item', 'payload': {{'type': 'message', 'role': 'user', 'content': []}}}},
            final('ANSWER:' + inputs[0]))
    turn_done('ANSWER:' + inputs[0])
for line in sys.stdin:
    print('RECEIVED:' + line.strip(), flush=True)
    inputs.append(line.strip())
    if 'EXIT_NOW' in line: sys.exit(7)
    rollout('main', started)  # Leave the answer unflushed: notify's message must still be reported.
    if 'SILENT' not in line: turn_done('ANSWER:' + line.strip().replace('\\x1b[200~', '').replace('\\x1b[201~', ''))
''')
    backend.chmod(0o755)
    # Each launcher tags its calls so tests can tell which one ran.
    (tmp_path / '.functions').write_text(f'c() {{ LAUNCHER=c "{backend}" "$@"; }}\nds() {{ LAUNCHER=ds "{backend}" "$@"; }}\n')
    (tmp_path / 'codex').symlink_to(backend)
    muse = tmp_path / 'muse'
    muse.write_text(f'#!{sys.executable}\n' + MUSE_NATIVE_MOCK)
    muse.chmod(0o755)
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
    env['CURSOR_AGENT_BIN'] = str(backend)
    # Run through a symlink, just like the installed skill path.
    installed = tmp_path / 'installed'
    installed.symlink_to(SKILLS / 'agent-team', target_is_directory=True)
    def run(*args, prompt='assignment', extra_env=None, unified=False, cwd=None):
        # unified drives the public helper; otherwise call the runner for this backend directly.
        command = ([installed / 'scripts' / 'agent-team', *args] if unified else
                   [installed / 'scripts' / 'review-subagent', name, *args])
        return subprocess.run(list(map(str, command)), input=prompt, text=True, cwd=cwd,
                              capture_output=True, env=env | (extra_env or {}), timeout=15)
    run.env = env
    yield name, run, tmp_path
    if tmux:
        subprocess.run([tmux, '-L', socket, 'kill-server'], capture_output=True)


def test_unified_parallel_backends(harness):
    name, run, _ = harness
    backends = ('claude', 'gpt', 'cursor')
    if name != 'gpt' or not shutil.which('tmux'):
        pytest.skip('Unified real session manager')
    result = run('start', *(arg for backend in backends for arg in ('--backend', backend)), unified=True)
    assert result.returncode == 0, result.stderr
    manifest = json.loads(result.stdout)
    sessions = [item['session'] for item in manifest['sessions']]
    assert [item['backend'] for item in manifest['sessions']] == list(backends)
    assert len(set(sessions)) == 3
    try:
        answers = run('wait', *sessions, unified=True)
        assert answers.returncode == 0, answers.stderr
        assert len(json.loads(answers.stdout)['results']) == 3
        states = run('status', *sessions, unified=True)
        assert all('input_ready=1' in item['result'] for item in json.loads(states.stdout)['results'])
        # Wait has already confirmed all three initial turns.
        sent = run('send', *sessions, prompt='SUPPLEMENT', unified=True)
        assert sent.returncode == 0, sent.stderr
        answers = run('wait', *sessions, unified=True)
        assert answers.returncode == 0, answers.stderr
        assert all('ANSWER:SUPPLEMENT' in item['result'] for item in json.loads(answers.stdout)['results'])
        # Different supplements must stay in each backend's own session.
        for index, session in enumerate(sessions):
            assert run('send', session, prompt=f'ONLY_{index}', unified=True).returncode == 0
        answers = run('wait', *sessions, unified=True)
        assert answers.returncode == 0, answers.stderr
        assert [item['result'] for item in json.loads(answers.stdout)['results']] == ['ANSWER:ONLY_0', 'ANSWER:ONLY_1', 'ANSWER:ONLY_2']
    finally:
        assert run('stop', *sessions, unified=True).returncode == 0


def test_unified_once_uses_real_cursor_adapter(harness):
    name, run, tmp = harness
    if name != 'cursor':
        pytest.skip('Cursor one-shot adapter integration')
    outcome = run('--once', '--backend', 'cursor', '--output-format', 'json', unified=True)
    assert outcome.returncode == 0, outcome.stderr
    assert json.loads(outcome.stdout) == {'result': 'review result', 'exit_code': 0, 'is_error': False}
    call = json.loads((tmp / 'call.json').read_text())
    assert call['sentinel'] == '1'
    assert call['args'][call['args'].index('--model') + 1] == 'gemini-4-argon-high'


def muse_session(run, prompt='assignment', extra_env=None):
    result = run('start', '--backend', 'muse', prompt=prompt, extra_env=extra_env, unified=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def muse_only(name):
    if name != 'gpt' or not shutil.which('tmux'):
        pytest.skip('Muse runs once per fixture through the unified helper')


def test_unified_muse_session_uses_stop_hook_and_fixed_model(harness):
    name, run, tmp = harness
    muse_only(name)
    session = muse_session(run)
    assert session.startswith('muse-review-')
    try:
        assert run('wait', session, unified=True).stdout.strip() == 'ANSWER:assignment'
        call = json.loads((tmp / 'call.json').read_text())
        args = call['args']
        assert call['sentinel'] == '1'
        assert args[args.index('--model') + 1] == 'muse-wonder-full-1.0'
        assert args[args.index('--reasoning-effort') + 1] == 'high'
        # Like the user's `m --yolo`: no approval can hang the turn, and network is available.
        assert '--yolo' in args and '--permission-profile' not in args
        assert args[-2:] == ['--', 'assignment']
        wait_for(lambda *a: run(*a, unified=True), session, 'status', 'input_ready=1')
        sent = run('send', session, prompt='SUPPLEMENT', unified=True)
        assert json.loads(sent.stdout)['delivery'] == 'submitted', sent.stderr
        assert run('wait', session, unified=True).stdout.strip() == 'ANSWER:SUPPLEMENT'
    finally:
        assert run('stop', session, unified=True).returncode == 0


def test_unified_muse_wait_skips_turns_that_finish_before_queued_input(harness):
    name, run, tmp = harness
    muse_only(name)
    session = muse_session(run, prompt='SLOW_A')
    try:
        wait_for(lambda *a: run(*a, unified=True), session, 'capture', 'esc to interrupt')
        assert run('send', session, prompt='SLOW_B', unified=True).returncode == 0
        wait_for(lambda *a: run(*a, unified=True), session, 'capture', 'Queued input')
        (tmp / 'SLOW_A.release').touch()
        # The queued input runs as its own turn; the reply to SLOW_A must not answer it.
        early = run('wait', session, '--timeout', '3', unified=True)
        assert early.returncode == 124, (early.stdout, early.stderr)
        (tmp / 'SLOW_B.release').touch()
        assert run('wait', session, unified=True).stdout.strip() == 'ANSWER:SLOW_B'
    finally:
        assert run('stop', session, unified=True).returncode == 0


def test_unified_muse_interrupt_clears_the_restored_draft(harness):
    name, run, _ = harness
    muse_only(name)
    session = muse_session(run, prompt='SLOW_A')
    try:
        wait_for(lambda *a: run(*a, unified=True), session, 'capture', 'esc to interrupt')
        assert run('send', session, prompt='BBB', unified=True).returncode == 0
        wait_for(lambda *a: run(*a, unified=True), session, 'capture', 'Queued input')
        assert run('interrupt', session, unified=True).returncode == 0
        assert run('send', session, prompt='CCC', unified=True).returncode == 0
        # Without clearing, Muse would submit `SLOW_A\nBBBCCC` and rerun the cancelled task.
        assert run('wait', session, unified=True).stdout.strip() == 'ANSWER:CCC'
        assert 'dead=0' in run('status', session, unified=True).stdout
    finally:
        assert run('stop', session, unified=True).returncode == 0


def test_unified_muse_stop_failure_fails_wait(harness):
    name, run, _ = harness
    muse_only(name)
    session = muse_session(run, prompt='FAIL')
    try:
        reply = run('wait', session, '--timeout', '10', unified=True)
        assert reply.returncode == 1 and 'turn failed' in reply.stderr and 'overloaded' in reply.stderr
        # A later successful turn clears the failure.
        assert run('send', session, prompt='AFTER', unified=True).returncode == 0
        assert run('wait', session, unified=True).stdout.strip() == 'ANSWER:AFTER'
    finally:
        assert run('stop', session, unified=True).returncode == 0


@pytest.mark.parametrize('failures,returncode', [(2, 0), (3, 1)])
def test_unified_muse_transient_failure_auto_continues(harness, failures, returncode):
    name, run, _ = harness
    muse_only(name)
    session = muse_session(run, extra_env={'MOCK_MUSE_NET_FAILURES': str(failures)})
    try:
        reply = run('wait', session, '--timeout', '20', unified=True)
        assert reply.returncode == returncode, reply.stderr
        assert 'auto-continued 1/2' in reply.stderr and 'auto-continued 2/2' in reply.stderr
        if returncode == 0:
            assert reply.stdout.strip().startswith('ANSWER:The previous turn ended early')
        else:
            assert 'net-timeout' in reply.stderr.splitlines()[-1]
        # A caller's send starts a new request with a fresh continuation budget.
        assert run('send', session, prompt='AFTER', unified=True).returncode == 0
        assert run('wait', session, unified=True).stdout.strip() == 'ANSWER:AFTER'
    finally:
        assert run('stop', session, unified=True).returncode == 0


def test_unified_muse_hook_survives_quotes_in_temp_paths(harness):
    name, run, tmp = harness
    muse_only(name)
    odd = tmp / 'it\'s "odd" \\dir'
    odd.mkdir()
    session = muse_session(run, extra_env={'TMPDIR': str(odd)})
    try:
        assert run('wait', session, '--timeout', '10', unified=True).stdout.strip() == 'ANSWER:assignment'
    finally:
        assert run('stop', session, unified=True).returncode == 0


def test_unified_muse_once_passes_prompt_as_an_argument(harness):
    name, run, tmp = harness
    if name != 'gpt':
        pytest.skip('Muse one-shot integration')
    (tmp / 'work' / 'muse').mkdir(parents=True)  # A same-named directory must not shadow the CLI.
    outcome = run('--once', '--backend', 'muse', '--output-format', 'json', prompt='-leading dash',
                  unified=True, cwd=tmp / 'work')
    assert outcome.returncode == 0, outcome.stderr
    assert json.loads(outcome.stdout)['result'] == 'review result'
    call = json.loads((tmp / 'call.json').read_text())
    assert call['args'][0] == 'exec' and '--no-session-log' in call['args'] and '--yolo' in call['args']
    assert call['args'][-2:] == ['--', '-leading dash']
    assert not [name for name in call['tmp_files'] if 'once' in name]  # No prompt file to leak.


def test_unified_can_follow_up_and_stop_a_legacy_session(harness):
    name, run, _ = harness
    if not shutil.which('tmux'):
        pytest.skip('Unified legacy lifecycle')
    session = run().stdout.strip()
    try:
        assert run('wait', session, unified=True).returncode == 0
        result = run('send', session, prompt='UNIFIED_SUPPLEMENT', unified=True)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)['delivery'] == ('confirmed' if name == 'cursor' else 'submitted')
        result = run('wait', session, unified=True)
        assert result.returncode == 0 and result.stdout.strip() == 'ANSWER:UNIFIED_SUPPLEMENT'
    finally:
        assert run('stop', session, unified=True).returncode == 0


@pytest.mark.parametrize('failure', ['input_unavailable', 'dead_pane'])
def test_unified_failed_send_cannot_replay_previous_reply(harness, failure):
    name, run, tmp = harness
    if name != 'gpt' or not shutil.which('tmux'):
        pytest.skip('Unified batch failure recovery')
    started = run('start', '--backend', 'claude', '--backend', 'gpt', unified=True)
    sessions = [item['session'] for item in json.loads(started.stdout)['sessions']]
    def tmux(*args):
        return subprocess.run(['tmux', *args], env=run.env, capture_output=True, text=True, check=True).stdout.strip()
    try:
        assert run('wait', *sessions, unified=True).returncode == 0
        wait_for(run, sessions[1], 'status', 'input_ready=1')
        if failure == 'dead_pane':
            pane = tmux('show-options', '-v', '-t', sessions[0], '@review_pane')
            tmux('respawn-pane', '-k', '-t', pane, 'exit 7')
            wait_for(lambda *args: run(*args, unified=True), sessions[0], 'status', 'dead=1')
        else:
            state = Path(tmux('show-options', '-v', '-t', sessions[0], '@review_paste_state'))
            state.write_text('0')
        sent = run('send', *sessions, prompt='SUPPLEMENT', unified=True)
        assert sent.returncode == 1, sent.stderr
        assert json.loads(sent.stdout)['results'][0]['delivery'] == 'failed'
        reply = run('wait', *sessions, '--timeout', '2', unified=True)
        assert reply.returncode == 1, reply.stderr
        results = json.loads(reply.stdout)['results']
        assert results[0]['is_error'] and not results[0]['result']
        assert results[1]['result'] == 'ANSWER:SUPPLEMENT'
        if failure == 'input_unavailable':
            state.write_text('1')
            assert run('send', sessions[0], prompt='RETRY', unified=True).returncode == 0
            assert run('wait', sessions[0], unified=True).stdout.strip() == 'ANSWER:RETRY'
    finally:
        run('stop', *sessions, unified=True)


def test_wait_rejects_empty_completed_turn(harness):
    name, run, _ = harness
    if not shutil.which('tmux'):
        pytest.skip('Native completion validation')
    session = run().stdout.strip()
    try:
        assert run('wait', session).returncode == 0
        directory = subprocess.run(['tmux', 'show-options', '-v', '-t', session, '@review_turn_dir'],
                                   env=run.env, text=True, capture_output=True, check=True).stdout.strip()
        # A real completion hook may publish a finished turn without an answer.
        subprocess.run([str(SKILLS / 'agent-team/scripts/turn-notifier')],
                       input=json.dumps({'last_assistant_message': ' \n '}), text=True, check=True,
                       env=run.env | {'REVIEW_SUBAGENT_TURN_DIR': directory})
        reply = run('wait', session)
        assert reply.returncode == 1 and not reply.stdout.strip()
        assert 'empty' in reply.stderr
    finally:
        run('stop', session)


def test_start_accepts_claude_trust_dialog(harness):
    name, run, tmp_path = harness
    if name not in ('claude', 'ds') or not shutil.which('tmux'):
        pytest.skip('Claude Code trust dialog')
    (tmp_path / 'trust-prompt').touch()
    session = run().stdout.strip()
    try:
        assert run('wait', session, '--timeout', '10').returncode == 0
    finally:
        run('stop', session)


def test_wait_fails_on_stuck_claude_trust_dialog(harness):
    name, run, tmp_path = harness
    if name not in ('claude', 'ds') or not shutil.which('tmux'):
        pytest.skip('Claude Code trust dialog')
    (tmp_path / 'trust-prompt').write_text('stuck')
    session = run().stdout.strip()
    try:
        reply = run('wait', session, '--timeout', '30')
        assert reply.returncode == 1 and 'trust dialog' in reply.stderr
    finally:
        run('stop', session)


def test_once_pins_and_json(harness):
    name, run, tmp = harness
    result = run('--once', '--output-format', 'json')
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {'result': 'review result', 'exit_code': 0, 'is_error': False}
    call = json.loads((tmp / 'call.json').read_text())
    args = call['args']
    assert args[args.index('--model') + 1] == {'claude': 'opus', 'gpt': 'gpt-6-astra', 'cursor': 'gemini-4-argon-high', 'ds': 'deepseek-flash[1m]'}[name]
    assert call['sentinel'] == '1'
    if name in ('claude', 'ds'):
        assert args[args.index('--effort') + 1] == 'high'
        assert call['launcher'] == {'claude': 'c', 'ds': 'ds'}[name]
    elif name == 'gpt':
        assert 'model_reasoning_effort="high"' in args
        assert '--dangerously-bypass-approvals-and-sandbox' in args
    else:
        assert '--mode' not in args
        assert call['config']['permissions']['deny'] == []
        assert '--force' in args and '--approve-mcps' in args
        assert args[args.index('--sandbox') + 1] == 'disabled'
        assert '--trust' in args


@pytest.mark.parametrize('mode', ['start', '--once'])
def test_cursor_launch_has_all_tool_permissions(harness, mode):
    name, run, tmp = harness
    if name != 'cursor' or (mode == 'start' and not shutil.which('tmux')):
        pytest.skip('Cursor full tool permissions')
    outcome = run(mode, unified=False)
    assert outcome.returncode == 0, outcome.stderr
    session = outcome.stdout.strip() if mode == 'start' else None
    try:
        if session:
            assert run('wait', session).returncode == 0
        call = json.loads((tmp / 'call.json').read_text())
        args = call['args']
        assert args.count('--force') == 1 and args.count('--approve-mcps') == 1
        assert args[args.index('--sandbox') + 1] == 'disabled'
        assert call['config']['permissions']['deny'] == []
        assert {'Read(**)', 'Write(**)', 'Shell(*)', 'Mcp(*:*)', 'WebFetch(*)'} <= set(call['config']['permissions']['allow'])
    finally:
        if session:
            assert run('stop', session).returncode == 0


@pytest.mark.parametrize('mode', ['--once', 'start'])
def test_gpt_matches_unsandboxed_launcher(harness, mode):
    name, run, tmp = harness
    if name != 'gpt':
        pytest.skip('GPT-only sandbox selection')
    if mode == 'start' and not shutil.which('tmux'):
        pytest.skip('tmux is required for session launch checks')
    result = run(mode)
    assert result.returncode == 0, result.stderr
    session = result.stdout.strip() if mode == 'start' else None
    try:
        if session:
            wait_for(run, session, 'capture', 'MOCK_READY')
        args = json.loads((tmp / 'call.json').read_text())['args']
        assert args[args.index('--model') + 1] == 'gpt-6-astra'
        assert 'model_reasoning_effort="high"' in args
        # Like the user's `x --yolo`: no approvals and no sandbox, so network is always available.
        assert '--dangerously-bypass-approvals-and-sandbox' in args and '--sandbox' not in args
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


@pytest.mark.parametrize('args', [('--model', 'other'), ('--effort', 'max'), ('--settings', '{}')])
def test_override_rejected(harness, args):
    _, run, tmp = harness
    assert run('--once', *args).returncode == 2
    assert not (tmp / 'call.json').exists()


def test_failures_and_empty_result(harness):
    name, run, _ = harness
    r = run('--once', '--output-format', 'json', extra_env={'MOCK_EXIT': '9'})
    assert r.returncode == 9
    assert json.loads(r.stdout)['is_error'] is True
    r = run('--once', extra_env={'MOCK_RESULT': ''})
    assert r.returncode == 1
    assert ('no complete terminal result' if name == 'cursor' else 'empty response') in r.stderr
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
    r = run('wait', session)
    expected = 'DRAFT:assignment\n\nANSWER:assignment' if name == 'gpt' else 'ANSWER:assignment'
    assert (r.returncode, r.stdout.strip()) == (0, expected), r.stderr
    r = run('capture', session)  # Point callers polling the screen at `wait`.
    assert 'turn finished' in r.stderr and 'wait' in r.stderr, r.stderr
    wait_for(run, session, 'status', 'input_ready=1')
    assert session in run('list').stdout
    assert run('send', session, prompt='FOLLOWUP_123').returncode == 0
    r = run('wait', session)  # Blocks for the turn hook, even if it fired before wait started.
    assert (r.returncode, r.stdout.strip()) == (0, 'ANSWER:FOLLOWUP_123'), r.stderr
    if name == 'cursor':
        call = json.loads((tmp / 'call.json').read_text())
        args = call['args']
        assert args[args.index('--resume') + 1] == 'cursor-main'
        assert '--mode' not in args
        assert args[args.index('--model') + 1] == 'gemini-4-argon-high'
        assert '--trust' in args
    assert run('send', session, prompt='SILENT').returncode == 0
    r = run('wait', session, '--timeout', '1')  # No new turn yet: times out instead of replaying the old one.
    assert r.returncode == 124, (r.stdout, r.stderr)
    assert 'turn running' in run('status', session).stderr
    assert 'FOLLOWUP_123' in run('capture', session).stdout
    assert run('interrupt', session).returncode == 0
    wait_for(run, session, 'status', 'input_ready=1')
    assert run('send', session, prompt='EXIT_NOW').returncode == (1 if name == 'cursor' else 0)
    wait_for(run, session, 'status', 'dead=1 exit_code=7')
    assert run('wait', session).returncode == 1  # A dead pane ends the wait instead of hanging.
    if name != 'cursor':
        assert run('send', session).returncode == 1
    assert run('stop', session).returncode == 0
    assert session not in run('list').stdout
    assert run('status', session).returncode == 1
    assert run('stop', 'unrelated-session').returncode == 2


def test_paste_mode_tracker(tmp_path):
    state = tmp_path / 'state'
    proc = subprocess.Popen([str(SKILLS / 'agent-team' / 'scripts' / 'paste-mode-tracker'), str(state)],
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


@pytest.mark.parametrize('events', [
    {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'I will inspect later.'}]}},
    {'type': 'result', 'is_error': False, 'result': 'answer without conversation identity'},
])
def test_cursor_tmux_rejects_incomplete_turn(harness, events):
    name, run, _ = harness
    if name != 'cursor' or not shutil.which('tmux'):
        pytest.skip('Cursor completion validation')
    result = run(extra_env={'MOCK_CURSOR_EVENTS': json.dumps(events)})
    assert result.returncode == 0, result.stderr
    session = result.stdout.strip()
    try:
        result = run('wait', session, '--timeout', '5')
        assert result.returncode == 1, (result.stdout, result.stderr)
        assert not result.stdout.strip()
    finally:
        assert run('stop', session).returncode == 0


def test_cursor_multiline_followup_is_complete(harness):
    name, run, _ = harness
    if name != 'cursor' or not shutil.which('tmux'):
        pytest.skip('Cursor multiline input')
    session = run().stdout.strip()
    try:
        assert run('wait', session).returncode == 0
        wait_for(run, session, 'status', 'input_ready=1')
        message = '第一行\n' + '证据 🙂\n' * 400 + '最后一行'
        assert run('send', session, prompt=message).returncode == 0
        result = run('wait', session)
        assert (result.returncode, result.stdout.strip()) == (0, 'ANSWER:' + message)
    finally:
        assert run('stop', session).returncode == 0


def test_cursor_accepts_messages_during_a_turn(harness):
    name, run, tmp = harness
    if name != 'cursor' or not shutil.which('tmux'):
        pytest.skip('Cursor busy-message delivery')
    session = run(prompt='BUSY_INITIAL', extra_env={'MOCK_CURSOR_STEER_SECONDS': '0.5'}).stdout.strip()
    try:
        deadline = time.monotonic() + 5
        while not (tmp / 'BUSY_INITIAL.started').exists() and time.monotonic() < deadline:
            time.sleep(.05)
        assert (tmp / 'BUSY_INITIAL.started').exists()
        first = run('send', session, prompt='BUSY_FOLLOWUP')
        assert first.returncode == 0, first.stderr
        message = '补充上下文\n保留此前分析 🙂'
        second = run('send', session, prompt=message)
        assert second.returncode == 0, second.stderr
        assert 'input_ready=1' in run('status', session).stdout
        (tmp / 'BUSY_INITIAL.release').touch()
        # The initial result must not satisfy wait after queued messages.
        assert run('wait', session, '--timeout', '1').returncode == 124
        (tmp / 'BUSY_FOLLOWUP.release').touch()
        result = run('wait', session, '--timeout', '8')
        assert (result.returncode, result.stdout.strip()) == (0, 'ANSWER:' + message), result.stderr
        assert 'turn finished' in run('status', session).stderr
        args = json.loads((tmp / 'call.json').read_text())['args']
        assert args[args.index('--resume') + 1] == 'cursor-main'
    finally:
        assert run('stop', session).returncode == 0


@pytest.mark.parametrize('message', ['BUSY_FOLLOWUP', '第一行\nsecond line\nthird line'])
def test_cursor_send_waits_for_delayed_steering(harness, message):
    name, run, tmp = harness
    if name != 'cursor' or not shutil.which('tmux'):
        pytest.skip('Cursor delayed steering')
    session = run(prompt='BUSY_INITIAL', extra_env={'MOCK_CURSOR_FOOTER_DELAY': '0.8'}).stdout.strip()
    try:
        wait_for(run, session, 'status', 'input_ready=1')
        result = run('send', session, prompt=message)
        assert result.returncode == 0, result.stderr
        time.sleep(.9)
        assert (tmp / 'steering.started').exists(), 'send succeeded without activating steering'
        assert '│ enter interrupt and send ·' in run('capture', session).stdout
    finally:
        assert run('stop', session).returncode == 0


def test_cursor_send_waits_for_paste_to_render(harness):
    name, run, tmp = harness
    if name != 'cursor' or not shutil.which('tmux'):
        pytest.skip('Cursor paste rendering')
    session = run(prompt='BUSY_INITIAL', extra_env={'MOCK_CURSOR_PASTE_DELAY': '0.5'}).stdout.strip()
    try:
        wait_for(run, session, 'status', 'input_ready=1')
        result = run('send', session, prompt='BUSY_FOLLOWUP')
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert (tmp / 'steering.started').exists()
    finally:
        assert run('stop', session).returncode == 0


def test_cursor_wait_steers_followup_queued_behind_a_steer(harness):
    name, run, tmp = harness
    if name != 'cursor' or not shutil.which('tmux'):
        pytest.skip('Cursor queued steering')
    session = run(prompt='BUSY_INITIAL', extra_env={'MOCK_CURSOR_STEER_SECONDS': '11'}).stdout.strip()
    try:
        wait_for(run, session, 'status', 'input_ready=1')
        assert run('send', session, prompt='FIRST').returncode == 0
        # Cursor steers one message at a time; the second stays queued past send's window.
        assert run('send', session, prompt='SECOND').returncode == 124
        assert run('wait', session, '--timeout', '4').returncode == 124
        assert (tmp / 'steering.started').read_text().split() == ['FIRST', 'SECOND']
    finally:
        assert run('stop', session).returncode == 0


def test_cursor_manages_sessions_started_as_gemini(harness):
    name, run, _ = harness
    if name != 'cursor' or not shutil.which('tmux'):
        pytest.skip('Sessions started before the gemini backend was renamed')
    session = run().stdout.strip()
    legacy = 'gemini' + session[len('cursor'):]
    turn_dir = Path(subprocess.run(['tmux', 'show-options', '-v', '-t', session, '@review_turn_dir'],
                                   env=run.env, capture_output=True, text=True, check=True).stdout.strip())
    subprocess.run(['tmux', 'rename-session', '-t', '=' + session, legacy], env=run.env, check=True)
    try:
        assert legacy in run('list', unified=True).stdout.split()
        assert run('wait', legacy, unified=True).stdout.strip() == 'ANSWER:assignment'
        # Its turn directory carries the old backend name too.
        old_dir = turn_dir.with_name(turn_dir.name.replace('-cursor-', '-gemini-'))
        turn_dir.rename(old_dir)
        subprocess.run(['tmux', 'set-option', '-t', legacy, '@review_turn_dir', str(old_dir)], env=run.env, check=True)
    finally:
        assert run('stop', legacy, unified=True).returncode == 0
    assert legacy not in run('list', unified=True).stdout.split()
    assert not old_dir.exists()


def test_cursor_wait_reports_stream_crash_with_unverified_text(harness):
    name, run, _ = harness
    if name != 'cursor' or not shutil.which('tmux'):
        pytest.skip('Cursor stream crash')
    session = run(extra_env={'MOCK_CURSOR_CRASH': '1'}).stdout.strip()
    try:
        result = run('wait', session, '--timeout', '20')
        assert (result.returncode, result.stdout) == (1, ''), result.stderr
        # Each automatic continuation crashes too, so the last one is reported.
        assert 'auto-continued 2/2' in result.stderr and 'WritableIterable is closed' in result.stderr
        assert 'unverified text' in result.stderr and 'ANSWER:The previous turn ended early' in result.stderr
    finally:
        assert run('stop', session).returncode == 0


def test_cursor_wait_reports_a_message_that_missed_a_crashed_turn(harness):
    name, run, tmp = harness
    if name != 'cursor' or not shutil.which('tmux'):
        pytest.skip('Cursor crash before steering')
    env = {'MOCK_CURSOR_CRASH': '1', 'MOCK_CURSOR_IGNORE_STEER': '1', 'AGENT_TEAM_CURSOR_UNDELIVERED_MS': '1000'}
    session = run(prompt='BUSY_INITIAL', extra_env=env).stdout.strip()
    try:
        wait_for(run, session, 'status', 'input_ready=1')
        assert run('send', session, prompt='FIRST').returncode == 124
        (tmp / 'BUSY_INITIAL.release').touch()
        result = run('wait', session, '--timeout', '10')
        assert result.returncode == 1, result.stderr
        assert 'not delivered' in result.stderr and 'auto-continued' not in result.stderr
    finally:
        assert run('stop', session).returncode == 0


def test_cursor_wait_auto_continues_after_stream_crash(harness):
    name, run, _ = harness
    if name != 'cursor' or not shutil.which('tmux'):
        pytest.skip('Cursor stream crash')
    session = run(extra_env={'MOCK_CURSOR_CRASHES': '1'}).stdout.strip()
    try:
        result = run('wait', session, '--timeout', '20')
        assert result.returncode == 0, result.stderr
        assert 'auto-continued 1/2' in result.stderr
        assert result.stdout.strip().startswith('ANSWER:The previous turn ended early')
    finally:
        assert run('stop', session).returncode == 0


@pytest.mark.parametrize('failure', ['MOCK_CURSOR_HIDE_FOOTER', 'MOCK_CURSOR_IGNORE_STEER'])
def test_cursor_send_reports_unconfirmed_delivery(harness, failure):
    name, run, tmp = harness
    if name != 'cursor' or not shutil.which('tmux'):
        pytest.skip('Cursor unconfirmed steering')
    session = run(prompt='BUSY_INITIAL', extra_env={failure: '1'}).stdout.strip()
    try:
        wait_for(run, session, 'status', 'input_ready=1')
        result = run('send', session, prompt='BUSY_FOLLOWUP')
        assert result.returncode == 124, (result.stdout, result.stderr)
        assert 'unconfirmed' in result.stderr and 'do not resend' in result.stderr
        assert not (tmp / 'steering.started').exists()
    finally:
        assert run('stop', session).returncode == 0
