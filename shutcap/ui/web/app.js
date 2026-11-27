// ShutCap main window. Talks to Python through window.pywebview.api (see shutcap/ui/webapp.py).
"use strict";

const $ = id => document.getElementById(id);
let api = null;
let S = null;              // last state from Python
let view = null;
let dialMinutes = 23 * 60 + 15;
let setupTimes = null;

const SETUP_ROWS = [
  ["warning_1_time", "First warning"],
  ["curfew_time", "Curfew"],
  ["shutdown_time", "Off"],
];
const ROWS = [
  ["warning_1_time", "First warning"],
  ["warning_2_time", "Last warning"],
  ["curfew_time", "Curfew"],
  ["grace_reminder_1_time", "Reminder"],
  ["grace_reminder_2_time", "Reminder"],
  ["final_warning_time", "Last minute"],
  ["shutdown_time", "Off"],
];

// ---------- helpers ----------------------------------------------------------------
const pad = n => String(n).padStart(2, "0");
const hhmm = m => `${pad(Math.floor(m / 60) % 24)}:${pad(m % 60)}`;
const toMin = s => { const [h, m] = s.split(":").map(Number); return h * 60 + m; };

function normalizeTime(raw) {
  const s = raw.trim();
  let h, m;
  const colon = s.match(/^(\d{1,2})[:.](\d{1,2})$/);
  const digits = s.match(/^(\d{1,4})$/);
  if (colon) { h = +colon[1]; m = +colon[2]; }
  else if (digits) {
    const d = digits[1];
    if (d.length <= 2) { h = +d; m = 0; } else { h = +d.slice(0, d.length - 2); m = +d.slice(-2); }
  } else return null;
  if (h > 23 || m > 59) return null;
  return `${pad(h)}:${pad(m)}`;
}

function duration(sec) {
  sec = Math.max(0, Math.round(sec));
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60);
  if (h && m) return `${h} h ${m} min`;
  if (h) return `${h} h`;
  return `${Math.max(1, m)} min`;
}
const clock = sec => { sec = Math.max(0, Math.ceil(sec)); return `${Math.floor(sec / 60)}:${pad(sec % 60)}`; };

let toastTimer;
function toast(text, actionLabel, action) {
  $("toast-text").textContent = text;
  const b = $("toast-action");
  b.hidden = !actionLabel;
  if (actionLabel) { b.textContent = actionLabel; b.onclick = action; }
  $("toast").classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $("toast").classList.remove("show"), 3200);
}

function sheet({ title, body, ok, cancel = "Cancel" }) {
  return new Promise(resolve => {
    $("sheet-title").textContent = title;
    $("sheet-body").textContent = body;
    $("sheet-ok").textContent = ok;
    $("sheet-cancel").textContent = cancel;
    const done = v => { $("scrim").classList.remove("open"); document.removeEventListener("keydown", key); resolve(v); };
    const key = e => { if (e.key === "Escape") done(false); };
    $("sheet-ok").onclick = () => done(true);
    $("sheet-cancel").onclick = () => done(false);
    document.addEventListener("keydown", key);
    $("scrim").classList.add("open");
    $("sheet-cancel").focus();
  });
}

// ---------- navigation -------------------------------------------------------------
function show(name) {
  view = name;
  document.querySelectorAll(".view").forEach(v => v.classList.toggle("active", v.id === "v-" + name));
  const page = name === "settings" || name === "history";
  const setup = name.startsWith("setup");
  $("back").hidden = !page;
  $("go-settings").hidden = page || setup;
  $("go-history").hidden = page || setup;
  $("practice").hidden = setup || !(S && S.practice);
  if (name === "settings") fillSettings();
  if (name === "history") loadHistory();
  if (name === "home" && S) renderHome();
  document.querySelector(`#v-${name}`).classList.add("fade-in");
}

// ---------- setup: dial ------------------------------------------------------------
const C = 136, R = 122;
function polar(min, r) {
  const a = (min / 1440) * 2 * Math.PI - Math.PI / 2;
  return [C + r * Math.cos(a), C + r * Math.sin(a)];
}
function drawDial() {
  const svg = $("dial-svg");
  let s = `<circle class="face" cx="${C}" cy="${C}" r="134"/>`;
  for (let h = 0; h < 24; h++) {
    const major = h % 6 === 0;
    const [x1, y1] = polar(h * 60, major ? 112 : 117);
    const [x2, y2] = polar(h * 60, 126);
    s += `<line class="tick${major ? " major" : ""}" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/>`;
    if (major) { const [lx, ly] = polar(h * 60, 98); s += `<text class="lbl" x="${lx}" y="${ly}">${pad(h)}</text>`; }
  }
  // Warning window: 45 minutes before the shutdown time.
  const start = (dialMinutes - 45 + 1440) % 1440;
  const [ax, ay] = polar(start, R), [bx, by] = polar(dialMinutes, R);
  s += `<path class="arc" d="M${ax} ${ay} A${R} ${R} 0 0 1 ${bx} ${by}"/>`;
  s += `<circle class="knob" cx="${bx}" cy="${by}" r="12"/>`;
  svg.innerHTML = s;
  $("dial-h").textContent = pad(Math.floor(dialMinutes / 60));
  $("dial-m").textContent = pad(dialMinutes % 60);
  $("dial-cap").textContent = `Warnings from ${hhmm(start)}`;
  $("dial").setAttribute("aria-valuetext", hhmm(dialMinutes));
}
function setDial(min) { dialMinutes = ((Math.round(min / 5) * 5) % 1440 + 1440) % 1440; drawDial(); }
function initDial() {
  const dial = $("dial");
  const fromPointer = e => {
    const r = dial.getBoundingClientRect();
    const x = e.clientX - r.left - r.width / 2, y = e.clientY - r.top - r.height / 2;
    let a = Math.atan2(y, x) + Math.PI / 2;
    if (a < 0) a += 2 * Math.PI;
    setDial((a / (2 * Math.PI)) * 1440);
  };
  let dragging = false;
  dial.addEventListener("pointerdown", e => { dragging = true; dial.setPointerCapture(e.pointerId); fromPointer(e); dial.focus(); });
  dial.addEventListener("pointermove", e => dragging && fromPointer(e));
  dial.addEventListener("pointerup", () => dragging = false);
  dial.addEventListener("wheel", e => {
    e.preventDefault();
    const step = e.target.id === "dial-h" ? 60 : 5;
    setDial(dialMinutes + (e.deltaY < 0 ? step : -step));
  }, { passive: false });
  dial.addEventListener("keydown", e => {
    const big = e.shiftKey || e.key.startsWith("Page") ? 60 : 5;
    if (["ArrowUp", "ArrowRight", "PageUp"].includes(e.key)) { setDial(dialMinutes + big); e.preventDefault(); }
    if (["ArrowDown", "ArrowLeft", "PageDown"].includes(e.key)) { setDial(dialMinutes - big); e.preventDefault(); }
    if (e.key === "Enter") $("setup-next").click();
  });
}

// ---------- time rows (setup + settings share one builder) ----------------------------
function buildRows(container, times, { offReadonly, onCommit, rows = ROWS }) {
  container.innerHTML = rows.map(([f, label]) => `
    <div class="row" data-field="${f}"><span class="label">${label}</span><span class="msg"></span>
      <input class="time" value="${times[f]}" ${offReadonly && f === "shutdown_time" ? "readonly tabindex=-1" : ""} maxlength="5" spellcheck="false"></div>`).join("");
  container.querySelectorAll("input.time").forEach(inp => {
    const row = inp.closest(".row");
    inp.addEventListener("keydown", e => {
      if (inp.readOnly) return;
      if (e.key === "Enter") inp.blur();
      if (e.key === "ArrowUp" || e.key === "ArrowDown") {
        const v = normalizeTime(inp.value);
        if (!v) return;
        const step = (e.shiftKey ? 60 : 5) * (e.key === "ArrowUp" ? 1 : -1);
        inp.value = hhmm((toMin(v) + step + 1440) % 1440);
        e.preventDefault();
        onCommit();
      }
    });
    inp.addEventListener("blur", () => {
      const v = normalizeTime(inp.value);
      if (v) inp.value = v;
      onCommit();
    });
  });
}
function readRows(container) {
  const out = {};
  for (const row of container.querySelectorAll(".row")) {
    const v = normalizeTime(row.querySelector("input").value);
    if (!v) return { error: { field: row.dataset.field, message: "Use HH:MM." } };
    out[row.dataset.field] = v;
  }
  return { times: out };
}
function markRows(container, err) {
  container.querySelectorAll(".row").forEach(r => {
    const bad = err && r.dataset.field === err.field;
    r.classList.toggle("error", !!bad);
    r.querySelector(".msg").textContent = bad ? err.message : "";
  });
}
async function checkRows(container, check = t => api.validate(t)) {
  const { times, error } = readRows(container);
  if (error) { markRows(container, error); return null; }
  const res = await check(times);
  markRows(container, res.ok ? null : res);
  return res.ok ? times : null;
}

// ---------- setup flow -------------------------------------------------------------
async function goSetup2() {
  setupTimes = await api.schedule_for(hhmm(dialMinutes));
  buildRows($("setup-rows"), setupTimes, { offReadonly: true, onCommit: refreshSetup2, rows: SETUP_ROWS });
  refreshTimeline(setupTimes);
  show("setup2");
}
const deriveCheck = t => api.derive(t);
async function refreshSetup2() {
  const t = await checkRows($("setup-rows"), deriveCheck);
  $("setup-finish").disabled = !t;
  if (t) refreshTimeline(t);
}
function refreshTimeline(t) {
  $("timeline").innerHTML = [["warning_1_time", "Warning"], ["curfew_time", "Curfew"], ["shutdown_time", "Off"]]
    .map(([f, l]) => `<div class="pt"><b>${t[f]}</b><i></i><span>${l}</span></div>`).join("");
}
async function finishSetup() {
  const t = await checkRows($("setup-rows"), deriveCheck);
  if (!t) return;
  const res = await api.finish_setup(t, $("setup-practice").checked);
  if (!res.ok) { markRows($("setup-rows"), res); return; }
  await refresh();
  show("home");
}

// ---------- home -------------------------------------------------------------------
const RING_LEN = 2 * Math.PI * 124;
function renderHome() {
  const s = S, ring = $("ring"), bar = $("ring-bar");
  $("practice").hidden = view.startsWith("setup") || !s.practice;
  $("s-warn").textContent = s.times.warning_1_time;
  $("s-curfew").textContent = s.times.curfew_time;
  $("s-off").textContent = s.times.shutdown_time;

  let cap = "Tonight", hero = s.times.shutdown_time, sub = "", progress = 0, cls = "", word = false, action = "";
  switch (s.mode) {
    case "armed":
      cap = s.off_day; sub = `in ${duration(s.secs_to_off)}`;
      progress = 1 - Math.min(1, s.secs_to_off / (12 * 3600));
      break;
    case "warning":
      sub = `Curfew in ${duration(s.secs_to_curfew)}`;
      progress = 1 - Math.min(1, s.secs_to_off / (12 * 3600));
      break;
    case "pending":
      cap = "Off in"; hero = clock(s.pending_left); sub = "Save your work.";
      progress = s.pending_total ? s.pending_left / s.pending_total : 0;
      if (s.pending_left <= 60) cls = "urgent";
      action = `<button class="link danger" id="act-cancel">Cancel shutdown</button>`;
      break;
    case "off":
      hero = "Off"; word = true; cls = "off"; progress = 1;
      sub = { emergency: "Emergency", cancelled: "Shutdown cancelled", skipped: "PC started after curfew", missed: "PC was off at curfew" }[s.off_reason] || "";
      if (s.can_rearm) action = `<button class="btn" id="act-rearm">Turn back on</button>`;
      break;
    case "done":
      hero = "Done"; word = true; cls = "off"; progress = 1;
      sub = s.practice ? "Practice: the PC stayed on." : `Turned off at ${s.times.shutdown_time}`;
      break;
    case "failed":
      hero = "Not off"; word = true; cls = "urgent"; progress = 1;
      sub = "Turn off the PC by hand.";
      break;
  }
  $("h-cap").textContent = cap;
  $("h-hero").textContent = hero;
  $("h-hero").classList.toggle("word", word);
  $("h-sub").textContent = sub || " ";
  ring.className = "ring " + cls;
  bar.style.strokeDasharray = RING_LEN;
  bar.style.strokeDashoffset = RING_LEN * (1 - Math.max(0, Math.min(1, progress)));

  const slot = $("h-action");
  if (slot.dataset.html !== action) {
    slot.dataset.html = action;
    slot.innerHTML = action;
    const c = $("act-cancel"), r = $("act-rearm");
    if (c) c.onclick = async () => {
      if (await sheet({ title: "Cancel tonight’s shutdown?", body: "ShutCap saves this in History.", ok: "Cancel shutdown", cancel: "Keep" })) {
        await api.cancel_shutdown(); refresh();
      }
    };
    if (r) r.onclick = async () => { await api.rearm(); refresh(); };
  }
}

// ---------- settings ---------------------------------------------------------------
function fillSettings() {
  buildRows($("set-rows"), S.times, { offReadonly: false, onCommit: saveTimes });
  markRows($("set-rows"), null);
  document.querySelectorAll("[data-set]").forEach(i => i.checked = !!S.settings[i.dataset.set]);
  $("ntfy-topic").value = S.settings.ntfy_topic || "";
  $("ntfy-row").classList.toggle("show", !!S.settings.ntfy_enabled);
  $("ver").textContent = `ShutCap ${S.version}`;
}
async function saveTimes() {
  const t = await checkRows($("set-rows"));
  if (t) { await api.save_times(t); await refresh(); }
}
function initSettings() {
  document.querySelectorAll("[data-set]").forEach(inp => inp.addEventListener("change", async () => {
    const key = inp.dataset.set;
    if (key === "dry_run" && !inp.checked) {
      inp.checked = true;
      const ok = await sheet({ title: "Turn off practice mode?", body: `ShutCap will turn off the PC at ${S.times.shutdown_time}.`, ok: "Turn off practice mode" });
      if (!ok) return;
      inp.checked = false;
    }
    await api.save_setting(key, inp.checked);
    if (key === "ntfy_enabled") $("ntfy-row").classList.toggle("show", inp.checked);
    await refresh();
  }));
  $("ntfy-topic").addEventListener("change", e => api.save_setting("ntfy_topic", e.target.value.trim()));
  $("reset-times").onclick = async () => {
    const t = await api.schedule_for(readRows($("set-rows")).times?.shutdown_time || S.times.shutdown_time);
    await api.save_times(t); await refresh(); fillSettings();
  };
  $("try-warning").onclick = () => api.test_warning();
  $("try-curfew").onclick = () => api.preview_curfew();
}

// ---------- history ----------------------------------------------------------------
async function loadHistory() {
  const days = await api.history();
  $("history-empty").hidden = days.length > 0;
  $("history-list").hidden = days.length === 0;
  $("export").disabled = $("clear").disabled = days.length === 0;
  $("history-list").innerHTML = days.map(d => `
    <div class="section-h">${d.day}</div>
    <div class="group">${d.items.map(i => `<div class="row"><span class="event-time">${i.time}</span><span class="label">${i.name}${i.detail ? `<small>${i.detail}</small>` : ""}</span></div>`).join("")}</div>`).join("");
}
function initHistory() {
  $("export").onclick = async () => {
    const r = await api.export_history();
    if (r.ok) toast("Saved", "Show", () => api.reveal(r.path));
    else if (r.ok === false) toast("Could not save the file.");
  };
  $("clear").onclick = async () => {
    if (await sheet({ title: "Clear history?", body: "You cannot undo this.", ok: "Clear" })) { await api.clear_history(); loadHistory(); }
  };
}

// ---------- state loop -------------------------------------------------------------
async function refresh() {
  S = await api.state();
  if (view === null) {
    if (S.setup_complete) show("home");
    else { setDial(toMin(S.times.shutdown_time)); show("setup1"); }
  } else if (view === "home") renderHome();
  else $("practice").hidden = view.startsWith("setup") || !S.practice;
  if (S.open_view && S.open_view !== view && S.setup_complete) show(S.open_view);
}

function init() {
  if (api) return;
  api = window.pywebview.api;
  drawDial(); initDial(); initSettings(); initHistory();
  $("setup-next").onclick = goSetup2;
  $("setup-back").onclick = () => show("setup1");
  $("setup-finish").onclick = finishSetup;
  $("go-settings").onclick = () => show("settings");
  $("go-history").onclick = () => show("history");
  $("back").onclick = () => show("home");
  $("win-min").onclick = () => api.minimize();
  $("win-close").onclick = () => api.hide();
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && !$("scrim").classList.contains("open") && (view === "settings" || view === "history")) show("home");
  });
  refresh();
  setInterval(refresh, 1000);
}
if (window.pywebview && window.pywebview.api && window.pywebview.api.state) init();
else window.addEventListener("pywebviewready", init);
