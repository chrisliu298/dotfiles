// ChatGPT Pro backend for agent-team, driven through the gpt-pro skill's wrapper.
// It speaks the session runner's action interface, but needs no tmux: the relay's
// detached worker owns each run, and the session handle embeds its run id.
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { accessSync, constants, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const skill = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const prefix = 'P-review-';
const defaultWait = 7200;
const registry = join(process.env.XDG_STATE_HOME || join(homedir(), '.local/state'), 'agent-team/pro');

function fail(message, code = 1) {
  process.stderr.write(`agent-team (P): ${message}\n`);
  process.exit(code);
}
function executable(path) {
  try { accessSync(path, constants.X_OK); return statSync(path).isFile(); }
  catch { return false; }
}
// GPT_PRO_BIN, then PATH, then the gpt-pro skill installed beside this one.
function gptPro() {
  const named = process.env.GPT_PRO_BIN;
  if (named) return named.includes('/') && executable(named) ? resolve(named) : null;
  const found = (process.env.PATH || '').split(':').map(dir => join(dir || '.', 'gpt-pro')).find(executable);
  if (found) return found;
  const sibling = resolve(skill, '../gpt-pro/scripts/gpt-pro');
  return executable(sibling) ? sibling : null;
}

function call(args, input = '') {
  const cli = gptPro();
  if (!cli) fail('gpt-pro is not installed; install the gpt-pro skill or put gpt-pro on PATH', 127);
  const result = spawnSync(cli, args, { input, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
  if (result.error) fail(result.error.message);
  return { stdout: result.stdout || '', stderr: result.stderr || '', code: result.status ?? 1 };
}
// Relay wrapper diagnostics under the codename, pointing every recovery or retry command at
// this helper. Resending identical text through `send` reuses its content-derived message id.
function relay(stderr) {
  process.stderr.write(stderr
    .replace(/gpt-pro --send ([A-Za-z0-9-]+) --message-id [A-Za-z0-9-]+/g, (_, id) => `agent-team send ${prefix}${id}`)
    .replace(/gpt-pro --run-id ([A-Za-z0-9-]+)/g, (_, id) => `agent-team wait ${prefix}${id}`)
    .replace(/^gpt-pro:/gm, 'agent-team (P):'));
}
function fileArgs(files) { return files.flatMap(file => ['-f', file]); }
function runId(session) { return session.slice(prefix.length); }
function readStdin() {
  try { return readFileSync(0, 'utf8'); }
  catch { return ''; }
}

const [action = 'start', ...rest] = process.argv.slice(2);
const files = [], sessions = [];
let timeout;
while (rest.length) {
  const option = rest.shift();
  if (option === '--file' && ['start', '--once'].includes(action)) files.push(rest.shift());
  else if (option === '--timeout') timeout = Number(rest.shift());
  else if (option.startsWith(prefix)) sessions.push(option);
  else fail(`unsupported option or argument: ${option}`, 2);
}
const session = sessions[0];
if (['send', 'wait', 'capture', 'status', 'interrupt', 'stop'].includes(action) && sessions.length !== 1) fail('specify one P session', 2);

if (action === '--once') {
  // The wrapper's own deadline exits 124 with a recovery hint while the run keeps going.
  const result = call(['--max-wait', String(timeout || defaultWait), ...fileArgs(files)], readStdin());
  process.stdout.write(result.stdout);
  relay(result.stderr);
  process.exit(result.code);
} else if (action === 'start') {
  // A one-second wait submits the run and returns 124 while the detached worker carries on;
  // 255 leaves submission unknown, which a later wait resolves by reattaching.
  const result = call(['--max-wait', '1', ...fileArgs(files)], readStdin());
  const id = /run_id=([A-Za-z0-9-]+)/.exec(result.stderr)?.[1];
  if (!id || ![0, 124, 255].includes(result.code)) {
    relay(result.stderr);
    fail(`submission failed (exit ${result.code})`, result.code || 1);
  }
  mkdirSync(registry, { recursive: true });
  writeFileSync(join(registry, prefix + id), '');
  process.stdout.write(prefix + id + '\n');
} else if (action === 'wait') {
  // Reattaching waits on the live worker, or restores collection if it died; it never resends.
  const result = call(['--run-id', runId(session), '--max-wait', String(timeout || defaultWait)]);
  process.stdout.write(result.stdout);
  relay(result.stderr);
  process.exit(result.code);
} else if (action === 'send') {
  const message = readStdin();
  if (!message.trim()) fail('message is empty', 2);
  // A content-derived id makes a retried supplement idempotent instead of sending it twice.
  const id = 'agent-team-' + createHash('sha256').update(runId(session) + '\0' + message).digest('hex').slice(0, 24);
  const result = call(['--send', runId(session), '--message-id', id], message);
  if (result.code === 2 && result.stderr.includes('run_finished')) {
    fail('this P conversation has finished and accepts no follow-up; start a new task that includes ' +
      'its answer and the new question', 2);
  }
  if (result.code === 2 && result.stderr.includes('run_not_ready')) {
    fail('P has not started answering yet; resend the same supplement shortly (its message id is ' +
      'stable, so it is never delivered twice)', 2);
  }
  relay(result.stderr);
  process.exit(result.code);
} else if (['status', 'capture'].includes(action)) {
  const result = call(['--run-id', runId(session), '--max-wait', '1']);
  const state = { 0: 'finished', 124: 'running', 5: 'stopped' }[result.code] || `failed exit_code=${result.code}`;
  process.stdout.write(`${session} state=${state}\n`);
  if (action === 'capture') {
    // The local engine's stage trace shows queueing and progress; a remote engine has none here.
    const trace = join(homedir(), '.gpt-pro/runs', runId(session), 'worker.stderr');
    try { process.stdout.write(readFileSync(trace, 'utf8').trimEnd().split('\n').slice(-5).join('\n') + '\n'); }
    catch { /* no local trace */ }
  }
} else if (['interrupt', 'stop'].includes(action)) {
  // Stop dequeues an unsent run or clicks Stop on the live turn; Pro cannot resume either way.
  const result = call(['--stop', runId(session)]);
  relay(result.stderr);
  if (action === 'stop' && [0, 4].includes(result.code)) rmSync(join(registry, session), { force: true });
  process.exit(result.code === 4 && action === 'stop' ? 0 : result.code);
} else if (action === 'list') {
  let names = [];
  try { names = readdirSync(registry).filter(name => name.startsWith(prefix)); }
  catch { /* no sessions yet */ }
  if (names.length) process.stdout.write(names.join('\n') + '\n');
} else fail(`unknown action: ${action}`, 2);
