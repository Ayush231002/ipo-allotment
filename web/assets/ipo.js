/* AllotCheck — IPO detail page (vanilla JS, no build) */
(() => {
  "use strict";
  const API = (window.APP_CONFIG && window.APP_CONFIG.apiBase) || "";
  const $ = id => document.getElementById(id);
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = v => { const n = Number(v); return (v !== "" && v != null && !isNaN(n)) ? n.toLocaleString("en-IN") : (v || ""); };

  /* theme */
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

  const slug = decodeURIComponent(location.pathname.replace(/^\/ipo\//, "").replace(/\/+$/, ""));

  const val = (v, suffix) => (v === null || v === undefined || v === "")
    ? `<span class="v none">—</span>`
    : `<span class="v">${esc(fmt(v))}${suffix ? " " + suffix : ""}</span>`;
  const kv = (k, v, suffix) => `<div class="kv"><span class="k">${esc(k)}</span>${val(v, suffix)}</div>`;

  function provenance(m) {
    if (!m || !m.available) return "";
    const bits = [];
    if (m.source) bits.push(`<span class="src">Source: ${esc(m.source)}</span>`);
    if (m.captured_at) bits.push(`Updated ${esc(m.captured_at)}`);
    return bits.length ? `<div class="provenance">${bits.join(" · ")}</div>` : "";
  }
  function emptyMetric(reason) {
    return `<div class="metric-empty">
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></svg>
      ${esc(reason || "Data unavailable.")}</div>`;
  }

  function priceBand(ipo) {
    if (ipo.price_min == null && ipo.price_max == null) return null;
    if (ipo.price_min != null && ipo.price_max != null) return `₹${fmt(ipo.price_min)} – ₹${fmt(ipo.price_max)}`;
    return `₹${fmt(ipo.price_min != null ? ipo.price_min : ipo.price_max)}`;
  }

  function render(d) {
    const ipo = d.ipo;
    const band = priceBand(ipo);
    const checkHref = ipo.registrar_key && ipo.registrar_client_id
      ? `/?registrar=${encodeURIComponent(ipo.registrar_key)}&ipo=${encodeURIComponent(ipo.registrar_client_id)}`
      : "/";

    const sub = d.subscription, gmp = d.gmp, lst = d.listing, est = d.listing_estimate;

    $("content").innerHTML = `
      <div class="detail-head">
        <h1>${esc(ipo.name)}</h1>
        <span class="badge ${esc(ipo.status || "unclassified")}">${esc(ipo.status || "unclassified")}</span>
      </div>
      <div class="detail-sub">
        ${ipo.board && ipo.board !== "unknown" ? `<span>${esc(ipo.board)}</span>` : ""}
        ${ipo.registrar_key ? `<span>Registrar: ${esc(ipo.registrar_key.toUpperCase())}</span>` : ""}
        ${ipo.exchange ? `<span>${esc(ipo.exchange)}</span>` : ""}
        ${ipo.sector ? `<span>${esc(ipo.sector)}</span>` : ""}
      </div>

      <div class="card section">
        <h2>Overview</h2>
        <div class="kv-grid">
          ${kv("Price band", band)}
          ${kv("Lot size", ipo.lot_size)}
          ${kv("Issue size", ipo.issue_size_cr, "Cr")}
          ${kv("Open date", ipo.open_date)}
          ${kv("Close date", ipo.close_date)}
          ${kv("Allotment date", ipo.allotment_date)}
          ${kv("Listing date", ipo.listing_date)}
        </div>
        ${(band == null || ipo.lot_size == null) ? `<p class="phase-note" style="margin-top:12px">Verified issue metadata is populated by the Phase 2 data pipeline or admin entry. Fields shown as “—” are awaiting a verified source.</p>` : ""}
      </div>

      <div class="card section">
        <h2>Subscription</h2>
        ${sub.available ? `<div class="kv-grid">
          ${kv("Overall", sub.value.overall_x, "x")}
          ${kv("QIB", sub.value.qib_x, "x")}
          ${kv("NII / HNI", sub.value.nii_x, "x")}
          ${kv("Retail", sub.value.retail_x, "x")}
        </div>${provenance(sub)}` : emptyMetric(sub.reason)}
      </div>

      <div class="card section">
        <h2>Grey Market Premium (GMP)</h2>
        ${gmp.available ? `<div class="kv-grid">
          ${kv("Current GMP", gmp.value.gmp, "₹")}
          ${kv("GMP %", gmp.value.gmp_pct, "%")}
        </div>${provenance(gmp)}` : emptyMetric(gmp.reason)}
        <div class="disclaimer-box">${esc(d.gmp_disclaimer)}</div>
      </div>

      <div class="card section">
        <h2>Listing estimate</h2>
        ${est.available ? "" : emptyMetric(est.reason)}
        <p class="phase-note" style="margin-top:10px">A transparent, weighted estimate range (GMP + subscription + institutional demand + market sentiment + comparable IPOs) arrives in Phase 5. It will always be shown as a probable range with a confidence level — never a guaranteed prediction.</p>
      </div>

      <div class="card section">
        <h2>Listing performance</h2>
        ${lst.available ? `<div class="kv-grid">
          ${kv("Listing price", lst.value.listing_price, "₹")}
          ${kv("Day high", lst.value.day_high, "₹")}
          ${kv("Day low", lst.value.day_low, "₹")}
          ${kv("Listing gain", lst.value.listing_gain_pct, "%")}
        </div>${provenance(lst)}` : emptyMetric(lst.reason)}
      </div>

      <div class="card section">
        <h2>Check allotment</h2>
        <p class="state-note" style="margin:0 0 12px">Check this IPO across all your saved PANs — privately, in your browser.</p>
        <a class="btn btn-primary" href="${checkHref}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
          Open allotment checker
        </a>
      </div>

      <p class="disclaimer" style="margin-top:18px">AllotCheck is independent and not affiliated with any registrar, exchange or issuer. Data is shown with its source and timestamp; unavailable data is labelled, not fabricated. Nothing here is investment advice.</p>`;
  }

  async function load() {
    if (!slug) { $("content").innerHTML = `<div class="card"><p class="state-note">No IPO specified.</p></div>`; return; }
    let r;
    try { r = await fetch(`${API}/api/v1/ipos/${encodeURIComponent(slug)}`); }
    catch (e) { $("content").innerHTML = `<div class="card"><p class="state-note">Couldn't reach the service.</p></div>`; return; }
    if (r.status === 404) {
      $("content").innerHTML = `<div class="card"><h2 style="margin-top:0">IPO not found</h2>
        <p class="state-note">This IPO isn't in the index yet. <a href="/dashboard">Browse the directory →</a></p></div>`;
      return;
    }
    if (!r.ok) { $("content").innerHTML = `<div class="card"><p class="state-note">Something went wrong (${r.status}).</p></div>`; return; }
    render(await r.json());
  }
  load();
})();
