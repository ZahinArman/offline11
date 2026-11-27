// ShutCap alert window: one window that changes between warning, curfew, emergency, countdown and failed.
"use strict";

const $ = id => document.getElementById(id);
let api = null, A = null, mode = null, timerAnim = null;
const PILL_LEN = 2 * Math.PI * 18;
const pad = n => String(n).padStart(2, "0");
const clock = s => { s = Math.max(0, Math.ceil(s)); return `${Math.floor(s / 60)}:${pad(s % 60)}`; };

function activate(m) {
  mode = m;
  document.querySelectorAll(".card").forEach(c => c.classList.toggle("active", c.id === m));
  setTimeout(() => {
    const card = $(m);
    api.fit(m === "pill" ? 0 : Math.ceil(card.getBoundingClientRect().height));
  }, 30);
}

function render() {
  if (A.mode !== mode) {
    activate(A.mode);
    if (A.mode === "warning") {
      const card = $("warning");
      card.className = "card active " + (A.level || "");
      $("w-title").textContent = A.title;
      $("w-title").classList.toggle("big", A.level === "critical");
      $("w-body").textContent = A.body || "";
      $("w-badge").hidden = !A.test;
      if (timerAnim) timerAnim.cancel();
      timerAnim = $("w-timer").animate([{ transform: "scaleX(1)" }, { transform: "scaleX(0)" }], { duration: A.auto_close * 1000, easing: "linear", fill: "forwards" });
    }
    if (A.mode === "curfew") {
      $("c-body").textContent = `The PC turns off at ${A.shutdown_time}. Save your work.`;
      $("c-badge").hidden = !A.preview;
    }
    if (A.mode === "emergency") {
      $("e-badge").hidden = !A.preview;
      $("e-reason").value = ""; $("e-ok").disabled = true;
      setTimeout(() => $("e-reason").focus(), 50);
    }
  }
  if (A.mode === "pill") {
    $("p-time").textContent = clock(A.pending_left);
    const p = A.pending_total ? A.pending_left / A.pending_total : 0;
    $("p-bar").style.strokeDasharray = PILL_LEN;
    $("p-bar").style.strokeDashoffset = PILL_LEN * (1 - p);
    const urgent = A.pending_left <= 60;
    $("pill").classList.toggle("urgent", urgent);
    $("p-ring").className = "ring" + (urgent ? " urgent" : "");
    $("p-cap").textContent = A.practice ? "Off in · Practice" : "Off in";
  }
}

async function poll() {
  A = await api.alert();
  if (!A) return;
  render();
}

function init() {
  if (api) return;
  api = window.pywebview.api;
  document.querySelectorAll("[data-close]").forEach(b => b.onclick = () => api.dismiss());
  $("c-ok").onclick = () => api.accept();
  $("c-emergency").onclick = () => api.to_emergency();
  $("p-emergency").onclick = () => api.to_emergency();
  $("e-back").onclick = () => api.leave_emergency();
  $("e-reason").addEventListener("input", e => $("e-ok").disabled = !e.target.value.trim());
  $("e-ok").onclick = () => api.emergency($("e-reason").value.trim());
  $("f-retry").onclick = () => api.retry_shutdown();
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && mode === "warning") api.dismiss();
    if (e.key === "Escape" && mode === "emergency") api.leave_emergency();
  });
  poll();
  setInterval(poll, 500);
}
if (window.pywebview && window.pywebview.api && window.pywebview.api.alert) init();
else window.addEventListener("pywebviewready", init);
