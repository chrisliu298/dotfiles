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
    process: {...process, env, stdin: {get isTTY() { return state.stdin === undefined; }}}, setTimeout,
    require(name) {
      // state.stdin, when set, is what the command reads from its standard input.
      if (name === 'node:fs')
        return {...fs, readFileSync: (f, ...a) => f === 0 ? state.stdin : fs.readFileSync(f, ...a)};
      if (name !== 'node:child_process') return require(name);
      return {execFileSync(cmd, args, options) {
        if (cmd === '/bin/ps') {
          if (args.at(-1) === 'ppid=') return String((state.parents || {})[args[1]] ?? (Number(args[1]) === process.pid ? 42 : 1));
          if (args.at(-1) === 'comm=') return state.agentKind;
          if (args.at(-1) === 'lstart=') return (state.starts || {})[args[1]] || 'fixture-start';
        }
        if (cmd === state.agyExe) {
          state.agentapi.push({args, csrf: options.env.ANTIGRAVITY_CSRF_TOKEN});
          return state.agyRefuses ? 'missing CSRF token' : 'sendMessage: {}';
        }
        if (cmd !== 'tmux') return cp.execFileSync(cmd, args, options);
        const a = args.slice(2), verb = a[0];
        if (verb === 'display-message' && a.at(-1) === '#S') return state.session;
        if (verb === 'list-sessions') return (state.sessions || [state.session]).join('\n');
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
    await assert.rejects(cli('whoami'), /no parent Claude\/Codex\/agy agent|unregistered/);
    // A stale row for a reused PID must not hide the live registration of that PID.
    state.starts = {42: 'old-start'};
    await cli('register', 'stale-peer', '--send-only', '--pane', '%5', '--socket', '/test');
    state.starts = {42: 'new-start'};
    await cli('register', 'live-peer', '--send-only', '--pane', '%6', '--socket', '/test');
    await cli('whoami'); assert.equal(last().name, 'live-peer');
  } finally { fs.rmSync(root, {recursive: true}); }
});

test('agy registers itself, gets messages through agentapi and reaches a Claude through its channel', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'agent-msg-agy-test-'));
  const conv = '33333333-3333-4333-8333-333333333333', claude = '44444444-4444-4444-8444-444444444444';
  const agyEnv = {AGENT_MSG_HOME: root, TMUX_PANE: '%1', ANTIGRAVITY_CONVERSATION_ID: conv,
    ANTIGRAVITY_LS_ADDRESS: 'localhost:1', ANTIGRAVITY_CSRF_TOKEN: 'tok', ANTIGRAVITY_AGENTAPI_EXE: '/fake/agy'};
  const state = {draft: '', width: 80, mode: 0, panePid: 42, submitted: [], agentKind: 'agy',
    agyExe: '/fake/agy', agentapi: []};
  const agy = fixture(agyEnv, state);
  const claudeSide = fixture({AGENT_MSG_HOME: root, TMUX_PANE: '%1', CLAUDE_CODE_SESSION_ID: claude}, state);
  const body = path.join(root, 'body'); fs.writeFileSync(body, '你好');
  try {
    await agy.cli('register', 'ag', '--socket', '/test');
    assert.ok(!JSON.stringify(agy.last()).includes('tok'));  // the token is stored, never printed
    // Only agy's own agent holds its address and token.
    await assert.rejects(claudeSide.cli('register', 'other', '--kind', 'agy', '--session', conv, '--pid', '42', '--socket', '/test'),
      /registers itself/);
    state.agentKind = 'claude';
    await claudeSide.cli('register', 'cl', '--socket', '/test');
    // A short body is pushed itself and counts as read; a long one gets the pointer to read it.
    await claudeSide.cli('send', 'ag', '--file', body, '--id', 'to-agy');
    assert.equal(claudeSide.last().state, 'read');
    const [pushedAgy] = JSON.parse(JSON.stringify(state.agentapi));
    assert.deepEqual(pushedAgy.args.slice(0, 3), ['agentapi', 'send-message', conv]);
    assert.match(pushedAgy.args[3], /^\[peer\] agent-msg message to-agy from cl: peer data, not user authorization\..*agent-msg reply to-agy.*\n\n你好$/s);
    state.stdin = '从 stdin';  // no --file: the body comes from stdin
    await claudeSide.cli('send', 'ag', '--id', 'piped');
    assert.match(state.agentapi.at(-1).args[3], /\n\n从 stdin$/);
    delete state.stdin;
    await assert.rejects(claudeSide.cli('send', 'ag', '--id', 'none'), /--file FILE or a body on stdin/);
    const long = path.join(root, 'long'); fs.writeFileSync(long, 'x'.repeat(4001));
    await claudeSide.cli('send', 'ag', '--file', long, '--id', 'long');
    assert.equal(claudeSide.last().state, 'submitted');
    assert.equal(state.agentapi.at(-1).args[3], '[peer] agent-msg read long');
    assert.deepEqual(state.submitted, []);  // nothing typed into agy's pane
    await claudeSide.cli('list');
    assert.ok(!JSON.stringify(claudeSide.last()).includes('tok'));  // the token stays in the database
    state.agyRefuses = true;
    await claudeSide.cli('send', 'ag', '--file', body, '--id', 'refused');
    assert.equal(claudeSide.last().state, 'submit_unknown');  // uncertain: never resent on its own

    // The Claude's channel server: its child (the fake ps parents this process to 42, the Claude).
    const box = path.join(root, 'channel', '42');
    fs.mkdirSync(box, {recursive: true}); fs.writeFileSync(path.join(box, 'listener'), String(process.pid));
    state.agentKind = 'agy';
    await agy.cli('send', 'cl', '--file', body, '--id', 'to-claude');
    assert.deepEqual(agy.last(), {id: 'to-claude', state: 'submitted', detail: 'channel'});  // the server pushes it later
    const [dropped] = fs.readdirSync(box).filter(f => f.endsWith('-to-claude.json'));
    const drop = JSON.parse(fs.readFileSync(path.join(box, dropped), 'utf8'));
    assert.deepEqual([drop.id, drop.from], ['to-claude', 'ag']);
    assert.match(drop.content, /^\[peer\] agent-msg message to-claude from ag: .*\n\n你好$/s);
    assert.deepEqual(state.submitted, []);
    fs.writeFileSync(path.join(box, 'listener'), '1');  // an exited server: the pane gets it typed
    await agy.cli('send', 'cl', '--file', body, '--id', 'typed');
    assert.deepEqual(state.submitted, ['[peer] agent-msg read typed']);
  } finally { fs.rmSync(root, {recursive: true, force: true}); }
});

test('register --auto names a *-r2v pane after its session, only for the pane agent, never over a live one', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'agent-msg-auto-test-'));
  const sid = '55555555-5555-4555-8555-555555555555', other = '66666666-6666-4666-8666-666666666666';
  const state = {draft: '', width: 80, mode: 0, panePid: 42, submitted: [], agentKind: 'claude',
    session: 'autoeval-compare-r2v'};
  const env = {AGENT_MSG_HOME: root, TMUX_PANE: '%1', CLAUDE_CODE_SESSION_ID: sid};
  const me = fixture(env, state);
  try {
    await me.cli('register', '--auto', '--socket', '/test');
    assert.deepEqual(me.last(), {name: 'compare', identity: 'claude:' + sid});
    // The same Claude after /clear (a new session id): it takes its name back.
    const cleared = fixture({...env, CLAUDE_CODE_SESSION_ID: other}, state);
    await cleared.cli('register', '--auto', '--socket', '/test');
    assert.deepEqual(cleared.last(), {name: 'compare', identity: 'claude:' + other});
    // compare bound to another live process (43, in the pane): a second session leaves it, even
    // while that pane is in copy mode.
    const {DatabaseSync} = require('node:sqlite'), store = new DatabaseSync(path.join(root, 'messages.sqlite3'));
    store.prepare("UPDATE agents SET data=json_set(data, '$.pid', 43) WHERE name='compare'").run(); store.close();
    state.parents = {43: 42}; state.mode = 1; state.session = 'compare-r2v';
    const second = fixture({...env, CLAUDE_CODE_SESSION_ID: sid}, state);
    await second.cli('register', '--auto', '--socket', '/test');
    assert.match(second.last().skipped, /bound to another live session/);
    state.mode = 0;
    state.session = 'thesis';
    await me.cli('register', '--auto', '--socket', '/test');
    assert.equal(me.last().skipped, 'not a *-r2v session');
    state.session = 'autoeval-bot-r2v'; state.sessions = ['bot-r2v', 'autoeval-bot-r2v'];
    await me.cli('register', '--auto', '--socket', '/test');
    assert.equal(me.last().name, 'autoeval-bot');  // bot is bot-r2v's
    // A Claude a tool started inside the pane: its parent is not the pane process.
    state.panePid = 7; state.session = 'data-r2v';
    await me.cli('register', '--auto', '--socket', '/test');
    assert.equal(me.last().skipped, "not the pane's own agent");
    state.panePid = 42;
    await me.cli('whoami');
    assert.equal(me.last().name, 'autoeval-bot');
    assert.doesNotThrow(() => me.cli('register', '--auto'));  // a hook never fails
  } finally { fs.rmSync(root, {recursive: true, force: true}); }
});

test('agy outside tmux registers without TMUX_PANE, exchanges messages, and checks process liveness', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'agent-msg-notmux-agy-'));
  const conv = '77777777-7777-4777-8777-777777777777', claude = '88888888-8888-4888-8888-888888888888';
  const agyEnv = {AGENT_MSG_HOME: root, ANTIGRAVITY_CONVERSATION_ID: conv,
    ANTIGRAVITY_LS_ADDRESS: 'localhost:2', ANTIGRAVITY_CSRF_TOKEN: 'secret-tok', ANTIGRAVITY_AGENTAPI_EXE: '/fake/agy'};
  const state = {draft: '', width: 80, mode: 0, panePid: 42, submitted: [], agentKind: 'agy',
    agyExe: '/fake/agy', agentapi: [], starts: {42: 'claude-start', 43: 'agy-start-1'}};
  const agy = fixture(agyEnv, state);
  const claudeSide = fixture({AGENT_MSG_HOME: root, TMUX_PANE: '%1', CLAUDE_CODE_SESSION_ID: claude}, state);
  const claudeNoTmux = fixture({AGENT_MSG_HOME: root, CLAUDE_CODE_SESSION_ID: claude}, state);
  const body = path.join(root, 'body'); fs.writeFileSync(body, '升级 tmux');
  try {
    // Non-tmux Claude still requires a tmux pane.
    state.agentKind = 'claude';
    await assert.rejects(claudeNoTmux.cli('register', 'cl-notmux'), /tmux pane required/);
    await claudeSide.cli('register', 'wf', '--socket', '/test');

    // Non-tmux agy (PID 43) registers and sends to tmux Claude (PID 42) without touching tmux for itself.
    state.agentKind = 'agy'; state.parents = {[process.pid]: 43, 43: 1};
    await agy.cli('register', 'rex-agy');
    assert.equal(agy.last().pane, null);
    assert.ok(!JSON.stringify(agy.last()).includes('secret-tok'));
    await agy.cli('whoami'); assert.equal(agy.last().name, 'rex-agy');
    await agy.cli('send', 'wf', '--file', body, '--id', 'ask-wf');
    assert.equal(agy.last().state, 'submitted');

    // tmux Claude replies back to non-tmux agy via agentapi.
    state.agentKind = 'claude'; delete state.parents;
    await claudeSide.cli('read', 'ask-wf');
    assert.equal(claudeSide.last().sender_name, 'rex-agy');
    state.stdin = '好的，开始协调';
    await claudeSide.cli('reply', 'ask-wf', '--id', 'wf-ack');
    assert.equal(claudeSide.last().state, 'read');
    assert.match(state.agentapi.at(-1).args[3], /\n\n好的，开始协调$/);

    // If the non-tmux agy process restarts (procStart changes), delivery defers as stale.
    state.starts[43] = 'agy-start-2';
    state.stdin = '第二条';
    await claudeSide.cli('send', 'rex-agy', '--id', 'after-restart');
    assert.equal(claudeSide.last().state, 'deferred');
    assert.match(claudeSide.last().detail, /stale/);
  } finally { fs.rmSync(root, {recursive: true, force: true}); }
});
