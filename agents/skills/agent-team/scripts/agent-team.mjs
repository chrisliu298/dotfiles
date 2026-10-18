import { spawn, spawnSync } from 'node:child_process';
import { accessSync, constants, readFileSync, statSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const skill = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const runner = resolve(skill, 'scripts/review-subagent');
// Pro runs live in the gpt-pro relay rather than tmux, so a separate adapter drives them.
const proSession = resolve(skill, 'scripts/pro-session.mjs');
const names = ['claude', 'gpt', 'gemini', 'muse', 'ds', 'pro'];
const args = process.argv.slice(2);

function usage(message) {
  if (message) process.stderr.write(`agent-team: ${message}\n`);
  process.stderr.write('usage: agent-team [start] --backend NAME[=PROMPT] [--backend ...] [--file PATH ...] [< prompt.md]\n' +
    '       agent-team --once --backend NAME[=PROMPT] [--backend ...] [--file PATH ...] [--output-format text|json] [--timeout SECONDS] [< prompt.md]\n' +
    '       agent-team send SESSION [SESSION ...] < message.md\n' +
    '       agent-team wait SESSION [SESSION ...] [--timeout SECONDS]\n' +
    '       agent-team capture|status|interrupt|stop SESSION [SESSION ...]\n' +
    '       agent-team list | backends\n' +
    '       NAME is claude, gpt, gemini, muse, ds, or pro; each at most once per call. NAME=PROMPT gives that\n' +
    '       backend its own prompt file instead of stdin. --file attaches a file to Pro and lists its\n' +
    '       path for the others. Models and high are fixed.\n');
  process.exit(2);
}

if (process.env.CODEX_REVIEW_SUBAGENT_ACTIVE === '1') {
  process.stderr.write('agent-team: recursive helper delegation is blocked\n');
  process.exit(126);
}
const action = !args.length || args[0].startsWith('-') && args[0] !== '--once' ? 'start' : args.shift();
const selections = [], sessions = [], files = [];
let format = 'text', timeout;
while (args.length) {
  const option = args.shift();
  if (option === '--backend' && ['start', '--once'].includes(action)) {
    const [backend, ...file] = (args.shift() || '').split('=');
    if (backend === 'cursor') usage('backend cursor was renamed to gemini (Cursor Agent on Gemini); use --backend gemini');
    if (!names.includes(backend)) usage('backend must be claude, gpt, gemini, muse, ds, or pro');
    if (selections.some(item => item.backend === backend)) usage(`each backend runs at most once per call: ${backend}`);
    const selection = { backend };
    if (file.length) {
      // A per-backend prompt file lets one call dispatch distinct assignments.
      const path = file.join('=');
      try { selection.prompt = readFileSync(resolve(path), 'utf8'); }
      catch (error) { usage(`could not read prompt file for ${backend}: ${path || '(empty path)'}: ${error.code || error.message}`); }
      if (!selection.prompt.trim()) usage(`prompt file for ${backend} is empty: ${path}`);
    }
    selections.push(selection);
  } else if (option === '--file' && ['start', '--once'].includes(action)) {
    const path = args.shift() || '';
    let stats;
    try { stats = statSync(path); accessSync(path, constants.R_OK); }
    catch (error) { usage(`could not read --file ${path || '(empty path)'}: ${error.code || error.message}`); }
    if (!stats.isFile()) usage(`--file must name a regular file: ${path}`);
    if (!files.includes(resolve(path))) files.push(resolve(path));
  } else if (option === '--output-format' && action === '--once') {
    format = args.shift();
    if (!['text', 'json'].includes(format)) usage('output format must be text or json');
  } else if (option === '--timeout' && ['wait', '--once'].includes(action)) {
    timeout = args.shift();
    if (!/^[1-9][0-9]*$/.test(timeout || '') || !Number.isSafeInteger(Number(timeout))) usage('timeout must be a positive integer');
  } else if (!option.startsWith('-') && ['send', 'wait', 'capture', 'status', 'interrupt', 'stop'].includes(action)) {
    const match = /^(claude|gpt|gemini|muse|ds|pro)-review-[a-zA-Z0-9-]+$/.exec(option);
    if (!match) usage(`invalid review session: ${option}`);
    if (sessions.some(item => item.session === option)) usage('the same session must not be targeted twice');
    sessions.push({ backend: match[1], session: option });
  } else usage(`unsupported option or argument: ${option}`);
}
if (['start', '--once'].includes(action) && !selections.length) usage('specify at least one backend; there is no automatic fallback');
if (['send', 'wait', 'capture', 'status', 'interrupt', 'stop'].includes(action) && !sessions.length) usage('specify a review session');
if (!['start', '--once', 'send', 'wait', 'capture', 'status', 'interrupt', 'stop', 'list', 'backends'].includes(action)) usage('unknown action');

function executable(path) {
  try { accessSync(path, constants.X_OK); return statSync(path).isFile(); }
  catch { return false; }
}
function command(name) {
  if (name.includes('/')) return executable(name) ? resolve(name) : null;
  return (process.env.PATH || '').split(':').map(dir => join(dir || '.', name)).find(executable) || null;
}
function availability(backend) {
  if (backend === 'pro') {
    const named = process.env.GPT_PRO_BIN;
    if (named ? !(named.includes('/') && executable(named)) : !command('gpt-pro') && !executable(resolve(skill, '../gpt-pro/scripts/gpt-pro'))) {
      return 'gpt-pro is missing or not executable; install the gpt-pro skill';
    }
  } else if (backend === 'muse') {
    if (!command(process.env.MUSE_BIN || 'muse')) return 'muse is missing or not executable';
  } else if (backend === 'gemini') {
    if (!command(process.env.CURSOR_AGENT_BIN || 'cursor-agent')) return 'cursor-agent is missing or not executable';
    if (!command('jq')) return 'jq is required for Cursor';
  } else if (backend === 'gpt') {
    const cli = join(homedir(), '.local/bin/codex');
    if (!executable(cli)) return 'managed Codex CLI is missing; run ./dotfiles.sh';
    const version = spawnSync(cli, ['--version'], { encoding: 'utf8', timeout: 5000 });
    const match = /^codex-cli (\d+)\.(\d+)\.(\d+)/.exec(version.stdout?.trim() || '');
    if (version.status !== 0 || !match) return 'could not verify the managed Codex CLI version';
    const [major, minor, patch] = match.slice(1).map(Number);
    if (major === 0 && (minor < 159 || minor === 159 && patch < 2)) return 'Codex CLI 0.159.2+ is required';
  } else {
    // Claude and DeepSeek both run Claude Code through the user's shell launchers.
    const [label, launcher] = backend === 'ds' ? ['DeepSeek', 'ds'] : ['Claude', 'c'];
    const shell = command('zsh');
    if (!shell) return `zsh is required for the ${label} launcher`;
    const check = spawnSync(shell, ['-c', `source "$HOME/.functions" >/dev/null || exit 127; (( $+functions[${launcher}] ))`],
      { encoding: 'utf8', timeout: 5000 });
    if (check.status !== 0) return `the configured ${label} ${launcher} launcher is unavailable`;
    // The launcher's zsh reads the key from ~/.zshenv.local, which the caller may not have loaded.
    if (backend === 'ds' && spawnSync(shell, ['-c', '[[ -n "${DEEPSEEK_API_KEY:-}" ]]'], { timeout: 5000 }).status !== 0) {
      return 'DEEPSEEK_API_KEY is not set (see ~/.zshenv.local)';
    }
  }
  return null;
}
function probe(backend) {
  try { return availability(backend); }
  catch (error) { return `backend configuration could not be read: ${error.message}`; }
}
const activeOnce = new Set();
let interrupted = 0, readingInput = false;
if (action === '--once') {
  for (const [signal, code] of [['SIGINT', 130], ['SIGTERM', 143]]) {
    process.on(signal, () => {
      interrupted = code;
      for (const cancel of activeOnce) cancel(code, `interrupted by ${signal}`);
      if (readingInput) process.stdin.destroy(new Error(`interrupted by ${signal}`));
    });
  }
}
function run(item, commandArgs, input = '', options = {}) {
  return new Promise(resolveResult => {
    let stdout = '', stderr = '';
    const bounded = commandArgs[0] === '--once', pro = item.backend === 'pro';
    // A Pro answer can take far longer than the tmux backends' default hour.
    const seconds = Number(timeout || (pro ? 7200 : 3600));
    let cancelled = 0, timer, killTimer;
    // Pro bounds its own one-shot wait; the outer deadline is only a backstop.
    if (pro && bounded) commandArgs = [...commandArgs, '--timeout', String(seconds)];
    // Each one-shot gets an owned process group so timeout also stops descendants.
    const child = pro ? spawn(process.execPath, [proSession, ...commandArgs], { stdio: ['pipe', 'pipe', 'pipe'], detached: bounded, ...options })
      : spawn(runner, [item.backend, ...commandArgs], { stdio: ['pipe', 'pipe', 'pipe'], detached: bounded, ...options });
    function signalGroup(signal) {
      if (!child.pid) return;
      try { process.kill(-child.pid, signal); }
      catch (error) { if (error.code !== 'ESRCH') stderr += `could not stop process group: ${error.message}\n`; }
    }
    function cancel(code, reason) {
      if (cancelled) return;
      cancelled = code;
      stderr += reason + '\n';
      signalGroup('SIGTERM');
      killTimer = setTimeout(() => signalGroup('SIGKILL'), 500);
    }
    if (bounded) {
      activeOnce.add(cancel);
      // Use a deadline rather than an overflowing Node timer for large valid values.
      const deadline = performance.now() + (seconds + (pro ? 60 : 0)) * 1000;
      timer = setInterval(() => {
        if (performance.now() >= deadline) cancel(124, `one-shot timed out after ${seconds} seconds`);
      }, Math.min(seconds * 1000, 1000));
    }
    child.stdout.setEncoding('utf8');
    child.stderr.setEncoding('utf8');
    child.stdout.on('data', chunk => { stdout += chunk; });
    child.stderr.on('data', chunk => { stderr += chunk; });
    child.stdin.on('error', error => { if (error.code !== 'EPIPE') stderr += error.message + '\n'; });
    child.on('error', error => { stderr += error.message + '\n'; });
    child.on('close', code => {
      clearInterval(timer);
      clearTimeout(killTimer);
      activeOnce.delete(cancel);
      if (cancelled) signalGroup('SIGKILL');
      let exit_code = cancelled || (code ?? 1);
      if (exit_code === 0 && ['--once', 'wait'].includes(commandArgs[0]) && !stdout.trim()) {
        stderr += 'backend returned an empty reply\n';
        exit_code = 1;
      }
      resolveResult({ ...item, stdout, stderr, exit_code });
    });
    child.stdin.end(input);
  });
}
function diagnose(results) {
  for (const item of results) {
    if (item.stderr) process.stderr.write(`[${item.backend}${item.session ? ` ${item.session}` : ''}] ${item.stderr}`);
  }
}
function exitCode(results) {
  const failed = results.filter(item => item.exit_code !== 0);
  return !failed.length ? 0 : failed.every(item => item.exit_code === 124) ? 124 : 1;
}
function json(value) { process.stdout.write(JSON.stringify(value) + '\n'); }
function result(item) {
  return { backend: item.backend, ...(item.session ? { session: item.session } : {}),
    result: item.stdout.replace(/\n$/, ''), exit_code: item.exit_code, is_error: item.exit_code !== 0,
    ...(item.stderr ? { diagnostics: item.stderr.trimEnd() } : {}) };
}

if (action === 'backends') {
  json({ backends: names.map(backend => { const reason = probe(backend); return { backend, available: !reason, ...(reason ? { reason } : {}) }; }) });
} else if (action === 'list') {
  const results = await Promise.all(names.map(backend => run({ backend }, ['list'])));
  diagnose(results);
  process.stdout.write(results.map(item => item.stdout).join(''));
  process.exitCode = exitCode(results);
} else {
  let input = '';
  if (action === 'send' || ['start', '--once'].includes(action) && selections.some(item => item.prompt === undefined)) {
    if (process.stdin.isTTY) usage('supply the assignment or message on stdin');
    process.stdin.setEncoding('utf8');
    readingInput = true;
    try { for await (const chunk of process.stdin) input += chunk; }
    catch (error) {
      if (interrupted) process.exit(interrupted);
      usage(`could not read stdin: ${error.message}`);
    }
    readingInput = false;
    if (interrupted) process.exit(interrupted);
    if (!input.trim()) usage('assignment or message is empty');
  }
  for (const item of selections) {
    item.prompt ??= input;
    // Pro inlines attached files itself; the other backends read them from disk.
    if (files.length && item.backend !== 'pro') item.prompt = item.prompt.replace(/\s*$/, '\n\nRead these files:\n') + files.map(path => `- ${path}\n`).join('');
  }
  if (action === 'start' && selections.some(item => Buffer.byteLength(item.prompt) > 131072)) usage('initial prompt exceeds 128 KiB; send further context later');
  if (['start', '--once'].includes(action)) {
    if (action === 'start' && selections.some(item => item.backend !== 'pro') && !command('tmux')) {
      process.stderr.write('agent-team: tmux is required\n');
      process.exit(127);
    }
    const checks = new Map();
    const results = await Promise.all(selections.map(item => {
      if (!checks.has(item.backend)) checks.set(item.backend, probe(item.backend));
      const reason = checks.get(item.backend);
      const extra = item.backend === 'pro' ? files.flatMap(path => ['--file', path]) : [];
      const task = reason ? Promise.resolve({ ...item, stdout: '', stderr: reason + '\n', exit_code: 1 }) : run(item, [action, ...extra], item.prompt);
      return task.then(outcome => {
        if (action === 'start' && outcome.exit_code === 0) {
          process.stderr.write(`[${item.backend}] started ${outcome.stdout.trim()}\n`);
        } else if (action === '--once') {
          // Recover completed replies from stderr if the caller ends before the manifest.
          process.stderr.write(JSON.stringify({ event: 'completed', ...result(outcome) }) + '\n');
        }
        return outcome;
      });
    }));
    diagnose(results);
    if (action === 'start') {
      const started = [], errors = [];
      for (const item of results) {
        const session = item.stdout.trim();
        if (new RegExp(`^${item.backend}-review-[a-zA-Z0-9-]+$`).test(session)) {
          started.push({ backend: item.backend, session });
          if (item.exit_code !== 0) errors.push({ backend: item.backend,
            session, exit_code: item.exit_code, error: item.stderr.trimEnd() || 'startup failed after returning a session handle' });
        } else errors.push({ backend: item.backend, exit_code: item.exit_code || 1,
          error: item.stderr.trimEnd() || 'startup returned no valid session handle' });
      }
      // Partial startup preserves successful handles so callers can collect and stop them.
      if (results.length === 1 && !errors.length) process.stdout.write(started[0].session + '\n');
      else json({ sessions: started, errors, is_error: errors.length > 0 });
      process.exitCode = errors.length ? 1 : 0;
    } else {
      if (results.length === 1) {
        if (format === 'json') json({ result: results[0].stdout.replace(/\n$/, ''), exit_code: results[0].exit_code, is_error: results[0].exit_code !== 0 });
        else process.stdout.write(results[0].stdout);
      } else json({ results: results.map(result), is_error: results.some(item => item.exit_code !== 0) });
      process.exitCode = interrupted || exitCode(results);
    }
  } else {
    const results = await Promise.all(sessions.map(item => run(item,
      [action, item.session, ...(timeout ? ['--timeout', timeout] : [])], input)));
    diagnose(results);
    if (action === 'send') {
      const messages = results.map(item => ({ ...result(item), delivery: item.exit_code === 0 ?
        ['gemini', 'pro'].includes(item.backend) ? 'confirmed' : 'submitted' : item.exit_code === 124 ? 'unconfirmed' : 'failed' }));
      json(results.length === 1 ? messages[0] : { results: messages, is_error: results.some(item => item.exit_code !== 0) });
    } else if (results.length === 1) process.stdout.write(results[0].stdout);
    else json({ results: results.map(result), is_error: results.some(item => item.exit_code !== 0) });
    process.exitCode = exitCode(results);
  }
}
