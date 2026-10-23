"""Offline boundary checks; run with uv run --with pytest pytest <this file>."""
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).parents[1] / 'scripts' / 'mjob'
loader = importlib.machinery.SourceFileLoader('mjob', str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)


def reply(data, token=None):
    return {'ResponseBase': {'code': 0}, 'data': data,
            'pagination': {'next_page_token': token}}


@pytest.mark.parametrize('wrap', [lambda x: x, lambda x: {'data': {'result': x}},
                                  lambda x: {'tool': 'merlin', 'result': x}])
def test_prefix_and_envelopes(wrap):
    response = reply([{'sid': 'one'}], '2')
    assert m.decode_response('Warning {not JSON}\n' + json.dumps(wrap(response))) == response


def test_nested_error_is_not_success():
    response = {'data': {'result': {'ResponseBase': {
        'code': 403, 'code_name': 'AccessResourceDenied',
        'message': 'denied token=secret-value https://logs.test/?signature=hidden'}}}}
    with pytest.raises(m.MjobError) as exc:
        m.decode_response(json.dumps(response))
    assert 'AccessResourceDenied' in str(exc.value)
    assert 'secret-value' not in str(exc.value)
    assert 'signature=hidden' not in str(exc.value)


def test_pages_follow_tokens_even_after_empty_page(monkeypatch):
    client = m.Client()
    calls = []
    responses = iter([reply([], '2'), reply([{'sid': 'two'}])])
    def call(command, body):
        calls.append(body.copy())
        return next(responses)
    monkeypatch.setattr(client, 'call', call)
    assert list(client.pages(('job-v2', 'runs', 'list'), {'filter': {}})) == [{'sid': 'two'}]
    assert calls[1]['page_token'] == '2'


def test_repeated_page_token_fails(monkeypatch):
    client = m.Client()
    monkeypatch.setattr(client, 'call', lambda *a: reply([], '2'))
    with pytest.raises(m.MjobError, match='page token'):
        list(client.pages(('job-v2', 'runs', 'list'), {}))


def run(sid='one', status='started', creator='liuyuhao.chris', trial='10', priority=40):
    return {'sid': sid, 'status': status, 'job_type': 'train', 'created_by': creator, 'name': 'a\nname',
            'runtime_context': {'trial_id': trial, 'trial_status': 'queued'},
            'attachments': [{'arnold_cluster_control_attachment': {'queue_priority': priority}}],
            'resource_config': {'arnold_resource_config': {'group_id': 1043,
                'roles': [{'num': 2, 'gpu': 8}, {'num': 3, 'gpu': 4}]}}}


def test_mine_rechecks_creator_status_and_group(monkeypatch):
    client = m.Client()
    wrong_group = run('wrong-group')
    wrong_group['resource_config']['arnold_resource_config']['group_id'] = 999
    rows = [run(), run('other', creator='other'), run('done', status='done'),
            run('launch', status='launching'), wrong_group]
    seen = []
    def pages(command, body):
        seen.append(body)
        return iter(rows)
    monkeypatch.setattr(client, 'pages', pages)
    args = SimpleNamespace(user='liuyuhao.chris', group=1043, since=None, gpu_only=False)
    assert [r['sid'] for r in m.mine_runs(client, args)] == ['one', 'launch']
    assert seen[0]['filter']['created_by_any'] == ['liuyuhao.chris']
    assert seen[0]['filter']['status_any'] == ['running', 'started', 'launching']


def test_gpu_only_excludes_zero_gpu_and_nontraining(monkeypatch):
    client = m.Client()
    cpu = run('cpu')
    cpu['resource_config']['arnold_resource_config']['roles'] = [{'num': 1, 'gpu': 0}]
    devbox = run('devbox')
    devbox['job_type'] = 'persistent_job'
    evaluation = run('evaluation')
    evaluation['job_type'] = 'evaluation'
    monkeypatch.setattr(client, 'pages', lambda *a: iter([run(), cpu, devbox, evaluation]))
    args = SimpleNamespace(user='liuyuhao.chris', group=1043, since=None, gpu_only=True)
    assert [r['sid'] for r in m.mine_runs(client, args)] == ['one']


def test_brief_and_current_trial_start(monkeypatch):
    client = m.Client()
    monkeypatch.setattr(client, 'pages', lambda *a: iter([
        {'sid': '9', 'job_run_sid': 'one', 'start_at': 'old'},
        {'sid': '10', 'job_run_sid': 'one', 'start_at': ''}]))
    starts = m.trial_starts(client, [run()])
    line = m.brief_line(run(), starts)
    assert 'status=started' in line and 'state=queued' in line
    assert 'gpus=28' in line and 'start_at=-' in line and 'old' not in line
    assert '\n' not in line


def test_queue_matches_reference_sort_and_excludes_running():
    rows = [run('b', trial='12'), run('a', trial='11'), run('urgent', priority=0),
            run('running', status='running'), run('missing', priority=None)]
    rows[3]['runtime_context']['trial_status'] = 'running'
    assert [r['sid'] for r in m.queue_runs(rows)] == ['urgent', 'a', 'b', 'missing']


def test_capacity_sums_only_target_gpu_queues():
    clusters = [{'cluster_sid': '47', 'queues': [
        {'node_type': 'gpu', 'total': {'gpu': {'NVIDIA-H20': 16}},
         'used': {'gpu': {'NVIDIA-H20': 8}}},
        {'node_type': 'gpu', 'total': {'gpu': {'NVIDIA-H20': 4}}},
        {'node_type': 'cpu', 'total': {'gpu': {'NVIDIA-H20': 99}}}]}]
    assert m.capacity({'group': {'resources': {'clusters': clusters}}}, '47') == (20, 8, 12)
    with pytest.raises(m.MjobError):
        m.capacity({'group': {'resources': {'clusters': clusters}}}, '999')


def test_rank_selection_not_api_order_and_ambiguous_rank_fails():
    pods = [{'sid': '9', 'pod_name': 'trial-executor-9'},
            {'sid': '0', 'pod_name': 'trial-executor-0'}]
    assert m.select_pod(pods, 0)['sid'] == '0'
    with pytest.raises(m.MjobError):
        m.select_pod(pods, 2)
    with pytest.raises(m.MjobError):
        m.select_pod(pods + [{'sid': 'x', 'pod_name': 'trial-worker-0'}], 0)


@pytest.mark.parametrize('local', [True, False])
def test_logs_filter_then_tail_and_tls_pagination(monkeypatch, capsys, local):
    client = m.Client()
    seen = []
    def call(command, body):
        seen.append((command, body))
        if command[1] == 'runs':
            return reply(run())
        return reply({'url': 'https://logs.test/signed' if local else ''})
    def pages(command, body):
        seen.append((command, body))
        if command[1] == 'run-trial-pods':
            return iter([{'sid': 'pod0', 'pod_name': 'trial-executor-0'}])
        return iter([{'content': 'step=1\nnoise'}, {'content': 'step=2\nstep=3'}])
    monkeypatch.setattr(client, 'call', call)
    monkeypatch.setattr(client, 'pages', pages)
    monkeypatch.setattr(m.urllib.request, 'urlopen', lambda *a, **kw:
                        io.BytesIO(b'step=1\nnoise\nstep=2\nstep=3\n'))
    args = SimpleNamespace(sid='one', rank=0, grep='step=', tail=2, since_min=60)
    m.show_logs(client, args)
    assert capsys.readouterr().out == 'step=2\nstep=3\n'
    if not local:
        query = seen[-1][1]['filter']
        assert query['trial_pod_sid'] == 'pod0' and query['trial_sid'] == '10'
        assert query['timestamp_ms_to'] - query['timestamp_ms_from'] == 3600000
        assert 'keyword' not in query


def test_cli_transport_is_read_only_json_body(monkeypatch):
    def process(argv, **kwargs):
        assert argv[:6] == ['merlin-cli', '--control-plane', 'cn-seed', 'job-v2', 'runs', 'get']
        assert argv[6] == '--json' and json.loads(argv[7]) == {'sid': 'one'}
        return SimpleNamespace(returncode=0, stdout=json.dumps(reply(run())), stderr='')
    monkeypatch.setattr(m.subprocess, 'run', process)
    assert m.Client().call(('job-v2', 'runs', 'get'), {'sid': 'one'})['data']['sid'] == 'one'
