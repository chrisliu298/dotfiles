const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const cp = require('node:child_process');
const {composer} = require('./agent-msg');
const source = path.join(__dirname, 'agent-msg');

test('composer rejects modals/unknown layouts and preserves multiline drafts', () => {
  assert.equal(composer('❯ \n────\nstatus', 'claude'), '');
  assert.equal(composer('❯ \n  do not send\n────\nstatus', 'claude'), 'do not send');
  assert.throws(() => composer('❯ 1. Yes\nEnter to select\n────', 'claude'), /modal/);
  assert.throws(() => composer('❯ draft', 'claude'), /incomplete/);
  assert.throws(() => composer('❯ [Pasted text 4 lines]\n────', 'claude'), /collapsed/);
  assert.equal(composer('› \x1b[2mAsk Codex to do anything\n \n\x1b[49m footer', 'codex'), '');
  assert.equal(composer('› Ask Codex to do anything\n \n\x1b[49m footer', 'codex'), 'Ask Codex to do anything');
});

test('Claude dim prompt suggestions are empty only with the cursor at the empty input origin', () => {
  const raw = '\x1b[39m❯\u00a0\x1b[2m目前进度如何\x1b[0m\n────\nstatus';
  assert.equal(composer(raw, 'claude', {cursorX: 2, cursorY: 0}), '');
  assert.equal(composer(raw, 'claude'), '目前进度如何');
  assert.equal(composer(raw, 'claude', {cursorX: 8, cursorY: 0}), '目前进度如何');
  assert.equal(composer(raw, 'claude', {cursorX: 2, cursorY: 1}), '目前进度如何');
  const human = '\x1b[39m❯\u00a0\x1b[38;2;242;242;242m目前进度如何\x1b[39m\n────\nstatus';
  assert.equal(composer(human, 'claude', {cursorX: 2, cursorY: 0}), '目前进度如何');
  const mixed = raw.replace('目前进度如何', '目前进度如何\x1b[0m真实输入');
  assert.equal(composer(mixed, 'claude', {cursorX: 2, cursorY: 0}), '目前进度如何真实输入');
  assert.equal(composer(raw.replace('\n────', '\n真实的第二行\n────'), 'claude', {cursorX: 2, cursorY: 0}), '目前进度如何\n真实的第二行');
  assert.equal(composer(raw.replace('目前进度如何', '目前进度\n如何'), 'claude', {cursorX: 2, cursorY: 0}), '');
  assert.equal(composer(raw.replace('目前进度如何', '目前进度\x1b[0m\n\x1b[2m如何'), 'claude', {cursorX: 2, cursorY: 0}), '');
  assert.throws(() => composer(raw.replace('目前进度如何', '[Pasted text 4 lines]'), 'claude', {cursorX: 2, cursorY: 0}), /collapsed/);
});

// Runs agent-msg against a fake ps/tmux: the caller's parent is PID 42, whose parent is 1.
function fixture(env, state) {
  const output = [];
  const context = {module: {exports: {}}, __filename: source, console: {log: x => output.push(x)},
    process: {...process, env}, setTimeout,
    require(name) {
      if (name !== 'node:child_process') return require(name);
      return {execFileSync(cmd, args, options) {
        if (cmd === '/bin/ps') {
          if (args.at(-1) === 'ppid=') return String(Number(args[1]) === process.pid ? 42 : 1);
          if (args.at(-1) === 'comm=') return state.agentKind;
          if (args.at(-1) === 'lstart=') return (state.starts || {})[args[1]] || 'fixture-start';
        }
        if (cmd !== 'tmux') return cp.execFileSync(cmd, args, options);
        const a = args.slice(2), verb = a[0];
        if (verb === 'display-message') return a.at(-1).includes('pane_in_mode') ? `${state.panePid}\t${state.mode}\t${state.width}\t0\t${state.cursorX ?? 2}\t0` : String(state.panePid);
        if (verb === 'capture-pane') return state.screenKind === 'codex' ? `› ${state.draft}\n \n\x1b[49m footer` : state.suggestion && !state.draft ? `\x1b[39m❯\u00a0\x1b[2m${state.suggestion}\x1b[0m\n────\nstatus` : `❯ ${state.draft}\n────\nstatus`;
        if (verb === 'send-keys' && a.includes('-l')) { state.draft += a.at(-1); if (state.race) state.draft += ' user typing'; return ''; }
        if (verb === 'send-keys' && a.at(-1) === 'Enter') { state.submitted.push(state.draft); state.draft = ''; return ''; }
        throw Error('unexpected tmux call');
      }};
    }};
  vm.runInNewContext(fs.readFileSync(source, 'utf8'), context);
  return {cli: (...args) => context.module.exports.main(args), last: () => JSON.parse(output.at(-1))};
}

test('delivery accepts a Claude ghost suggestion but preserves identical real input and typing races', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'agent-msg-ghost-test-'));
  const sid = '11111111-1111-4111-8111-111111111111';
  const env = {AGENT_MSG_HOME: root, CODEX_THREAD_ID: sid, TMUX_PANE: '%1'};
  const state = {draft: '', suggestion: '目前进度如何', width: 80, mode: 0, panePid: 42,
    race: false, submitted: [], agentKind: 'codex'};
  const {cli, last} = fixture(env, state);
  const body = path.join(root, 'body'); fs.writeFileSync(body, 'peer body');
  try {
    await cli('register', 'sender', '--socket', '/test', '--pid', '42');
    await cli('register', 'target', '--kind', 'claude', '--session', '22222222-2222-4222-8222-222222222222', '--pane', '%2', '--socket', '/test', '--pid', '42');
    await cli('send', 'target', '--file', body, '--id', 'ghost');
    assert.equal(last().state, 'submitted');
    assert.deepEqual(state.submitted, ['[peer] agent-msg read ghost']);
    state.draft = '目前进度如何'; // The user accepted/typed the same words and moved Home.
    await cli('send', 'target', '--file', body, '--id', 'real');
    assert.equal(last().state, 'deferred');
    assert.equal(state.draft, '目前进度如何');
    assert.equal(state.submitted.length, 1);
    state.draft = ''; state.race = true;
    await cli('send', 'target', '--file', body, '--id', 'race');
    assert.equal(last().state, 'typed_unsubmitted');
    assert.equal(state.submitted.length, 1);
  } finally { fs.rmSync(root, {recursive: true}); }
});

test('delivery, drafts, races, deduplication, locks, read/reply and stale identities', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'agent-msg-test-'));
  const sid = '11111111-1111-4111-8111-111111111111';
  const sid2 = '22222222-2222-4222-8222-222222222222';
  const env = {AGENT_MSG_HOME: root, CODEX_THREAD_ID: sid, TMUX_PANE: '%1'};
  const state = {draft: '', width: 80, mode: 0, panePid: 42, race: false, submitted: [], agentKind: 'codex'};
  const {cli, last} = fixture(env, state);
  const body = path.join(root, 'body'); fs.writeFileSync(body, 'peer body');
  try {
    await cli('register', 'sender', '--socket', '/test', '--pid', '42');
    await cli('register', 'target', '--kind', 'claude', '--session', sid2, '--pane', '%2', '--socket', '/test', '--pid', '42');
    // Timers may explicitly wake their own session; ordinary sends cannot loop back.
    await assert.rejects(cli('send', 'sender', '--file', body, '--id', 'self_denied'), /cannot steer own/);
    await assert.rejects(cli('send', '--self', '--file', body), /explicit stable --id/);
    state.screenKind = 'codex';
    await cli('send', '--self', '--file', body, '--id', 'self_tick'); assert.equal(last().state, 'submitted');
    await cli('send', '--self', '--file', body, '--id', 'self_tick'); assert.equal(last().duplicate, true); assert.equal(state.submitted.length, 1);
    await cli('read', 'self_tick'); assert.equal(last().sender, 'codex:' + sid); assert.equal(last().recipient, 'codex:' + sid);
    await assert.rejects(cli('send', 'target', '--self', '--file', body), /self.*send without/);
    await assert.rejects(cli('reply', 'self_tick', '--self', '--file', body), /self.*send without/);
    state.draft = 'human self draft'; await cli('send', '--self', '--file', body, '--id', 'self_draft'); assert.equal(last().state, 'deferred'); assert.equal(state.draft, 'human self draft');
    state.draft = ''; delete state.screenKind; state.submitted = [];
    await cli('send', 'target', '--file', body, '--id', 'first'); assert.equal(last().state, 'submitted');
    await cli('send', 'target', '--file', body, '--id', 'first'); assert.equal(last().duplicate, true); assert.equal(state.submitted.length, 1);
    fs.writeFileSync(body, 'different'); await assert.rejects(cli('send', 'target', '--file', body, '--id', 'first'), /conflicts/);
    state.draft = 'human draft'; await cli('send', 'target', '--file', body, '--id', 'draft'); assert.equal(last().state, 'deferred'); assert.equal(state.draft, 'human draft');
    state.draft = ''; state.race = true; await cli('send', 'target', '--file', body, '--id', 'race'); assert.equal(last().state, 'typed_unsubmitted'); assert.equal(state.submitted.length, 1);
    await assert.rejects(cli('send', '--retry', 'race'), /only own deferred/);
    state.draft = ''; state.race = false; state.width = 10; await cli('send', 'target', '--file', body, '--id', 'narrow'); assert.equal(last().state, 'deferred');
    state.width = 80; await cli('send', '--retry', 'narrow'); assert.equal(last().state, 'submitted');
    await Promise.all([cli('send', 'target', '--file', body, '--id', 'parallel1'), cli('send', 'target', '--file', body, '--id', 'parallel2')]);
    await cli('status', 'parallel2'); assert.equal(last().state, 'deferred');
    // Rebinding a recipient must not strand a retried message in stored.
    await cli('register', 'target', '--kind', 'claude', '--session', '33333333-3333-4333-8333-333333333333', '--pane', '%2', '--socket', '/test', '--pid', '42', '--replace');
    await cli('send', '--retry', 'parallel2'); assert.equal(last().state, 'deferred');
    await cli('send', '--retry', 'parallel2'); assert.equal(last().state, 'deferred');
    await cli('register', 'target', '--kind', 'claude', '--session', sid2, '--pane', '%2', '--socket', '/test', '--pid', '42', '--replace');
    env.CLAUDE_CODE_SESSION_ID = sid2; // stale inherited Claude ID must not override nearest Codex.
    await cli('status', 'first'); assert.equal(last().sender, 'codex:' + sid);
    state.agentKind = 'claude'; // nearest Claude must win even when Codex env is inherited.
    await assert.rejects(cli('status', 'first'), /caller pane differs/);
    state.agentKind = 'codex';
    await assert.rejects(cli('read', 'first'), /not addressed/);
    delete env.CODEX_THREAD_ID; env.CLAUDE_CODE_SESSION_ID = sid2; env.TMUX_PANE = '%2'; state.agentKind = 'claude';
    await cli('read', 'first'); assert.equal(last().body, 'peer body'); assert.equal(last().state, 'read');
    // Reply persistence is distinct from delivery; target Codex screen is deliberately unrecognized.
    await cli('reply', 'first', '--file', body, '--id', 'answer'); assert.equal(last().state, 'deferred');
    await cli('status', 'first'); assert.equal(last().state, 'replied');
    state.mode = 1; await cli('send', 'sender', '--file', body, '--id', 'copy'); assert.equal(last().state, 'deferred');
    state.mode = 0; state.panePid = process.pid + 100000; await cli('send', 'sender', '--file', body, '--id', 'stale'); assert.equal(last().state, 'deferred');
  } finally { fs.rmSync(root, {recursive: true}); }
});

test('send-only peers ask registered agents but never receive', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'agent-msg-test-'));
  const sid = '11111111-1111-4111-8111-111111111111';
  const env = {AGENT_MSG_HOME: root, CLAUDE_CODE_SESSION_ID: sid, TMUX_PANE: '%1'};
  const state = {draft: '', width: 80, mode: 0, panePid: 42, race: false, submitted: [], agentKind: 'claude'};
  const {cli, last} = fixture(env, state);
  const body = path.join(root, 'body'); fs.writeFileSync(body, 'question');
  const peer = 'cursor-review-0f0e0d0c-1111-2222-3333-444455556666';
  try {
    await cli('register', 'caller', '--socket', '/test', '--pid', '42');
    await cli('whoami'); assert.equal(last().name, 'caller');
    // A backend is known by its pane process, not by an agent session ID.
    await cli('register', peer, '--send-only', '--pane', '%3', '--socket', '/test');
    assert.equal(last().identity, 'send-only:' + peer);
    // Any agent under that pane, including ones agent-msg cannot recognize, sends as the peer.
    delete env.CLAUDE_CODE_SESSION_ID; state.agentKind = 'cursor-agent';
    await cli('whoami'); assert.equal(last().name, peer);
    await cli('send', 'caller', '--file', body, '--id', 'q1'); assert.equal(last().state, 'submitted');
    env.CLAUDE_CODE_SESSION_ID = sid; state.agentKind = 'claude';
    await cli('read', 'q1'); assert.equal(last().sender_name, peer); assert.equal(last().body, 'question');
    // Answers go through the channel that started the peer, never agent-msg.
    await assert.rejects(cli('reply', 'q1', '--file', body, '--id', 'a1'), /send-only/);
    await assert.rejects(cli('send', peer, '--file', body, '--id', 'a2'), /send-only/);
    await assert.rejects(cli('unregister', 'caller'), /only send-only/);
    // Another pane cannot take a peer's name without --replace.
    await assert.rejects(cli('register', peer, '--send-only', '--pane', '%4', '--socket', '/test'), /--replace/);
    // A late cleanup for an earlier pane must not remove the current registration.
    await cli('unregister', peer, '--pane', '%9'); assert.equal(last().removed, false);
    await cli('unregister', peer, '--pane', '%3'); assert.equal(last().removed, true);
    await cli('register', peer, '--send-only', '--pane', '%3', '--socket', '/test');
    // A pane respawned within the same second keeps its start string but not its PID.
    state.panePid = 43;
    await assert.rejects(cli('register', peer, '--send-only', '--pane', '%3', '--socket', '/test'), /--replace/);
    state.panePid = 42;
    // The same pane number on another server, or after a restart, is a different pane.
    await cli('unregister', peer, '--pane', '%3', '--pid', '43'); assert.equal(last().removed, false);
    await cli('unregister', peer, '--pane', '%3', '--pid', '42'); assert.equal(last().removed, true);
    await cli('register', peer, '--send-only', '--pane', '%3', '--socket', '/test');
    await cli('unregister', peer); assert.equal(last().removed, true);
    await cli('unregister', peer); assert.equal(last().removed, false);
    delete env.CLAUDE_CODE_SESSION_ID; state.agentKind = 'cursor-agent';
    await assert.rejects(cli('whoami'), /no parent Claude\/Codex agent|unregistered/);
    // A stale row for a reused PID must not hide the live registration of that PID.
    state.starts = {42: 'old-start'};
    await cli('register', 'stale-peer', '--send-only', '--pane', '%5', '--socket', '/test');
    state.starts = {42: 'new-start'};
    await cli('register', 'live-peer', '--send-only', '--pane', '%6', '--socket', '/test');
    await cli('whoami'); assert.equal(last().name, 'live-peer');
  } finally { fs.rmSync(root, {recursive: true}); }
});
