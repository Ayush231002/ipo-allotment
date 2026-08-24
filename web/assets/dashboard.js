/* AllotCheck — IPO Intelligence dashboard (vanilla JS, no build) */
(() => {
  "use strict";
  const API = (window.APP_CONFIG && window.APP_CONFIG.apiBase) || "";
  const $ = id => document.getElementById(id);
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const nfmt = n => Number(n || 0).toLocaleString("en-IN");

  /* theme (shared behaviour with the checker) */
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

  const ICON = {
    running: '<path d="M13 2L3 14h7l-1 8 10-12h-7z"/>',
    upcoming: '<path d="M12 6v6l4 2"/><circle cx="12" cy="12" r="9"/>',
    closed: '<path d="M20 7L9 18l-5-5"/>',
    listed: '<path d="M3 17l6-6 4 4 8-8"/><path d="M14 7h7v7"/>',
    indexed: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18"/>',
    closing: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    allot: '<path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>',
    listing: '<path d="M23 6l-9.5 9.5-5-5L1 18"/><path d="M17 6h6v6"/>',
    gmp: '<path d="M3 3v18h18"/><path d="M7 14l3-4 3 3 5-6"/>',
    peak: '<path d="M3 20h18"/><path d="M7 20l4-11 3 6 3-8 4 13"/>',
  };
  function ovCard(icon, n, label, sub, awaiting) {
    const val = awaiting ? "Awaiting data" : nfmt(n);
    return `<div class="ov-card${awaiting ? " awaiting" : ""}">
      <div class="ov-top"><span class="ov-l">${esc(label)}</span>
        <span class="ov-ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICON[icon] || ""}</svg></span></div>
      <div class="ov-n">${val}</div>${sub ? `<div class="ov-sub">${esc(sub)}</div>` : ""}</div>`;
  }

  async function loadDashboard() {
    let d;
    try { d = await fetch(`${API}/api/v1/dashboard`).then(r => r.json()); }
    catch (e) { $("ovGrid").innerHTML = `<div class="state-note" style="padding:14px">Couldn't reach the intelligence service.</div>`; return; }
    const c = d.counts || {};
    // Market classification (running/upcoming/etc.) lands in Phase 2. Until any
    // dated metadata exists, show those as "Awaiting data" rather than a bare 0.
    const noMarket = !d.market_data_available;
    const t = d.today || {};
    $("ovGrid").innerHTML =
      ovCard("running", c.running, "Running IPOs", d.as_of ? "as of " + d.as_of : "", noMarket && !c.running) +
      ovCard("upcoming", c.upcoming, "Upcoming", "", noMarket && !c.upcoming) +
      ovCard("closing", t.closing_today, "Closing today", "", noMarket && !t.closing_today) +
      ovCard("allot", t.allotment_today, "Allotment today", "", noMarket && !t.allotment_today) +
      ovCard("listing", t.listing_today, "Listing today", "", noMarket && !t.listing_today) +
      ovCard("closed", c.closed, "Closed", "awaiting listing", noMarket && !c.closed) +
      ovCard("listed", c.listed, "Recently listed", "", noMarket && !c.listed) +
      ovCard("indexed", c.indexed_total, "IPOs indexed", "identity records", false);

    // GMP summary (unofficial — clearly labelled)
    const g = d.gmp || {};
    let gmpCards = ovCard("gmp", g.active_count, "Active GMP", "unofficial", !g.active_count);
    if (g.highest) {
      gmpCards += `<div class="ov-card"><div class="ov-top"><span class="ov-l">Highest GMP</span>
        <span class="ov-ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICON.peak}</svg></span></div>
        <div class="ov-n">₹${nfmt(g.highest.gmp)}</div>
        <div class="ov-sub"><a href="/ipo/${encodeURIComponent(g.highest.slug)}">${esc(g.highest.name)}</a></div></div>`;
    } else {
      gmpCards += ovCard("peak", 0, "Highest GMP", "unofficial", true);
    }
    $("ovGrid").insertAdjacentHTML("beforeend", gmpCards);
  }

  async function loadDataQuality() {
    try {
      const d = await fetch(`${API}/api/v1/data-quality`).then(r => r.json());
      const srcs = d.sources || [];
      const official = srcs.filter(s => s.type === "official").length;
      const issues = d.validation_issues || {};
      $("dqStrip").innerHTML =
        `<span class="dq-pill official"><b>${official}</b> official sources</span>` +
        `<span class="dq-pill manual">Admin-entered where noted</span>` +
        (issues.error ? `<span class="dq-pill" style="color:var(--danger)"><b>${issues.error}</b> validation errors</span>` : "") +
        `<span class="updated"><span class="dot"></span>Every metric carries a source &amp; timestamp</span>`;
    } catch (e) { /* non-critical */ }
  }

  /* IPO directory */
  let status = "", q = "", tmr = null;
  const badge = s => `<span class="badge ${esc(s || "unclassified")}">${esc(s || "unclassified")}</span>`;

  function ipoRow(it) {
    const meta = [];
    meta.push(badge(it.status));
    if (it.board && it.board !== "unknown") meta.push(esc(it.board));
    if (it.registrar_key) meta.push(esc(it.registrar_key.toUpperCase()));
    if (it.open_date) meta.push("Opens " + esc(it.open_date));
    return `<a class="ipo-row" href="/ipo/${encodeURIComponent(it.slug)}">
      <span class="ir-main"><div class="ir-name">${esc(it.name)}</div>
        <div class="ir-meta">${meta.join("")}</div></span>
      <span class="chev"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M9 6l6 6-6 6"/></svg></span></a>`;
  }

  async function loadList() {
    const box = $("ipoList"), empty = $("listEmpty");
    box.innerHTML = `<div class="skel" style="height:64px"></div><div class="skel" style="height:64px"></div><div class="skel" style="height:64px"></div>`;
    empty.hidden = true;
    let d;
    try {
      const url = `${API}/api/v1/ipos?limit=100&status=${encodeURIComponent(status)}&q=${encodeURIComponent(q)}`;
      d = await fetch(url).then(r => r.json());
    } catch (e) { box.innerHTML = ""; empty.hidden = false; empty.textContent = "Couldn't load IPOs. Please try again."; return; }
    const items = d.items || [];
    $("dirCount").textContent = items.length ? `${items.length} shown` : "";
    if (!items.length) {
      box.innerHTML = "";
      empty.hidden = false;
      empty.textContent = q
        ? `No IPOs match “${q}”.`
        : (status ? `No ${status} IPOs indexed yet. Market classification is populated by the Phase 2 pipeline.`
                  : "No IPOs indexed yet.");
      return;
    }
    box.innerHTML = items.map(ipoRow).join("");
  }

  $("filters").addEventListener("click", e => {
    const b = e.target.closest(".fchip"); if (!b) return;
    status = b.dataset.status;
    [...$("filters").children].forEach(x => x.classList.toggle("active", x === b));
    loadList();
  });
  $("search").addEventListener("input", e => {
    q = e.target.value.trim();
    clearTimeout(tmr); tmr = setTimeout(loadList, 220);
  });

  loadDataQuality();
  loadDashboard();
  loadList();
})();
