/* AllotCheck admin dashboard */
(() => {
  "use strict";
  const API = (window.APP_CONFIG && window.APP_CONFIG.apiBase) || "";
  const $ = id => document.getElementById(id);
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const nfmt = n => Number(n || 0).toLocaleString("en-IN");
  const TOKKEY = "allotcheck.admintoken";
  let days = 14;

  /* theme (shared with app) */
  const themeKey = "allotcheck.theme";
  function applyTheme(t) {
    if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t);
    else document.documentElement.removeAttribute("data-theme");
    const dark = t === "dark" || (t !== "light" && matchMedia("(prefers-color-scheme: dark)").matches);
    $("themeIcon").innerHTML = dark
      ? '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>'
      : '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>';
  }
  applyTheme(localStorage.getItem(themeKey) || "auto");
  $("themeBtn").addEventListener("click", () => { const cur = localStorage.getItem(themeKey) || "auto"; const next = cur === "dark" ? "light" : "dark"; localStorage.setItem(themeKey, next); applyTheme(next); });

  const flag = cc => (cc && cc.length === 2 && /[A-Z]{2}/.test(cc)) ? cc.replace(/./g, c => String.fromCodePoint(127397 + c.charCodeAt(0))) : "🏳️";
  const REGLABEL = { kfintech: "KFintech", mufg: "MUFG / Intime" };

  async function fetchStats(token) {
    // Token goes in a header, never the URL (query strings leak into logs/history).
    const r = await fetch(`${API}/api/admin/stats?days=${days}`, { headers: { "x-admin-token": token } });
    if (r.status === 401) throw new Error("unauthorized");
    if (r.status === 503) throw new Error("disabled");
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }

  function showLogin(msg) {
    $("login").hidden = false; $("dash").hidden = true; $("rangeSel").hidden = true; $("logout").hidden = true;
    if (msg) $("loginErr").textContent = msg;
  }

  async function enter(token) {
    try {
      const data = await fetchStats(token);
      sessionStorage.setItem(TOKKEY, token);
      $("login").hidden = true; $("dash").hidden = false; $("rangeSel").hidden = false; $("logout").hidden = false;
      render(data);
    } catch (e) {
      const m = String(e.message);
      if (m === "unauthorized") showLogin("Wrong token. Try again.");
      else if (m === "disabled") showLogin("Admin dashboard is disabled — no token is configured on the server.");
      else showLogin("Couldn't load stats. Is the server running?");
    }
  }

  function kpi(n, l, sub) { return `<div class="kpi"><div class="n">${nfmt(n)}</div><div class="l">${esc(l)}</div>${sub ? `<div class="sub">${esc(sub)}</div>` : ""}</div>`; }

  function render(d) {
    $("rangeLbl").textContent = d.range_days;
    const w = d.window, today = d.today || {};
    $("kpis").innerHTML =
      kpi(w.visits, "Unique visitors", `${nfmt(today.visits)} today`) +
      kpi(w.pageviews, "Page views", `${nfmt(today.pageviews)} today`) +
      kpi(w.checks, "Checks run", `${nfmt(today.checks)} today`) +
      kpi(w.pans, "PANs checked", `all-time ${nfmt(d.totals.pans)}`);

    // trend bars (unique visits + pageviews)
    const maxv = Math.max(1, ...d.series.map(p => Math.max(p.pageviews, p.visits)));
    $("trend").innerHTML = d.series.map(p => {
      const dd = p.date.slice(5);
      return `<div class="col" title="${p.date}: ${p.visits} visitors, ${p.pageviews} views, ${p.checks} checks">
        <div style="display:flex; gap:2px; align-items:flex-end; width:100%; justify-content:center; height:120px">
          <div class="bar pv" style="height:${(p.pageviews / maxv * 100).toFixed(1)}%"></div>
          <div class="bar" style="height:${(p.visits / maxv * 100).toFixed(1)}%"></div>
        </div>
        <div class="lbl">${dd}</div></div>`;
    }).join("");

    // registrar health
    const rt = $("regTbl").querySelector("tbody");
    const regs = Object.entries(d.registrars);
    rt.innerHTML = regs.length ? regs.map(([k, r]) => {
      const total = r.checks || 1;
      const bad = (r.busy + r.err);
      const rate = (r.busy + r.err) / Math.max(1, (r.ok + r.no + r.busy + r.err));
      const cls = rate > 0.25 ? "bad" : rate > 0.08 ? "warn" : "good";
      const txt = rate > 0.25 ? "At risk" : rate > 0.08 ? "Watch" : "Healthy";
      return `<tr><td>${esc(REGLABEL[k] || k)}</td><td class="num">${nfmt(r.checks)}</td><td class="num">${nfmt(r.ok)}</td><td class="num">${nfmt(bad)}</td><td><span class="health ${cls}">${txt} · ${(rate * 100).toFixed(0)}%</span></td></tr>`;
    }).join("") : `<tr><td colspan="5" class="state-note">No checks yet.</td></tr>`;

    // devices
    const dev = d.device || {}; const devTot = Object.values(dev).reduce((a, b) => a + b, 0) || 1;
    const devOrder = ["desktop", "mobile", "tablet"];
    $("devices").innerHTML = devOrder.filter(k => dev[k]).map(k =>
      `<div class="rowbar"><span class="k">${k[0].toUpperCase() + k.slice(1)}</span><span class="track"><span class="fill" style="width:${(dev[k] / devTot * 100).toFixed(0)}%"></span></span><span class="v">${(dev[k] / devTot * 100).toFixed(0)}%</span></div>`
    ).join("") || `<div class="state-note">No data yet.</div>`;

    // countries
    const cmax = Math.max(1, ...d.country.map(c => c.count));
    $("countries").innerHTML = d.country.length ? d.country.map(c =>
      `<div class="rowbar"><span class="k">${flag(c.key)} ${esc(c.key)}</span><span class="track"><span class="fill" style="width:${(c.count / cmax * 100).toFixed(0)}%"></span></span><span class="v">${nfmt(c.count)}</span></div>`
    ).join("") : `<div class="state-note">No data yet.</div>`;

    // top IPOs
    const imax = Math.max(1, ...d.top_ipos.map(i => i.count));
    $("ipos").innerHTML = d.top_ipos.length ? d.top_ipos.map(i =>
      `<div class="rowbar"><span class="k" title="${esc(i.ipo)}">${esc(i.ipo)}</span><span class="track"><span class="fill" style="width:${(i.count / imax * 100).toFixed(0)}%"></span></span><span class="v">${nfmt(i.count)}</span></div>`
    ).join("") : `<div class="state-note">No checks yet.</div>`;
  }

  // range selector
  $("rangeSel").addEventListener("click", e => {
    const b = e.target.closest("button[data-d]"); if (!b) return;
    days = +b.dataset.d;
    [...$("rangeSel").children].forEach(x => x.classList.toggle("active", x === b));
    const t = sessionStorage.getItem(TOKKEY); if (t) enter(t);
  });
  $("logout").addEventListener("click", () => { sessionStorage.removeItem(TOKKEY); showLogin(""); });
  $("loginBtn").addEventListener("click", () => enter($("tokenInput").value.trim()));
  $("tokenInput").addEventListener("keydown", e => { if (e.key === "Enter") enter($("tokenInput").value.trim()); });

  // auto-enter if token remembered
  const saved = sessionStorage.getItem(TOKKEY);
  if (saved) enter(saved); else showLogin("");
})();
