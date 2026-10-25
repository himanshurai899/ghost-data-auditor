// Real-browser smoke check of the console's landing-page tooltips (mouse, keyboard, click-to-pin, touch) and of
// horizontal overflow, using Chrome's DevTools protocol. No dependencies: needs Node >= 22 (built-in WebSocket) and Chrome.
//
//   (start the API on :8000 and `npm run dev` in web/ first)
//   node scripts/ui_check.mjs [http://127.0.0.1:5173]        CHROME=path/to/chrome.exe to override the browser
//
// Exit code 1 if any check fails.
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

const BASE = process.argv[2] || 'http://127.0.0.1:5173'
const CHROME = process.env.CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const PORT = 9333 + Math.floor(Math.random() * 500)
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'uicheck-'))
const proc = spawn(CHROME, ['--headless=new', '--disable-gpu', '--no-sandbox', `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' })
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
let failures = 0
const rows = []
const check = (name, ok, detail = '') => { rows.push(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  ' + detail : ''}`); if (!ok) failures++ }

async function connect() {
  for (let i = 0; i < 50; i++) {
    try { const t = await (await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`, { method: 'PUT' })).json(); return t.webSocketDebuggerUrl } catch { await sleep(200) }
  }
  throw new Error('Chrome did not start')
}
const ws = new WebSocket(await connect())
await new Promise((r) => (ws.onopen = r))
let id = 0
const pending = new Map()
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id) } }
const send = (method, params = {}) => new Promise((res, rej) => { const i = ++id; pending.set(i, (d) => (d.error ? rej(new Error(method + ': ' + d.error.message)) : res(d.result))); ws.send(JSON.stringify({ id: i, method, params })) })
const ev = async (expr) => (await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true })).result.value
const mouse = (type, x, y, extra = {}) => send('Input.dispatchMouseEvent', { type, x, y, button: 'left', clickCount: 1, ...extra })
const key = async (k, code, vk) => { await send('Input.dispatchKeyEvent', { type: 'keyDown', key: k, code, windowsVirtualKeyCode: vk }); await send('Input.dispatchKeyEvent', { type: 'keyUp', key: k, code, windowsVirtualKeyCode: vk }) }

const tip = () => ev(`(() => { const t = [...document.querySelectorAll('[role=tooltip]')]; if (!t.length) return null; const r = t[0].getBoundingClientRect();
  return { n: t.length, len: t[0].textContent.length, text: t[0].textContent.slice(0, 70), inView: r.left >= -1 && r.right <= innerWidth + 1 && r.top >= -1 && r.bottom <= innerHeight + 1 } })()`)
const center = (sel, i) => ev(`(() => { const e = document.querySelectorAll(${JSON.stringify(sel)})[${i}]; e.scrollIntoView({ inline: 'center', block: 'center' }); const r = e.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2, name: (e.getAttribute('aria-label') || e.textContent).trim().slice(0, 28) } })()`)

async function open(theme, w, h, mobile = false) {
  await send('Page.enable'); await send('Runtime.enable')
  await send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: 1, mobile })
  await send('Emulation.setTouchEmulationEnabled', { enabled: mobile })
  await send('Page.addScriptToEvaluateOnNewDocument', { source: `try{localStorage.setItem('ghost.theme','${theme}')}catch{}` })
  await send('Page.navigate', { url: BASE + '/#/' })
  await sleep(2500)
  await ev(`location.reload()`); await sleep(2500)
}

try {
  // ---------------- desktop: hover, keyboard, pin
  await open('light', 1280, 900)
  check('theme attribute applied (light)', (await ev(`document.documentElement.getAttribute('data-theme')`)) === 'light')
  const N = await ev(`document.querySelectorAll('.pl-node, .pl-gate').length`)
  check('pipeline has 9 stages + 7 gates as focusable buttons', N === 16, `found ${N}`)
  let hoverOk = 0, viewOk = 0, closeOk = 0
  for (let i = 0; i < N; i++) {
    const c = await center('.pl-node, .pl-gate', i)
    await mouse('mouseMoved', c.x, c.y); await sleep(260)
    const t = await tip()
    if (t && t.len > 40) hoverOk++
    if (t && t.inView) viewOk++
    await mouse('mouseMoved', 4, 4); await sleep(260)
    if ((await tip()) === null) closeOk++
  }
  check('hover opens an informative tooltip on every stage and gate', hoverOk === N, `${hoverOk}/${N}`)
  check('tooltip stays inside the viewport', viewOk === N, `${viewOk}/${N}`)
  check('tooltip closes when the mouse leaves', closeOk === N, `${closeOk}/${N}`)

  await ev(`document.activeElement && document.activeElement.blur(); window.scrollTo(0, 0)`)
  let tabs = 0, reached = false
  for (; tabs < 60 && !reached; tabs++) { await key('Tab', 'Tab', 9); reached = await ev(`!!document.activeElement.closest('.pl-node, .pl-gate')`) }
  await sleep(250)
  const kt = await tip()
  check('keyboard Tab reaches a stage and shows its tooltip (focus)', reached && !!kt && kt.len > 40, `after ${tabs} Tab presses`)
  check('focused trigger is described by the tooltip (aria-describedby)', (await ev(`(() => { const a = document.activeElement, id = a.getAttribute('aria-describedby'); return !!id && !!document.getElementById(id) })()`)) === true)
  await key('Escape', 'Escape', 27); await sleep(200)
  check('Escape closes the tooltip', (await tip()) === null)

  const g = await center('.pl-gate', 0)
  await mouse('mouseMoved', g.x, g.y); await mouse('mousePressed', g.x, g.y); await mouse('mouseReleased', g.x, g.y); await sleep(200)
  await mouse('mouseMoved', 4, 4); await sleep(300)
  check('click pins the tooltip open after the mouse leaves', (await tip()) !== null)
  await mouse('mousePressed', 640, 8); await mouse('mouseReleased', 640, 8); await sleep(250)
  check('click outside closes a pinned tooltip', (await tip()) === null)

  // ---------------- mobile: touch, overflow
  await open('dark', 375, 812, true)
  check('theme attribute applied (dark) at 375px', (await ev(`document.documentElement.getAttribute('data-theme')`)) === 'dark')
  const m = await center('.pl-gate', 1)
  await send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: m.x, y: m.y }] })
  await send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] }); await sleep(350)
  const tt = await tip()
  check('tap opens the gate tooltip on a 375px touch device', !!tt && tt.len > 40, tt ? tt.text.slice(0, 40) : 'no tooltip')
  check('touch tooltip fits the 375px viewport', !!tt && tt.inView)
  await send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: 5, y: 5 }] })
  await send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] }); await sleep(300)
  check('tapping elsewhere closes it', (await tip()) === null)
  check('no horizontal page overflow at 375px (landing)', (await ev(`document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1`)) === true)
  const tapTargets = await ev(`[...document.querySelectorAll('.pl-node, .pl-gate, button')].filter((b) => { const r = b.getBoundingClientRect(); return r.width > 0 && (r.height < 32 || r.width < 32) && getComputedStyle(b).visibility !== 'hidden' }).map((b) => (b.getAttribute('aria-label') || b.textContent).trim().slice(0, 20) + ' ' + Math.round(b.getBoundingClientRect().width) + 'x' + Math.round(b.getBoundingClientRect().height))`)
  check('touch targets at least 32px (visible buttons)', tapTargets.length === 0, tapTargets.join(' | '))
} catch (e) {
  check('script completed', false, String(e.message || e))
} finally {
  console.log(rows.join('\n'))
  console.log(failures ? `\n${failures} check(s) failed` : '\nall checks passed')
  try { ws.close() } catch { /* ignore */ }
  proc.kill()
  try { fs.rmSync(profile, { recursive: true, force: true }) } catch { /* ignore */ }
  process.exit(failures ? 1 : 0)
}
