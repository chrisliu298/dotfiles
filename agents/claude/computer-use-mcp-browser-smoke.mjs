// Real browser parity check, without model calls or account writes. Opens local test tabs.
// Run: node agents/claude/computer-use-mcp-browser-smoke.mjs [--screenshot /tmp/proof.jpg]
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
import readline from 'node:readline';
import { randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const launcher = fileURLToPath(new URL('./computer-use-mcp.sh', import.meta.url));
const html = `<!doctype html><meta charset="utf-8"><title>MCP parity</title>
<style>body{font:20px system-ui;margin:40px}input,button,select{font:inherit;margin:8px}iframe{display:block;height:140px}</style>
<h1>Claude / Codex MCP parity</h1><label>测试文本 <input></label>
<label>模式 <select><option>默认</option><option>增强</option></select></label>
<label><input type="checkbox">确认测试</label><button id="apply">应用</button><output id="result">等待</output>
<iframe src="/frame" title="嵌入测试"></iframe><button id="async">异步更新</button><output id="status">未更新</output>
<p><a href="/next">下一页</a></p>
<script>document.querySelector('#apply').onclick=()=>document.querySelector('#result').textContent=document.querySelector('input').value+' / '+document.querySelector('select').value+' / '+document.querySelector('[type=checkbox]').checked;
document.querySelector('#async').onclick=()=>setTimeout(()=>document.querySelector('#status').textContent='更新完成',150);</script>`;
const web = http.createServer((req, res) => {
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  res.end(req.url === '/frame'
    ? `<label>嵌入输入 <input></label><button onclick="this.textContent='嵌入成功'">嵌入按钮</button>`
    : req.url === '/next' ? '<h1>第二页</h1>' : html);
});
web.listen(0, '127.0.0.1');
await new Promise((resolve) => web.once('listening', resolve));
const url = `http://127.0.0.1:${web.address().port}/`;
const clients = [];
const text = (reply) => (reply.content || []).filter((item) => item.type === 'text').map((item) => item.text).join('\n');
const marker = (reply) => JSON.parse(text(reply).match(/PARITY(\{[^\n]*\})/)[1]);

async function connect(host) {
  const child = spawn(launcher, [], { stdio: ['pipe', 'pipe', 'inherit'] });
  let nextId = 1;
  const session = randomUUID();
  const pending = new Map();
  const exited = new Promise((resolve) => child.once('exit', (code, signal) => resolve({ code, signal })));
  const fail = (error) => { for (const p of pending.values()) p.reject(error); pending.clear(); };
  child.on('error', fail);
  child.on('exit', () => fail(new Error(`${host} MCP exited before replying`)));
  readline.createInterface({ input: child.stdout }).on('line', (line) => {
    const msg = JSON.parse(line);
    const p = pending.get(msg.id);
    if (!p || msg.method) return;
    pending.delete(msg.id);
    if (msg.error) p.reject(new Error(msg.error.message)); else p.resolve(msg.result);
  });
  const request = (method, params) => new Promise((resolve, reject) => {
    const id = nextId++;
    // Claude sends no Codex identity; Codex can send a different turn identity on each call.
    if (host === 'codex' && method === 'tools/call') {
      params._meta = { 'x-codex-turn-metadata': { session_id: session, turn_id: `host-turn-${id}` } };
    }
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`${host}: ${method} timed out`)); }, 40000);
    pending.set(id, {
      resolve: (value) => { clearTimeout(timer); resolve(value); },
      reject: (error) => { clearTimeout(timer); reject(error); },
    });
    child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n');
  });
  const client = {
    host, child, request,
    async call(code) {
      const reply = await request('tools/call', { name: 'js', arguments: { code, timeout_ms: 30000 } });
      assert.equal(reply.isError, false, text(reply));
      assert.equal(reply._meta?.['codex/toolSurface']?.screenshot, undefined);
      return reply;
    },
    async stop() {
      child.stdin.end();
      const timer = setTimeout(() => child.kill('SIGKILL'), 10000);
      try { assert.deepEqual(await exited, { code: 0, signal: null }); }
      finally { clearTimeout(timer); }
    },
  };
  clients.push(client);
  client.info = await request('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: host, version: 'parity-smoke' } });
  child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }) + '\n');
  client.tools = (await request('tools/list', {})).tools;
  const listed = await client.call('await cua.listBrowsers();');
  const browsers = listed.content.filter((item) => item.type === 'text' && item.text.startsWith('[')).map((item) => JSON.parse(item.text)).flat();
  assert.equal(browsers.length, 1, 'Expected one connected browser; open Helium with the ChatGPT extension connected');
  client.browserId = browsers[0].id;
  return client;
}

try {
  for (const host of ['claude', 'codex']) {
    const client = await connect(host);
    const created = await client.call(`var parityTab = await cua.createBrowserTab(${JSON.stringify(client.browserId)}, ${JSON.stringify(url)}, {sessionName:"🔬 MCP parity ${host}"});`);
    client.tabId = created._meta['codex/toolSurface'].openTabIds[0];
    assert.ok(client.tabId);
    const page = await client.call('nodeRepl.write(await parityTab.playwright.domSnapshot());');
    assert.match(text(page), /textbox "测试文本"/);
    const applied = await client.call(`
await parityTab.playwright.getByRole('textbox',{name:'测试文本',exact:true}).fill('同一套接口 ✓');
await parityTab.playwright.getByRole('combobox',{name:'模式'}).selectOption({label:'增强'});
await parityTab.playwright.getByRole('checkbox',{name:'确认测试'}).check();
await parityTab.playwright.getByRole('button',{name:'应用',exact:true}).click();
await parityTab.playwright.frameLocator('iframe').getByRole('textbox',{name:'嵌入输入'}).fill('iframe 中文');
await parityTab.playwright.frameLocator('iframe').getByRole('button',{name:'嵌入按钮'}).click();
await parityTab.playwright.getByRole('button',{name:'异步更新'}).click();
await parityTab.playwright.getByText('更新完成',{exact:true}).waitFor({state:'visible',timeoutMs:3000});
nodeRepl.write(await parityTab.playwright.domSnapshot());`);
    assert.match(text(applied), /同一套接口 ✓ \/ 增强 \/ true/);
    assert.match(text(applied), /嵌入成功/);
    const screenshot = await client.call('await parityTab.getScreenshot();');
    const img = screenshot.content.find((item) => item.type === 'image');
    assert.ok(img, 'Explicit screenshot must reach both hosts as an MCP image');
    if (host === 'codex' && process.argv[2] === '--screenshot') {
      fs.writeFileSync(process.argv[3], Buffer.from(img.data, 'base64'));
    }
    const navigated = await client.call(`await parityTab.playwright.getByRole('link',{name:'下一页'}).click(); nodeRepl.write(await parityTab.playwright.domSnapshot());`);
    assert.match(text(navigated), /heading "第二页"/);
    await client.call('await parityTab.back(); nodeRepl.write(await parityTab.playwright.domSnapshot());');
    const reset = await client.request('tools/call', { name: 'js_reset', arguments: {} });
    assert.equal(reset.isError, false);
    await client.call(`var parityTab = await cua.getTab(${JSON.stringify(client.tabId)}, {browser:${JSON.stringify(client.browserId)}});`);
    const preserved = await client.call('nodeRepl.write(await parityTab.playwright.domSnapshot());');
    assert.match(text(preserved), /同一套接口 ✓ \/ 增强 \/ true/);
    console.log(`ok ${host}: input, select, checkbox, iframe, async, screenshot, navigation and reset`);
  }
  const [claude, codex] = clients;
  assert.deepEqual(claude.tools, codex.tools);
  assert.equal(claude.info.instructions, codex.info.instructions);
  await claude.stop();
  const observed = marker(await codex.call(`nodeRepl.write('PARITY'+JSON.stringify({ids:(await cua.listTabs({browser:${JSON.stringify(codex.browserId)},emit:false})).map(t=>t.id)}));`));
  assert.ok(!observed.ids.includes(claude.tabId), 'Claude session tab leaked');
  assert.ok(observed.ids.includes(codex.tabId), 'Claude exit closed the Codex tab');
  await codex.stop();
  const observer = await connect('observer');
  const remaining = marker(await observer.call(`nodeRepl.write('PARITY'+JSON.stringify({ids:(await cua.listTabs({browser:${JSON.stringify(observer.browserId)},emit:false})).map(t=>t.id)}));`));
  assert.ok(!remaining.ids.includes(codex.tabId), 'Codex session tab leaked after host metadata/reset');
  console.log('ok parity: identical tools/instructions; both sessions clean up without affecting each other');
} finally {
  await Promise.allSettled(clients.map((client) => client.stop()));
  web.closeAllConnections();
  web.close();
}
