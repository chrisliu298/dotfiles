const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const vm = require('node:vm');
const {EventEmitter} = require('node:events');
const {input, modelEffort} = require('./rex-claude');
const script = path.join(__dirname, 'rex-claude');
test('queued launches cannot survive rollback or supersede a newer launch', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'rex-launch-test-'));
  const metadata = path.join(root, 'metadata'); fs.mkdirSync(metadata);
  const state = path.join(root, 'state');
  const record = {role: 'test-r2v', sessionId: '11111111-2222-3333-4444-555555555555', cwd: root,
    model: 'claude-opus-5-5', effort: 'high', launchEffort: 'high', rexSession: 'session:test', handoff: path.join(root, 'handoff.md')};
  const src = path.join(root, 'register.json'); fs.writeFileSync(src, JSON.stringify(record));
  fs.writeFileSync(record.handoff, 'saved tasks');
  let spawnCount = 0, queued = 0, child;
  const env = {...process.env, REX_CLAUDE_STATE: state, REX_CLAUDE_SESSIONS: metadata, REX_SESSION: 'session:test', REX_BLOCK: 'block:test'};
  delete env.TMUX_PANE;
  const context = {module: {exports: {}}, __filename: script, console: {log() {}},
    process: {...process, env, stdout: {write() {}}}, setTimeout,
    require(name) {
      if (name !== 'node:child_process') return require(name);
      return {
        execFileSync(cmd, args) {
          if (cmd === 'rex') { queued++; return '{}'; }
          // No real process scan or Claude process can escape this fixture.
          if (cmd === '/bin/ps') return args[0] === '-p' ? 'test-start' : '';
          throw Error('unexpected command ' + cmd);
        },
        spawn() { spawnCount++; child = new EventEmitter(); child.pid = 12345; return child; }
      };
    }
  };
  vm.runInNewContext(fs.readFileSync(script, 'utf8') + '\nmodule.exports = {main};', context);
  const cli = (...args) => context.module.exports.main(args);
  const current = () => JSON.parse(fs.readFileSync(path.join(state, 'sessions/test-r2v.json')));
  try {
    await cli('register', src);
    await cli('start', record.role);
    const revoked = current().pendingLaunch;
    await assert.rejects(cli('start', record.role), /launch is pending/);
    assert.equal(queued, 1);
    await cli('rollback', record.role);
    await assert.rejects(cli('_run', record.role, revoked), /revoked or superseded/);
    assert.equal(spawnCount, 0); assert.equal(current().transport, 'tmux');
    await cli('start', record.role);
    const valid = current().pendingLaunch;
    assert.notEqual(valid, revoked);
    await assert.rejects(cli('_run', record.role, revoked), /revoked or superseded/);
    const running = cli('_run', record.role, valid);
    assert.equal(spawnCount, 1);
    await assert.rejects(cli('rollback', record.role), /native lock exists/);
    child.emit('spawn');
    child.emit('exit', 0, null);
    await running;
    await cli('rollback', record.role);
    assert.equal(current().transport, 'tmux');
  } finally { fs.rmSync(root, {recursive: true}); }
});
test('an empty first draft line does not hide a multiline user draft', () => {
  assert.equal(input('❯ old\n────\n❯ \n  用户未发送的第二行\n────\nstatus'), '\n  用户未发送的第二行');
  assert.equal(input('❯ \n────\nOpus 5.5 high ·'), '');
  assert.throws(() => input('❯ draft without lower border'));
});
test('save uses the current fallback effort, independently of launch policy', () => {
  assert.deepEqual(modelEffort('Opus 5.5 medium ·\nOpus 5 high ·'), {model: 'claude-opus-5', effort: 'high'});
  assert.throws(() => modelEffort('model not visible'));
});
test('a live writer prevents start and rollback before Rex is invoked', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'rex-claude-test-'));
  try {
    const metaDir = path.join(root, 'metadata'); fs.mkdirSync(metaDir);
    const record = {role: 'test-r2v', sessionId: '11111111-2222-3333-4444-555555555555', cwd: root,
      model: 'claude-opus-5', effort: 'high', launchEffort: 'medium', rexSession: 'session:test', handoff: path.join(root, 'handoff.md')};
    const src = path.join(root, 'register.json'); fs.writeFileSync(src, JSON.stringify(record));
    fs.writeFileSync(record.handoff, 'saved tasks');
    const env = {...process.env, REX_CLAUDE_STATE: path.join(root, 'state'), REX_CLAUDE_SESSIONS: metaDir};
    const cli = (...args) => spawnSync(process.execPath, [script, ...args], {env, encoding: 'utf8'});
    assert.equal(cli('register', src).status, 0);
    const procStart = spawnSync('/bin/ps', ['-p', String(process.pid), '-o', 'lstart='], {env: {...process.env, TZ: 'UTC', LC_ALL: 'C'}, encoding: 'utf8'}).stdout.trim();
    fs.writeFileSync(path.join(metaDir, 'writer.json'), JSON.stringify({pid: process.pid, procStart, sessionId: record.sessionId}));
    for (const verb of ['start', 'restart', 'rollback']) {
      const result = cli(verb, record.role);
      assert.equal(result.status, 1); assert.match(result.stderr, /still running/);
    }
    assert.equal(cli('register', src).status, 1);
    const saved = JSON.parse(fs.readFileSync(path.join(env.REX_CLAUDE_STATE, 'sessions/test-r2v.json')));
    assert.equal(saved.effort, 'high'); assert.equal(saved.launchEffort, 'medium');
    assert.equal(saved.transport, 'prepared');
  } finally { fs.rmSync(root, {recursive: true}); }
});
test('repin transport prefers inner tmux and preserves multiline drafts', () => {
  const source = fs.readFileSync(path.join(__dirname, '../agents/claude/opus-repin.sh'), 'utf8');
  const declarations = source.slice(source.indexOf('terminal_pane()'), source.indexOf('fresh()'));
  const result = spawnSync('bash', ['-c', declarations + `
TMUX_PANE=%9 REX_BLOCK=block:test
[[ $(terminal_pane) == %9 ]] || exit 1
unset TMUX_PANE
[[ $(terminal_pane) == block:test ]] || exit 2
pane_capture() { printf '❯ \\n  user draft\\n────\\n'; }
[[ -n $(input_line block:test) ]] || exit 3
pane_capture() { printf '❯ \\n────\\n'; }
[[ -z $(input_line block:test) ]] || exit 4
pane_capture() { printf '❯ 1. Yes, switch to high\\nold dialog\\n❯ user draft\\n────\\n'; }
pane_key() { exit 5; }
answer_effort_dialog block:test high
pane_capture() { printf '❯ explain this prompt:\\n   ❯ 1. Yes, switch to high\\n────\\n'; }
answer_effort_dialog block:test high
pane_capture() { printf 'Change effort level?\\n   ❯ 1. Yes, switch to high\\n'; }
[[ $(effort_dialog block:test) == high ]] || exit 6
`], {encoding: 'utf8'});
  assert.equal(result.status, 0, result.stderr);
});
test('repin gets the original override instead of resume CLI effort', () => {
  const source = fs.readFileSync(path.join(__dirname, '../agents/claude/opus-repin.sh'), 'utf8');
  const declaration = source.slice(source.indexOf('launch_effort()'), source.indexOf('# The level for the fallback:'));
  const result = spawnSync('bash', ['-c', declaration + `
CLAUDE_CODE_EFFORT_LEVEL=high OPUS_REPIN_LAUNCH_EFFORT=medium
[[ $(launch_effort) == medium ]] || exit 1
OPUS_REPIN_LAUNCH_EFFORT=settings
[[ -z $(launch_effort) ]] || exit 2
`], {encoding: 'utf8'});
  assert.equal(result.status, 0, result.stderr);
});
