/* AllotCheck — frontend logic (vanilla JS, no build step) */
(() => {
  "use strict";
  const API = (window.APP_CONFIG && window.APP_CONFIG.apiBase) || "";
  const $ = id => document.getElementById(id);
  const PAN_RE = /^[A-Z]{5}[0-9]{4}[A-Z]$/;
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = v => { const n = Number(v); return (v !== "" && v != null && !isNaN(n)) ? n.toLocaleString("en-IN") : (v || ""); };

  /* ---- anonymous analytics beacon (never sends a PAN) ---- */
  function track(payload) {
    try {
      const body = JSON.stringify(payload);
      if (navigator.sendBeacon) navigator.sendBeacon(API + "/api/track", body);
      else fetch(API + "/api/track", { method: "POST", body, keepalive: true });
    } catch (e) { /* analytics must never break the app */ }
  }

  let REG = null;
  let registrars = [];
  let companies = [];        // [{id,name}] for the active registrar
  let selectedIpo = null;    // {id,name}

  /* ---------------- theme ---------------- */
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
  $("themeBtn").addEventListener("click", () => {
    const cur = localStorage.getItem(themeKey) || "auto";
    const next = cur === "dark" ? "light" : "dark";
    localStorage.setItem(themeKey, next); applyTheme(next);
  });

  /* ---------------- toasts ---------------- */
  function toast(msg, kind = "info", ms = 2600) {
    const el = document.createElement("div");
    el.className = "toast " + kind; el.textContent = msg;
    $("toasts").appendChild(el);
    setTimeout(() => { el.style.opacity = "0"; el.style.transition = ".3s"; setTimeout(() => el.remove(), 300); }, ms);
  }

  /* ---------------- registrar switch ---------------- */
  async function loadRegistrars() {
    try {
      registrars = await fetch(API + "/api/registrars").then(r => r.json());
      if (!Array.isArray(registrars) || !registrars.length) throw new Error("empty");
    } catch (e) {
      $("registrars").innerHTML = '<div class="state-note" style="padding:12px">Could not reach the service. If you\'re running locally, start it with run.bat.</div>';
      return;
    }
    REG = registrars[0].key;
    $("regSub").textContent = registrars.length + " supported";
    const box = $("registrars"); box.innerHTML = "";
    registrars.forEach(r => {
      const b = document.createElement("button");
      b.type = "button"; b.setAttribute("role", "tab");
      if (r.key === REG) { b.classList.add("active"); b.setAttribute("aria-selected", "true"); }
      else b.setAttribute("aria-selected", "false");
      b.dataset.reg = r.key;
      b.innerHTML = `<span>${esc(r.label)}</span>` + (r.note ? `<span class="r-note">${esc(r.note)}</span>` : "");
      b.addEventListener("click", () => {
        if (r.key === REG) return;
        REG = r.key;
        [...box.children].forEach(x => { const on = x.dataset.reg === REG; x.classList.toggle("active", on); x.setAttribute("aria-selected", on ? "true" : "false"); });
        loadCompanies();
      });
      box.appendChild(b);
    });
    loadCompanies();
  }

  /* ---------------- IPO combobox ---------------- */
  const combo = $("ipoCombo"), input = $("ipoInput"), panel = $("ipoPanel"), selBox = $("ipoSelected");
  let activeIdx = -1, filtered = [];

  function setSelected(c) {
    selectedIpo = c || null;
    if (c) {
      input.value = c.name;
      selBox.hidden = false;
      selBox.innerHTML = `<span class="tick">✓</span> Selected: <b>${esc(c.name)}</b>`;
    } else {
      selBox.hidden = true;
    }
    updateGoLabel();
  }
  function openPanel() { combo.dataset.open = "true"; input.setAttribute("aria-expanded", "true"); panel.hidden = false; }
  function closePanel() {
    combo.dataset.open = "false"; input.setAttribute("aria-expanded", "false"); panel.hidden = true;
    input.value = selectedIpo ? selectedIpo.name : "";  // reconcile free text
  }
  function renderPanel(q) {
    const term = (q || "").trim().toLowerCase();
    filtered = term ? companies.filter(c => c.name.toLowerCase().includes(term)) : companies.slice();
    if (!companies.length) { panel.innerHTML = `<div class="combo-empty">No IPOs available. Try “Refresh list”.</div>`; return; }
    if (!filtered.length) { panel.innerHTML = `<div class="combo-empty">No IPO matches “${esc(q)}”.</div>`; return; }
    activeIdx = 0;
    panel.innerHTML = filtered.map((c, i) => {
      let label = esc(c.name);
      if (term) { const idx = c.name.toLowerCase().indexOf(term); if (idx >= 0) label = esc(c.name.slice(0, idx)) + "<mark>" + esc(c.name.slice(idx, idx + term.length)) + "</mark>" + esc(c.name.slice(idx + term.length)); }
      return `<div class="combo-opt${i === 0 ? " active" : ""}" role="option" data-i="${i}">${label}</div>`;
    }).join("");
    panel.querySelectorAll(".combo-opt").forEach(o => {
      o.addEventListener("mousedown", e => { e.preventDefault(); setSelected(filtered[+o.dataset.i]); closePanel(); });
      o.addEventListener("mouseenter", () => setActive(+o.dataset.i));
    });
  }
  function setActive(i) {
    const opts = panel.querySelectorAll(".combo-opt"); if (!opts.length) return;
    activeIdx = (i + opts.length) % opts.length;
    opts.forEach((o, k) => o.classList.toggle("active", k === activeIdx));
    opts[activeIdx].scrollIntoView({ block: "nearest" });
  }
  input.addEventListener("focus", () => { renderPanel(""); openPanel(); input.select(); });
  input.addEventListener("input", () => { renderPanel(input.value); openPanel(); });
  input.addEventListener("keydown", e => {
    if (e.key === "ArrowDown") { e.preventDefault(); if (panel.hidden) { renderPanel(input.value); openPanel(); } else setActive(activeIdx + 1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive(activeIdx - 1); }
    else if (e.key === "Enter") { e.preventDefault(); if (!panel.hidden && filtered[activeIdx]) { setSelected(filtered[activeIdx]); closePanel(); } }
    else if (e.key === "Escape") { closePanel(); }
  });
  document.addEventListener("click", e => { if (!combo.contains(e.target) && combo.dataset.open === "true") closePanel(); });

  async function loadCompanies() {
    const st = $("ipoState");
    st.textContent = "loading…";
    selectedIpo = null; input.value = ""; input.placeholder = "Loading IPOs…"; selBox.hidden = true;
    panel.innerHTML = `<div class="combo-skel"><div class="skel" style="width:70%"></div><div class="skel" style="width:55%"></div><div class="skel" style="width:80%"></div></div>`;
    updateGoLabel();
    try {
      const list = await fetch(`${API}/api/${REG}/companies`).then(r => r.json());
      if (list.error) throw new Error(list.error);
      companies = Array.isArray(list) ? list : [];
      if (!companies.length) { st.innerHTML = `0 IPOs · <a href="#" id="retryIpo">retry</a>`; input.placeholder = "No active IPOs"; }
      else { st.textContent = companies.length + " IPOs"; input.placeholder = `Search ${companies.length} IPOs by name…`; }
    } catch (e) {
      companies = [];
      st.innerHTML = `unavailable · <a href="#" id="retryIpo">retry</a>`;
      input.placeholder = "Couldn't load — tap retry";
    }
    const rt = $("retryIpo"); if (rt) rt.addEventListener("click", ev => { ev.preventDefault(); loadCompanies(); });
    if (combo.dataset.open === "true") renderPanel(input.value);
  }

  /* ---------------- saved PANs ---------------- */
  const LS = "allotcheck.pans.v1";
  let saved = [];
  const AV = ["#5b57f6", "#0f9d63", "#c07d00", "#e03e4a", "#8b5cff", "#0e8fb3", "#d1568c", "#5a7d1f"];
  const avatarColor = s => { let h = 0; for (const c of s) h = (h * 31 + c.charCodeAt(0)) >>> 0; return AV[h % AV.length]; };
  const initials = (name, pan) => { if (name) { const p = name.trim().split(/\s+/); return ((p[0][0] || "") + (p[1] ? p[1][0] : "")).toUpperCase(); } return pan.slice(0, 2); };
  function loadSaved() { try { saved = JSON.parse(localStorage.getItem(LS)) || []; } catch (e) { saved = []; } if (!Array.isArray(saved)) saved = []; }
  function persist() { try { localStorage.setItem(LS, JSON.stringify(saved)); } catch (e) { toast("Couldn't save (storage blocked?)", "err"); } }
  function savedName(pan) { const m = saved.find(s => s.pan === pan); return m ? m.name : ""; }
  function syncSelAll() { const all = saved.length && saved.every(s => s.on !== false); $("selAll").checked = !!all; }

  function renderPeople() {
    const box = $("people"); box.innerHTML = "";
    $("peopleEmpty").style.display = saved.length ? "none" : "";
    saved.forEach((s, i) => {
      const div = document.createElement("div"); div.className = "person";
      div.innerHTML =
        `<input type="checkbox" class="chk" ${s.on !== false ? "checked" : ""} data-i="${i}" aria-label="Include ${esc(s.pan)}">` +
        `<span class="avatar" style="background:${avatarColor(s.name || s.pan)}">${esc(initials(s.name, s.pan))}</span>` +
        `<span class="who"><div class="nm ${s.name ? "" : "none"}">${s.name ? esc(s.name) : "No name"}</div><div class="pn">${esc(s.pan)}</div></span>` +
        `<button class="del" data-i="${i}" aria-label="Remove ${esc(s.pan)}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg></button>`;
      box.appendChild(div);
    });
    box.querySelectorAll(".chk").forEach(c => c.addEventListener("change", e => { saved[+e.target.dataset.i].on = e.target.checked; persist(); syncSelAll(); updateGoLabel(); }));
    box.querySelectorAll(".del").forEach(b => b.addEventListener("click", e => {
      const i = +e.currentTarget.dataset.i;
      if (confirm(`Remove "${saved[i].name || saved[i].pan}"?`)) { saved.splice(i, 1); persist(); renderPeople(); updateGoLabel(); }
    }));
    syncSelAll(); updateGoLabel();
  }
  function addSaved() {
    const pan = $("newPan").value.trim().toUpperCase(), name = $("newName").value.trim();
    if (!PAN_RE.test(pan)) { toast("Invalid PAN format (e.g. ABCDE1234F)", "err"); return; }
    if (saved.some(s => s.pan === pan)) { toast("That PAN is already in your list", "info"); return; }
    saved.push({ name, pan, on: true }); persist(); renderPeople();
    $("newPan").value = ""; $("newName").value = ""; $("newName").focus();
  }

  function selectedPans() {
    const fromSaved = saved.filter(s => s.on !== false).map(s => s.pan);
    const fromText = $("extraPans").value.split(/[\s,;]+/).map(s => s.trim().toUpperCase()).filter(Boolean);
    return [...new Set([...fromSaved, ...fromText])];
  }
  function updateGoLabel() {
    const n = selectedPans().length;
    const label = $("goLabel");
    if (selectedIpo && n) { const short = selectedIpo.name.length > 26 ? selectedIpo.name.slice(0, 24) + "…" : selectedIpo.name; label.textContent = `Check ${n} PAN${n > 1 ? "s" : ""} on ${short}`; }
    else if (n) label.textContent = `Check ${n} PAN${n > 1 ? "s" : ""}`;
    else label.textContent = "Check allotment";
  }

  /* ---------------- check (direct client-side when possible) ---------------- */
  const DIRECT = {
    kfintech: async (url, clientId, pan) => {
      const r = await fetch(url, { headers: { reqparam: pan, client_id: clientId } });
      if (r.status === 404) return { found: false };
      if (r.status !== 200) throw new Error("HTTP " + r.status);
      const j = await r.json();
      let d = (j && j.data !== undefined) ? j.data : j;
      if (d && d.data) d = d.data;
      const rec = Array.isArray(d) ? d[0] : (d && typeof d === "object" ? d : null);
      if (!rec) return { found: false };
      return { found: true, name: rec.Name || "", applied: rec.App_Shares || "", allotted: rec.All_Shares || "", category: "", refund: "", account: rec.DP_CLID || "" };
    }
  };
  async function checkOne(clientId, pan, attempt = 0) {
    const rd = registrars.find(r => r.key === REG) || {};
    if (attempt === 0 && rd.direct && DIRECT[rd.direct.type]) {
      try { const res = await DIRECT[rd.direct.type](rd.direct.url, clientId, pan); return res.found ? { kind: "ok", d: res } : { kind: "notfound" }; }
      catch (e) { /* fall back to server proxy */ }
    }
    try {
      const r = await fetch(`${API}/api/${REG}/check?clientid=${encodeURIComponent(clientId)}&pan=${encodeURIComponent(pan)}`).then(x => x.json());
      if (r.busy) return { kind: "busy", site: r.site || rd.site || "" };
      if (r.error) { if (attempt < 2) { await sleep(900 * (attempt + 1)); return checkOne(clientId, pan, attempt + 1); } return { kind: "error", msg: String(r.error).slice(0, 40) }; }
      return r.found ? { kind: "ok", d: r } : { kind: "notfound" };
    } catch (e) {
      if (attempt < 2) { await sleep(900 * (attempt + 1)); return checkOne(clientId, pan, attempt + 1); }
      return { kind: "error", msg: "service unreachable" };
    }
  }

  const pill = (k, t) => `<span class="pill ${k}">${t}</span>`;
  let lastRows = [];

  function applyFilter() {
    const only = $("onlyAllotted").checked;
    document.querySelectorAll("#tbl tbody tr").forEach(tr => { tr.style.display = (only && !tr.classList.contains("hit")) ? "none" : ""; });
  }

  async function run() {
    if (!selectedIpo) { toast("Search and pick an IPO first", "err"); input.focus(); return; }
    const clientId = selectedIpo.id, ipoName = selectedIpo.name;
    const pans = selectedPans();
    if (!pans.length) { toast("Add or select at least one PAN", "err"); return; }

    const tbody = document.querySelector("#tbl tbody"); tbody.innerHTML = "";
    $("resultCard").hidden = false; $("onlyAllotted").checked = false;
    $("go").disabled = true;
    $("progress").classList.add("on"); $("progressBar").style.width = "0%";
    lastRows = []; const c = { ok: 0, no: 0, err: 0, busy: 0 }; let busyHit = false;
    const regLabel = (registrars.find(r => r.key === REG) || {}).label || REG;

    for (let i = 0; i < pans.length; i++) {
      const pan = pans[i];
      $("prog").textContent = `Checking ${i + 1} of ${pans.length} — ${pan}`;
      const tr = document.createElement("tr");
      if (!PAN_RE.test(pan)) {
        tr.innerHTML = `<td class="num">${i + 1}</td><td class="mono" data-label="PAN">${esc(pan)}</td><td data-label="Status">${pill("err", "Invalid PAN")}</td><td data-label="Details" colspan="4" class="state-note">Wrong format (ABCDE1234F)</td>`;
        tbody.appendChild(tr); c.err++; lastRows.push({ pan, status: "Invalid PAN", name: "", applied: "", allotted: "", details: "" });
        $("progressBar").style.width = ((i + 1) / pans.length * 100) + "%"; continue;
      }
      tr.innerHTML = `<td class="num">${i + 1}</td><td class="mono" data-label="PAN">${esc(pan)}</td><td data-label="Status">${pill("wait", '<span class="spin"></span>checking')}</td><td colspan="4"></td>`;
      tbody.appendChild(tr);

      const myName = savedName(pan);
      const res = await checkOne(clientId, pan);
      let status = "", name = myName, applied = "", allotted = "", details = "", detailsHtml = "", badge = "", hit = false;
      if (res.kind === "ok") {
        const d = res.d; name = d.name || myName; applied = d.applied || ""; allotted = d.allotted || "";
        const bits = [];
        if (d.category) bits.push(d.category);
        if (d.refund && d.refund !== "0") bits.push("Refund ₹" + fmt(d.refund));
        if (d.account) bits.push(d.account);
        details = bits.join(" · ");
        hit = Number(allotted) > 0;
        status = hit ? "Allotted" : "Applied · not allotted";
        badge = hit ? pill("ok", "✓ Allotted") : pill("no", "Not allotted");
        hit ? c.ok++ : c.no++;
      } else if (res.kind === "notfound") { status = "Not found"; badge = pill("no", "Not found"); c.no++; }
      else if (res.kind === "busy") {
        status = "Registrar busy"; badge = pill("wait", "Busy"); c.busy++; busyHit = true;
        if (res.site) detailsHtml = `<a href="${esc(res.site)}" target="_blank" rel="noopener">Check on registrar site ↗</a>`;
      }
      else { status = res.msg || "Error"; badge = pill("err", "⚠ " + (res.msg || "Error")); c.err++; }

      if (hit) tr.classList.add("hit");
      tr.innerHTML = `<td class="num">${i + 1}</td><td class="mono" data-label="PAN">${esc(pan)}</td><td data-label="Status">${badge}</td>` +
        `<td data-label="Name">${esc(name)}</td><td class="num" data-label="Applied">${fmt(applied)}</td><td class="num" data-label="Allotted"><span class="big">${fmt(allotted)}</span></td><td class="state-note" data-label="Details">${detailsHtml || esc(details)}</td>`;
      lastRows.push({ pan, status, name, applied, allotted, details });
      $("progressBar").style.width = ((i + 1) / pans.length * 100) + "%";
      await sleep(300);
    }

    $("cOk").textContent = c.ok; $("cNo").textContent = c.no; $("cErr").textContent = c.err + c.busy;
    $("resultMeta").innerHTML = `<b>${esc(regLabel)}</b> · ${esc(ipoName)} · ${pans.length} PAN${pans.length > 1 ? "s" : ""} checked`;
    track({ type: "check_run", registrar: REG, ipo: ipoName, count: pans.length, results: { ok: c.ok, no: c.no, busy: c.busy, err: c.err } });
    $("prog").textContent = "";
    $("go").disabled = false;
    setTimeout(() => { $("progress").classList.remove("on"); $("progressBar").style.width = "0%"; }, 700);
    applyFilter();
    if (busyHit) toast(`${regLabel} is busy — some checks couldn't complete. Try again shortly.`, "err", 4200);
    else if (c.ok > 0) toast(`${c.ok} allotment${c.ok > 1 ? "s" : ""} found 🎉`, "ok");
  }

  /* ---------------- backup / export ---------------- */
  function download(name, text, type) { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; a.click(); }
  $("exportBtn").addEventListener("click", () => { download("allotcheck-pans-backup.json", JSON.stringify(saved, null, 2), "application/json"); toast("Backup saved", "ok"); });
  $("importBtn").addEventListener("click", () => $("importFile").click());
  $("importFile").addEventListener("change", e => {
    const f = e.target.files[0]; if (!f) return; const rd = new FileReader();
    rd.onload = () => {
      try {
        const arr = JSON.parse(rd.result); if (!Array.isArray(arr)) throw 0; let n = 0;
        arr.forEach(it => { const pan = (it.pan || "").toUpperCase(); if (PAN_RE.test(pan) && !saved.some(s => s.pan === pan)) { saved.push({ name: it.name || "", pan, on: it.on !== false }); n++; } });
        persist(); renderPeople(); toast(n + " PAN(s) imported", "ok");
      } catch (_) { toast("That file doesn't look like a valid backup", "err"); }
      e.target.value = "";
    };
    rd.readAsText(f);
  });
  $("csv").addEventListener("click", () => {
    const head = ["PAN", "Status", "Name", "Applied", "Allotted", "Details"];
    const rows = lastRows.map(r => [r.pan, r.status, r.name, r.applied, r.allotted, r.details].map(v => `"${String(v).replace(/"/g, '""')}"`).join(","));
    download("allotcheck-" + new Date().toISOString().slice(0, 10) + ".csv", [head.join(","), ...rows].join("\n"), "text/csv");
  });
  $("copy").addEventListener("click", () => {
    const txt = lastRows.map(r => [r.pan, r.status, r.allotted].join("\t")).join("\n");
    navigator.clipboard.writeText(txt).then(() => toast("Copied to clipboard", "ok"));
  });

  /* ---------------- wire up ---------------- */
  $("yr").textContent = new Date().getFullYear();
  loadSaved(); renderPeople(); loadRegistrars();
  // analytics: page view every load; unique visit once per day per browser
  track({ type: "pageview" });
  (() => { const t = new Date().toISOString().slice(0, 10); if (localStorage.getItem("allotcheck.lastVisit") !== t) { track({ type: "visit" }); try { localStorage.setItem("allotcheck.lastVisit", t); } catch (e) {} } })();
  $("reloadIpo").addEventListener("click", loadCompanies);
  $("addPan").addEventListener("click", addSaved);
  $("newPan").addEventListener("keydown", e => { if (e.key === "Enter") addSaved(); });
  $("newName").addEventListener("keydown", e => { if (e.key === "Enter") $("newPan").focus(); });
  $("selAll").addEventListener("change", e => { saved.forEach(s => s.on = e.target.checked); persist(); renderPeople(); });
  $("extraPans").addEventListener("input", updateGoLabel);
  $("onlyAllotted").addEventListener("change", applyFilter);
  $("go").addEventListener("click", run);
})();
