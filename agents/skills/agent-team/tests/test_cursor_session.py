"""Native transcript rewrites must not complete an unfinished or stale reply."""
import json
import os
from pathlib import Path
import subprocess
import time

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'cursor-session.mjs'


def record(role, text):
    return {'role': role, 'message': {'content': [{'type': 'text', 'text': text}]}}


def until(predicate):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    assert predicate()


@pytest.fixture
def session(tmp_path):
    transcript = tmp_path / 'primary.jsonl'
    (tmp_path / 'transcript-paths.json').write_text(json.dumps([str(transcript)]))
    watcher = subprocess.Popen(['node', str(SCRIPT), 'watch', str(tmp_path)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env=os.environ | {'AGENT_TEAM_CURSOR_UNDELIVERED_MS': '500'})
    try:
        yield tmp_path, transcript
        assert watcher.poll() is None
    finally:
        watcher.terminate()
        watcher.communicate(timeout=5)


def write(transcript, records):
    replacement = transcript.with_suffix('.tmp')
    replacement.write_text(''.join(json.dumps(item, ensure_ascii=False) + '\n' for item in records))
    replacement.replace(transcript)


def test_only_explicit_success_completes_full_reply_after_rewrites(session):
    directory, transcript = session
    history = [record('user', 'Review the brief.'), record('assistant', 'I will inspect it.')]
    write(transcript, history)
    time.sleep(0.25)
    assert not (directory / 'done').exists()
    transcript.write_text(json.dumps(history[0]) + '\n{"role":')
    time.sleep(0.25)
    assert not (directory / 'done').exists()
    reply = '完整结论🙂\n' * 2000
    history[-1] = record('assistant', reply)
    complete = history + [{'type': 'turn_ended', 'status': 'success'}]
    write(transcript, complete)
    until(lambda: (directory / 'done').exists())
    assert (directory / 'last').read_text() == reply
    write(transcript, complete)
    time.sleep(0.25)
    assert (directory / 'done').read_text() == '1'
    # Cursor rewrites history with only the latest completion marker.
    history += [record('user', 'Follow up.'), record('assistant', 'Second answer.')]
    write(transcript, history + [{'type': 'turn_ended', 'status': 'success'}])
    until(lambda: (directory / 'done').read_text() == '2')
    assert (directory / 'last').read_text() == 'Second answer.'


def test_pending_supplement_cannot_be_satisfied_by_previous_answer(session):
    directory, transcript = session
    history = [record('user', 'Original.'), record('assistant', 'Previous answer.')]
    write(transcript, history + [{'type': 'turn_ended', 'status': 'success'}])
    until(lambda: (directory / 'done').exists())
    message = directory / 'message.txt'
    message.write_text('补充信息\nsecond line\n')
    subprocess.run(['node', str(SCRIPT), 'mark-send', str(directory), str(message)], check=True)
    # Another answer to the old user input must not release wait for the new input.
    history[-1] = record('assistant', 'Old turn finished just after send.')
    write(transcript, history + [{'type': 'turn_ended', 'status': 'success'}])
    time.sleep(0.25)
    assert (directory / 'done').read_text() == '1'
    assert (directory / 'latest-message.json').exists()
    history += [record('user', '<user_query>\n补充信息\nsecond line\n</user_query>'),
                record('assistant', 'Supplement included.')]
    write(transcript, history + [{'type': 'turn_ended', 'status': 'aborted'}])
    until(lambda: (directory / 'error').exists())
    assert (directory / 'done').read_text() == '1'
    assert not (directory / 'latest-message.json').exists()
    write(transcript, history + [{'type': 'turn_ended', 'status': 'success'}])
    until(lambda: (directory / 'done').read_text() == '2')
    assert not (directory / 'error').exists()


def test_full_permissions_are_session_local_and_clear_inherited_denials(tmp_path):
    original = tmp_path / 'original'
    original.mkdir()
    config = {'theme': 'light', 'permissions': {'allow': ['Shell(*)'], 'deny': ['Read(secret)']}}
    source = original / 'cli-config.json'
    source.write_text(json.dumps(config))
    target = tmp_path / 'review'
    subprocess.run(['node', str(SCRIPT), 'config', str(target)], check=True,
                   env={**os.environ, 'CURSOR_CONFIG_DIR': str(original)})
    result = json.loads((target / 'cli-config.json').read_text())
    assert json.loads(source.read_text()) == config
    assert result['theme'] == 'light'
    assert result['steering'] is True
    assert result['modelSlashCommands'] is False
    assert result['permissions']['deny'] == []
    assert {'Read(**)', 'Write(**)', 'Shell(*)', 'Mcp(*:*)', 'WebFetch(*)'} <= set(result['permissions']['allow'])
    assert (target / 'cli-config.json').stat().st_mode & 0o777 == 0o600


# Records Cursor injects itself, copied from live transcripts.
INTERRUPTED = 'Your previous response was interrupted. Continue from where you left off.'
TIMESTAMP = '<timestamp>Friday, Oct 9, 2026, 6:50 PM (UTC+8)</timestamp>'
NOTICE = (TIMESTAMP + '\n\n<user_query>Briefly inform the user about the task result and perform '
          'any follow-up actions (if needed).</user_query>')


def supplement(directory, history):
    write(directory / 'primary.jsonl', history + [{'type': 'turn_ended', 'status': 'success'}])
    until(lambda: (directory / 'done').exists())
    message = directory / 'message.txt'
    message.write_text('补充信息\nsecond line\n')
    subprocess.run(['node', str(SCRIPT), 'mark-send', str(directory), str(message)], check=True)
    return history + [record('user', TIMESTAMP + '\n<user_query>\n补充信息\nsecond line\n</user_query>'),
                      record('assistant', 'Supplement included.')]


def test_cursor_injected_user_records_do_not_hide_the_supplement(session):
    directory, transcript = session
    history = supplement(directory, [record('user', 'Original.'), record('assistant', 'Previous answer.')])
    history += [record('user', INTERRUPTED), record('assistant', 'Already complete.'),
                record('user', TIMESTAMP), record('user', NOTICE), record('assistant', 'Background job done.')]
    write(transcript, history + [{'type': 'turn_ended', 'status': 'success'}])
    until(lambda: (directory / 'done').read_text() == '2')
    assert not (directory / 'latest-message.json').exists()
    assert (directory / 'last').read_text() == 'Supplement included.\n\nAlready complete.\n\nBackground job done.'


def test_cursor_stream_crash_fails_the_pending_supplement(session):
    directory, transcript = session
    history = supplement(directory, [record('user', 'Original.'), record('assistant', 'Previous answer.')])
    history += [record('user', NOTICE), record('assistant', 'Background job done.')]
    write(transcript, history + [{'type': 'turn_ended', 'status': 'error', 'error': 'WritableIterable is closed'}])
    until(lambda: (directory / 'error').exists())
    assert 'WritableIterable is closed' in (directory / 'error').read_text()
    assert not (directory / 'latest-message.json').exists()
    # The text before the crash is kept for inspection, not reported as a reply.
    assert (directory / 'partial').read_text() == 'Supplement included.\n\nBackground job done.'
    write(transcript, history + [{'type': 'turn_ended', 'status': 'success'}])
    until(lambda: (directory / 'done').read_text() == '2')
    assert not (directory / 'partial').exists()


def pending(directory, history):
    """Mark a supplement that Cursor holds as steering or queued, outside the transcript."""
    write(directory / 'primary.jsonl', history + [{'type': 'turn_ended', 'status': 'success'}])
    until(lambda: (directory / 'done').exists())
    message = directory / 'message.txt'
    message.write_text('补充信息\n')
    subprocess.run(['node', str(SCRIPT), 'mark-send', str(directory), str(message)], check=True)
    return history + [record('user', 'Second request.'), record('assistant', 'Partial work.')]


def test_cursor_crash_before_the_supplement_joins_reports_it_undelivered(session):
    directory, transcript = session
    history = pending(directory, [record('user', 'Original.'), record('assistant', 'Previous answer.')])
    write(transcript, history + [{'type': 'turn_ended', 'status': 'error', 'error': 'Connection stalled'}])
    until(lambda: (directory / 'error').exists())
    error = (directory / 'error').read_text()
    assert 'Connection stalled' in error and 'not delivered' in error
    # The marker stays, so wait does not resume the turn and silently drop the message.
    assert (directory / 'latest-message.json').exists()
    assert (directory / 'done').read_text() == '1'


def test_cursor_crash_before_the_supplement_joins_waits_for_its_follow_up(session):
    directory, transcript = session
    history = pending(directory, [record('user', 'Original.'), record('assistant', 'Previous answer.')])
    history += [{'type': 'turn_ended', 'status': 'error', 'error': 'Connection stalled'}]
    write(transcript, history)
    time.sleep(0.2)
    # Cursor submits the queued message as a follow-up within the grace period.
    history += [record('user', TIMESTAMP + '\n<user_query>\n补充信息\n</user_query>'), record('assistant', 'Follow-up answer.')]
    write(transcript, history + [{'type': 'turn_ended', 'status': 'success'}])
    until(lambda: (directory / 'done').read_text() == '2')
    time.sleep(0.6)
    assert not (directory / 'error').exists()
    assert (directory / 'last').read_text() == 'Follow-up answer.'


def test_cursor_turn_that_ended_before_the_supplement_is_never_replayed(session):
    directory, transcript = session
    history = pending(directory, [record('user', 'Original.'), record('assistant', 'Previous answer.')])
    history += [{'type': 'turn_ended', 'status': 'success'}]
    write(transcript, history)
    time.sleep(0.2)
    # The queued message runs as a follow-up; the turn it missed must not count afterwards.
    history += [record('user', TIMESTAMP + '\n<user_query>\n补充信息\n</user_query>'), record('assistant', 'Follow-up answer.')]
    write(transcript, history + [{'type': 'turn_ended', 'status': 'success'}])
    until(lambda: (directory / 'done').read_text() == '2')
    time.sleep(0.3)
    assert (directory / 'done').read_text() == '2'
    assert (directory / 'last').read_text() == 'Follow-up answer.'
