/* LeetClaude / LeetCodex micro-app. No build step, no dependencies. The name follows the agent that opened the ticket. */
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const J = (v) => JSON.stringify(v);
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* private mode etc. */ } },
};
const pick = (arr, seed) => arr[Math.abs(seed | 0) % arr.length];
const ago = (t) => { const s = Math.max(0, Date.now() / 1000 - t); return s < 60 ? `${s | 0}s` : s < 3600 ? `${(s / 60) | 0}m` : `${(s / 3600).toFixed(1)}h`; };

const LINES = {
  solved: ["Strong hire. Your prompt privileges have been restored.", "Offer extended. Compensation: one (1) prompt.",
    "The hiring committee was impressed. {a} may proceed.", "Accepted. You may now return to your actual job.",
    "Passed the loop. Please do not ask about the team you'll be on."],
  bailed: ["Tapped out. The recruiter will circle back.", "We've decided to move forward with other candidates. (You may still prompt.)",
    "No worries, we'll keep your résumé on file for six to twelve months.", "Bailed. The gate opens anyway, because this is a joke."],
  waiting: ["{a} finished {t} ago. It's just sitting there.", "Your PR is ready. Your algorithm is not. ({t} ago)",
    "{a} wrapped up {t} ago and is pretending to look busy.", "Task done {t} ago. The interviewer is checking their watch."],
  working: ["{a} is working on: ", "Meanwhile, {a} is doing your actual job: ", "{a} is shipping: "],
  cancelled: ["Gate disabled mid-interview. Bold. Logged as a rage-quit.", "You walked out of the interview. HR has been notified (not really)."],
};

let S = null, renderKey = "", busy = false, editor = null, lastResult = null, hold = 0;
const B = () => (S && S.brand) || { name: "LeetClaude", agent: "claude", agent_name: "Claude", cli: "leetclaude", on: "/leetclaude:on" };
const say = (line) => line.replaceAll("{a}", B().agent_name);

function applyBrand() {
  const b = B();
  document.documentElement.dataset.agent = b.agent;
  document.title = S && S.ticket && !S.closed ? `${b.name} · ticket #${S.ticket.id}` : b.name;
  $("#brand").setAttribute("aria-label", b.name);
  $("#scrawl").textContent = b.agent === "codex" ? "x" : "Claude";
}

async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: J(body) });
  const j = await r.json().catch(() => ({ error: `HTTP ${r.status}` }));
  if (!r.ok || j.error) throw new Error(j.error || `HTTP ${r.status}`);
  return j;
}

function keyOf(s) {
  const t = s.ticket, it = s.item;
  if (!t) return "none";
  return [t.id, s.closed, t.status, it && it.pid, it && it.status, (t.queue || []).map((q) => q.status).join(","),
    it && it.answer && !!it.answer.community, it && !!it.statement].join("|");
}

async function poll() {
  try {
    const s = await api("/api/state");
    const k = keyOf(s);
    const statementOnly = S && k !== renderKey && k.replace(/\|(true|false)$/, "") === renderKey.replace(/\|(true|false)$/, "");
    S = s;
    header();
    if (k !== renderKey && Date.now() >= hold) {
      renderKey = k;
      if (statementOnly && $("#statement")) $("#statement").innerHTML = statementHTML(S.item);
      else render();
    }
  } catch (e) {
    $("#claude").textContent = `${B().name} server unreachable. Run: ${B().cli} start`;
  }
}

function header() {
  applyBrand();
  const t = S.ticket, c = $("#claude");
  c.classList.remove("done");
  if (!t) c.innerHTML = "No open ticket. <b>The gate is open.</b>";
  else if (S.closed) c.innerHTML = t.status === "cancelled" ? "Gate disabled." : `<b>Gate open.</b> Go prompt ${esc(B().agent_name)}.`;
  else if (t.task_done_at) { c.classList.add("done"); c.innerHTML = `<b>${esc(say(pick(LINES.waiting, t.id)).replace("{t}", ago(t.task_done_at)))}</b>`; }
  else c.innerHTML = `${esc(say(pick(LINES.working, t.id)))}<b>${esc(t.task)}</b>`;
  c.title = t ? t.task : "";
  const p = $("#parked");
  if (S.parked && S.parked.text) {
    p.hidden = false;
    p.innerHTML = `<div style="flex:1;min-width:0"><div class="lbl">Your blocked prompt, parked here so it isn't lost. Paste it back once you're through:</div><pre>${esc(S.parked.text)}</pre></div>
      <button class="ghost" id="copyParked">Copy</button><button class="ghost" id="dismissParked">Dismiss</button>`;
    $("#copyParked").onclick = () => navigator.clipboard.writeText(S.parked.text).then(() => ($("#copyParked").textContent = "Copied"));
    $("#dismissParked").onclick = () => api("/api/dismiss-parked", {}).then(poll);
  } else p.hidden = true;
}

function tick() {
  const el = $("#clock");
  const it = S && S.item;
  if (!it || !it.started) { el.textContent = "--:--"; return; }
  const end = it.status === "active" && !(S && S.closed) ? Date.now() / 1000 : (it.solved_at || (S.ticket && S.ticket.closed_at) || Date.now() / 1000);
  const s = Math.max(0, end - it.started) | 0;
  el.textContent = `${String((s / 60) | 0).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

function queueHTML(t) {
  if (!t.queue || t.queue.length < 2) return "";
  return `<div class="queue">${t.queue.map((q) => `<span class="pip ${q.status}">${esc(q.tier)}${q.kind === "sql" ? " sql" : ""} · ${esc(q.status === "active" ? "now" : q.status)}</span>`).join("")}</div>`;
}

function render() {
  const app = $("#app"), t = S.ticket, it = S.item;
  lastResult = null;
  if (!t) { app.innerHTML = idleHTML(); loadInlineStats(); return; }
  if (S.closed) { app.innerHTML = closedHTML(t, it); bindAnswerCopy(); loadInlineStats(); return; }
  if (!it) { app.innerHTML = `<div class="empty">Ticket #${t.id} has nothing active. Refreshing…</div>`; return; }
  if (it.kind === "quiz") return renderQuiz(app, t, it);
  renderProblem(app, t, it);
}

function idleHTML() {
  return `<div class="card hero"><div class="big" data-scrawl="prompt freely (for now)">No open ticket</div>
    <div class="note">Ask ${esc(B().agent_name)} for a code change and a problem will appear here. Turn the gate on in a project with <code>${esc(B().on)}</code>.</div></div>
    <div class="card"><h3>Interview record</h3><div id="inlineStats" class="small">…</div></div>`;
}

function answerHTML(a) {
  if (!a) return "";
  if (a.text !== undefined) return `<div class="card"><h3>Answer</h3><p><b>${esc(a.text)}</b></p><p class="note">${esc(a.why || "")}</p></div>`;
  let h = `<div class="card"><h3>The answer (for next time)</h3>`;
  if (a.approach) h += `<p>${esc(a.approach)}</p>`;
  if (a.code) h += `<div class="row"><span class="small">Reference (${esc(a.lang)})</span><span class="spacer" style="flex:1"></span><button class="ghost copy" data-k="code">Copy</button></div><pre class="answer">${esc(a.code)}</pre>`;
  if (a.community) h += `<div class="row" style="margin-top:12px"><span class="small">Top community answer (${esc(a.community.lang)}): <a href="${esc(a.community.url)}" target="_blank" rel="noopener">${esc(a.community.title || "LeetCode")}</a></span><span style="flex:1"></span><button class="ghost copy" data-k="community">Copy</button></div><pre class="answer">${esc(a.community.code)}</pre>`;
  else if (a.url) h += `<p class="small">Fetching a community answer in your language… or browse <a href="${esc(a.url)}" target="_blank" rel="noopener">LeetCode solutions</a>.</p>`;
  if (!a.code && !a.community) h += `<p class="note">No local reference for this live problem. Community answers load from LeetCode (above, when found).</p>`;
  return h + "</div>";
}

function bindAnswerCopy() {
  document.querySelectorAll("button.copy").forEach((b) => {
    b.onclick = () => {
      const a = S.item && S.item.answer;
      const txt = b.dataset.k === "community" ? a.community.code : a.code;
      navigator.clipboard.writeText(txt).then(() => (b.textContent = "Copied"));
    };
  });
}

function closedHTML(t, it) {
  if (t.status === "cancelled") return `<div class="card hero bad"><div class="big" data-scrawl="rage-quit logged">Interview abandoned</div><div class="note">${esc(pick(LINES.cancelled, t.id))}</div></div>`;
  const ok = t.status === "solved";
  const items = (t.queue || []).filter((q) => q.status !== "exchanged");
  return `<div class="card hero ${ok ? "ok" : "bad"}"><div class="big" data-scrawl="${ok ? "strong hire!" : "no shame. it's a joke."}">${ok ? "Accepted" : "Tapped out"}</div>
      <div>${esc(say(pick(ok ? LINES.solved : LINES.bailed, t.id)))}</div>
      <div class="note" style="margin-top:8px">Ticket #${t.id} · ${items.length} problem${items.length === 1 ? "" : "s"} · for: ${esc(t.task)}</div></div>
    ${!ok && it ? answerHTML(it.answer) : ""}
    <div class="card"><h3>Interview record</h3><div id="inlineStats" class="small">…</div></div>`;
}

function statementHTML(it) {
  if (it.statement) return it.statement;
  return (it.summary || "") + (it.source === "bank" && it.url ? `<p class="note">Fetching the official statement from LeetCode…</p>` : "");
}

function tableHTML(cols, rows) {
  return `<table class="t"><tr>${cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr>${rows.map((r) => `<tr>${r.map((v) => `<td>${v === null ? "<i>null</i>" : esc(v)}</td>`).join("")}</tr>`).join("")}</table>`;
}

function datasetHTML(ds) {
  return `<div class="tables">${Object.entries(ds.headers || {}).map(([tname, cols]) => `<div><div class="small">${esc(tname)}</div>${tableHTML(cols, (ds.rows || {})[tname] || [])}</div>`).join("")}</div>`;
}

function examplesHTML(it) {
  const ex = it.examples || [];
  if (it.kind === "sql") {
    return ex.map((e, i) => `<div class="ex"><div class="k">Example ${i + 1} input</div>${datasetHTML(e.dataset)}<div class="k">Expected</div>${tableHTML(e.expected.cols, e.expected.rows)}</div>`).join("");
  }
  return ex.map((e) => `<div class="ex"><span class="k">Input:</span> ${esc(e.input)}<br><span class="k">Output:</span> ${esc(J(e.expected))}</div>`).join("");
}

function renderProblem(app, t, it) {
  const langs = it.langs || {};
  let lang = store.get(`lg:lang:${it.pid}`) || it.lang;
  if (!langs[lang]) lang = Object.keys(langs)[0];
  const cmpNote = it.cmp === "unordered" ? " Any order accepted." : it.cmp === "unordered_deep" ? " Order doesn't matter (at any level)." : "";
  const hidden = it.n_tests - it.n_examples;
  const testsNote = it.source === "live"
    ? `Checked against LeetCode's ${it.n_tests} example${it.n_tests === 1 ? "" : "s"} (live pull, no hidden tests).`
    : `Run = ${it.n_examples} examples. Submit = all ${it.n_tests} tests (${hidden} hidden).`;
  const nextTier = it.tier === "hard" ? "medium" : "easy";
  app.innerHTML = `${queueHTML(t)}<div class="split">
    <section class="card">
      <h1>${it.lc ? esc(it.lc) + ". " : ""}${esc(it.title)}</h1>
      <div class="meta"><span class="badge ${esc(it.tier)}">${esc(it.tier)}</span>${it.kind === "sql" ? '<span class="badge quiz">SQL</span>' : ""}
        <span>${it.source === "live" ? "random LeetCode pull" : "curated"}</span>
        ${it.url ? `<a href="${esc(it.url)}" target="_blank" rel="noopener">Open on LeetCode ↗</a>` : ""}</div>
      <div class="statement" id="statement">${statementHTML(it)}</div>
      ${it.kind === "sql" ? `<h3 style="margin-top:14px">Schema</h3><pre class="detail">${esc((it.schema || []).join(";\n"))};</pre>` : ""}
      <h3 style="margin-top:14px">Examples</h3><div class="examples">${examplesHTML(it)}</div>
      <p class="note">${esc(testsNote + cmpNote)}${it.kind === "sql" ? (it.ordered ? " Row order matters." : " Row order doesn't matter.") : ""}</p>
    </section>
    <section>
      <div class="card">
        <div class="toolbar">
          <select id="lang" aria-label="Language">${Object.entries(langs).map(([k, v]) => `<option value="${esc(k)}" ${k === lang ? "selected" : ""}>${esc(v)}</option>`).join("")}</select>
          <button class="ghost" id="reset" title="Restore starter code">Reset</button>
          <span class="spacer"></span>
          ${it.can_exchange ? `<button class="ghost" id="exchange" title="One ${esc(it.tier)} for two ${nextTier}">Trade for 2× ${nextTier}</button>` : ""}
          <button class="danger" id="bail">Tap out</button>
          <button id="run">Run</button>
          <button class="primary" id="submit">Submit</button>
        </div>
        <div class="editor"><div class="gutter" id="gutter">1</div><textarea class="code" id="code" spellcheck="false" autocomplete="off" autocapitalize="off"></textarea></div>
        <div class="hint">⌘/Ctrl + ' runs examples · ⌘/Ctrl + Enter submits · Tab indents · attempts so far: ${it.attempts || 0}</div>
        <div class="results" id="results"></div>
      </div>
    </section></div>`;
  editor = setupEditor($("#code"), $("#gutter"), it, lang);
  $("#lang").onchange = (e) => { editor.save(); lang = e.target.value; store.set(`lg:lang:${it.pid}`, lang); editor.load(lang); };
  $("#reset").onclick = () => editor.reset();
  $("#run").onclick = () => runCode(false);
  $("#submit").onclick = () => runCode(true);
  $("#bail").onclick = () => confirmModal("Tap out?", "You'll see the answer and the gate opens. It goes on your permanent record (a SQLite file).", "Tap out", bail);
  if ($("#exchange")) $("#exchange").onclick = () => confirmModal(`Trade this ${it.tier}?`, `You'll get two ${nextTier} problems instead. Both must be solved.`, "Trade", exchange);
}

function setupEditor(ta, gutter, it, lang) {
  const k = (l) => `lg:code:${it.pid}:${l}`;
  let cur = lang;
  const lines = () => { const n = ta.value.split("\n").length; gutter.textContent = Array.from({ length: n }, (_, i) => i + 1).join("\n"); };
  const load = (l) => { cur = l; ta.value = store.get(k(l)) ?? (it.starters || {})[l] ?? ""; lines(); };
  const save = () => store.set(k(cur), ta.value);
  ta.addEventListener("input", () => { lines(); save(); });
  ta.addEventListener("scroll", () => { gutter.scrollTop = ta.scrollTop; });
  ta.addEventListener("keydown", (e) => {
    const mod = e.metaKey || e.ctrlKey;
    if (mod && e.key === "Enter") { e.preventDefault(); runCode(true); return; }
    if (mod && e.key === "'") { e.preventDefault(); runCode(false); return; }
    const { selectionStart: s, selectionEnd: en, value: v } = ta;
    if (e.key === "Tab") {
      e.preventDefault();
      const ls = v.lastIndexOf("\n", s - 1) + 1;
      if (s === en && !e.shiftKey) { ta.setRangeText("    ", s, en, "end"); }
      else {
        const block = v.slice(ls, en);
        const out = e.shiftKey ? block.replace(/^ {1,4}/gm, "") : block.replace(/^/gm, "    ");
        ta.setRangeText(out, ls, en, "select");
      }
      lines(); save();
    } else if (e.key === "Enter" && !mod) {
      e.preventDefault();
      const ls = v.lastIndexOf("\n", s - 1) + 1;
      const line = v.slice(ls, s);
      let ind = (line.match(/^\s*/) || [""])[0];
      if (/[:{[(]\s*$/.test(line)) ind += "    ";
      ta.setRangeText("\n" + ind, s, en, "end");
      lines(); save();
    }
  });
  load(lang);
  return { load, save, reset: () => { ta.value = (it.starters || {})[cur] || ""; lines(); save(); }, lang: () => cur, value: () => ta.value };
}

async function runCode(submit) {
  if (busy || !editor) return;
  busy = true;
  ["run", "submit"].forEach((id) => $("#" + id) && ($("#" + id).disabled = true));
  const res = $("#results");
  res.innerHTML = `<div class="banner info">${submit ? "Submitting" : "Running examples"}… (compiled languages take a second or two)</div>`;
  try {
    const r = await api("/api/run", { code: editor.value(), lang: editor.lang(), submit });
    lastResult = r;
    res.innerHTML = resultHTML(r, submit);
    if (r.solved) { hold = Date.now() + 1800; setTimeout(poll, 1900); }
  } catch (e) {
    res.innerHTML = `<div class="banner bad">${esc(e.message)}</div>`;
  } finally {
    busy = false;
    ["run", "submit"].forEach((id) => $("#" + id) && ($("#" + id).disabled = false));
  }
}

function resultHTML(r, submit) {
  if (r.compile_error) return `<div class="banner bad">Compile / load error</div><pre class="detail">${esc(r.compile_error)}</pre>`;
  let h = "";
  if (r.solved) h += `<div class="banner ok">Accepted. ${r.next ? `Next up: ${esc(r.next)}.` : "Ticket cleared. The gate is open."}</div>`;
  else if (r.status === "timeout") h += `<div class="banner bad">Time limit exceeded (10s). ${r.passed}/${r.total} passed before the clock ran out.</div>`;
  else h += `<div class="banner ${r.all_passed ? "ok" : "bad"}">${r.passed}/${r.total} ${submit ? "tests" : "examples"} passed${r.all_passed && !submit ? ". Now Submit." : ""}${r.ms ? ` · ${r.ms} ms` : ""}</div>`;
  h += `<div class="cases">${r.cases.map((c) => `<span class="case ${c.pass ? "p" : "f"}">${c.hidden ? "h" : ""}#${c.i + 1} ${c.pass ? "✓" : "✗"}</span>`).join("")}</div>`;
  const f = r.cases.find((c) => !c.pass);
  if (f) {
    if (f.dataset !== undefined) {
      h += `<div class="detail">${f.error ? `<div><span class="k">Error:</span> ${esc(f.error)}</div>` : ""}<div class="k">Input (test ${f.i + 1})</div>${datasetHTML(f.dataset)}
        <div class="tables"><div><div class="k">Expected</div>${tableHTML(f.expected.cols, f.expected.rows)}</div>${f.got ? `<div><div class="k">Yours</div>${tableHTML(f.got.cols, f.got.rows)}</div>` : ""}</div></div>`;
    } else if (f.input !== undefined) {
      h += `<div class="detail"><span class="k">Input:</span>    ${esc(f.input)}\n<span class="k">Expected:</span> ${esc(J(f.expected))}\n<span class="k">Yours:</span>    ${f.error ? "" : esc(J(f.got))}${f.error ? `\n<span class="k">Error:</span>\n${esc(f.error)}` : ""}</div>`;
    } else if (f.error) h += `<pre class="detail">${esc(f.error)}</pre>`;
  }
  if (r.stdout) h += `<div class="small" style="margin-top:8px">Your stdout</div><pre class="detail">${esc(r.stdout)}</pre>`;
  if (r.note) h += `<p class="note" style="margin-top:8px">${esc(r.note)}</p>`;
  if (r.stderr && !r.all_passed) h += `<div class="small" style="margin-top:8px">stderr</div><pre class="detail">${esc(r.stderr)}</pre>`;
  return h;
}

function renderQuiz(app, t, it) {
  app.innerHTML = `${queueHTML(t)}<div class="card quiz" style="max-width:820px;margin:0 auto">
    <div class="meta"><span class="badge quiz">quiz</span><span>${it.source === "claude" ? `about this project (written by ${esc(B().agent_name)})` : "software engineering"}</span></div>
    <h1>${esc(it.q)}</h1>
    ${it.code ? `<pre class="answer">${esc(it.code)}</pre>` : ""}
    <div id="qbody">${it.written
      ? `<input type="text" id="qtext" placeholder="Short answer" autocomplete="off"><div class="row end"><button class="danger" id="bail">Tap out</button><button class="primary" id="qsend">Answer</button></div>`
      : `${it.choices.map((c, i) => `<label class="choice" data-i="${i}"><input type="radio" name="q" value="${i}"><span>${esc(c)}</span></label>`).join("")}
         <div class="row end"><button class="danger" id="bail">Tap out</button><button class="primary" id="qsend">Answer</button></div>`}</div>
    <div id="qres"></div></div>`;
  $("#bail").onclick = () => confirmModal("Tap out?", "You'll see the answer and the gate opens.", "Tap out", bail);
  if (it.written) $("#qtext").addEventListener("keydown", (e) => { if (e.key === "Enter") $("#qsend").click(); });
  $("#qsend").onclick = async () => {
    const body = it.written ? { text: $("#qtext").value } : { choice: (document.querySelector('input[name="q"]:checked') || {}).value };
    if (!it.written && body.choice === undefined) return;
    $("#qsend").disabled = true;
    try {
      const r = await api("/api/quiz", body);
      if (!it.written) document.querySelectorAll(".choice").forEach((el) => {
        if (el.querySelector("span").textContent === r.text) el.classList.add("right");
        else if (el.dataset.i === String(body.choice)) el.classList.add("wrong");
      });
      $("#qres").innerHTML = `<div class="banner ${r.correct ? "ok" : "bad"}" style="margin-top:12px">${r.correct ? "Correct." : `Not quite. Answer: ${esc(r.text)}. Here's another one.`}</div><p class="note">${esc(r.why || "")}</p>`;
      hold = Date.now() + (r.correct ? 1500 : 4500);
      setTimeout(poll, r.correct ? 1600 : 4600);
    } catch (e) { $("#qres").innerHTML = `<div class="banner bad">${esc(e.message)}</div>`; $("#qsend").disabled = false; }
  };
}

function confirmModal(title, body, okLabel, fn) {
  const d = $("#modal");
  $("#modalTitle").textContent = title;
  $("#modalBody").textContent = body;
  $("#modalOk").textContent = okLabel;
  d.onclose = () => { if (d.returnValue === "ok") fn(); };
  d.showModal();
}

async function bail() {
  try { await api("/api/bail", {}); } catch (e) { alertBanner(e.message); }
  poll();
  setTimeout(poll, 2500);
  setTimeout(poll, 6000);
}

async function exchange() {
  const b = $("#exchange");
  if (b) { b.disabled = true; b.textContent = "Negotiating…"; }
  try { await api("/api/exchange", {}); } catch (e) { alertBanner(e.message); }
  poll();
}

function alertBanner(msg) { const r = $("#results"); if (r) r.innerHTML = `<div class="banner bad">${esc(msg)}</div>`; }

function statsTable(s) {
  const order = ["quiz", "easy", "medium", "hard"];
  const rows = order.filter((k) => s.tiers[k]).map((k) => {
    const t = s.tiers[k];
    const solved = t.solved + t.quiz_correct, bailed = t.bailed + t.quiz_missed, done = solved + bailed;
    return `<tr><td>${k}</td><td>${t.presented}</td><td>${solved}</td><td>${bailed}</td><td>${t.exchanged}</td><td>${done ? Math.round((100 * solved) / done) + "%" : "–"}</td><td>${t.avg_solve_secs ? (t.avg_solve_secs / 60).toFixed(1) + "m" : "–"}</td><td>${t.avg_attempts ?? "–"}</td></tr>`;
  }).join("");
  if (!rows) return `<p class="small">No interviews yet. Enjoy it while it lasts.</p>`;
  return `<table class="stats"><tr><th>Tier</th><th>Seen</th><th>Solved</th><th>Bailed</th><th>Traded</th><th>Solve rate</th><th>Avg time</th><th>Avg submits</th></tr>${rows}</table>
    <p class="small">Current streak: ${s.streak} · rage-quits: ${s.totals.rage_quit || 0}</p>`;
}

async function loadInlineStats() {
  const el = $("#inlineStats");
  if (!el) return;
  try { el.innerHTML = statsTable(await api("/api/stats")); } catch { el.textContent = "stats unavailable"; }
}

$("#statsBtn").onclick = async () => {
  const s = await api("/api/stats").catch(() => null);
  if (!s) return;
  const recent = (s.problems || []).slice(0, 15).map((p) => `<tr><td class="l">${esc(p.title || p.pid)}</td><td>${esc(p.tier)}</td><td>${esc(p.lang || "")}</td><td>${p.solved}</td><td>${p.bailed}</td></tr>`).join("");
  $("#statsBody").innerHTML = statsTable(s) + (recent ? `<h3 style="margin-top:16px">Recent problems</h3><table class="stats"><tr><th>Problem</th><th>Tier</th><th>Lang</th><th>Solved</th><th>Bailed</th></tr>${recent}</table>` : "");
  $("#statsModal").showModal();
};

poll();
setInterval(poll, 2500);
setInterval(tick, 1000);
