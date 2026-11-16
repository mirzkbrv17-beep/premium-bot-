(() => {
"use strict";
const tg = window.Telegram && window.Telegram.WebApp;
if (tg) { tg.ready(); tg.expand(); try { tg.setHeaderColor("#08090D"); tg.setBackgroundColor("#08090D"); } catch (e) {} }
const $ = (s, r = document) => r.querySelector(s);
const view = $("#view");
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (n) => Number(n || 0).toLocaleString("ru-RU");
const state = { tab: "home", me: null, lastF: null, lastT: null };

// yengil animatsiya rejimi (qurilmada saqlanadi)
const LITE_KEY = "abu_lite";
function applyLite() { let on = false; try { on = localStorage.getItem(LITE_KEY) === "1"; } catch (e) {} document.body.classList.toggle("lite", on); return on; }
applyLite();

async function api(path, body) {
  const res = await fetch("/api" + path, {
    method: body !== undefined ? "POST" : "GET",
    headers: { "Content-Type": "application/json", "X-Init-Data": (tg && tg.initData) || "" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  let data = {};
  try { data = await res.json(); } catch (e) {}
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Xatolik yuz berdi");
  return data;
}

let toastTimer;
function toast(msg, err) {
  const t = $("#toast"); t.textContent = msg; t.className = "show" + (err ? " err" : "");
  clearTimeout(toastTimer); toastTimer = setTimeout(() => (t.className = ""), 2800);
}
const notify = (msgs) => (msgs || []).forEach((m, i) => setTimeout(() => toast(m), i * 2900));
function confirmBox(text) {
  return new Promise((ok) => (tg && tg.showConfirm ? tg.showConfirm(text, ok) : ok(window.confirm(text))));
}
function haptic(kind) { try { tg && tg.HapticFeedback && tg.HapticFeedback.notificationOccurred(kind); } catch (e) {} }

// ---------- 3D elementlar ----------
function coinHTML() {
  let slices = "";
  for (let i = -4; i <= 4; i++) slices += `<div class="slice" style="transform:translateZ(${i}px)"></div>`;
  return `<div class="coin">${slices}<div class="face front"><b>ABU</b><small>F</small></div><div class="face back"><b>ABU</b><small>F</small></div></div>`;
}
function gemHTML() {
  return `<div class="gem"><div class="face front">ABU TON</div><div class="face back">ABU TON</div></div>`;
}
function sparks() {
  let h = "";
  for (let i = 0; i < 6; i++) h += `<span class="spark" style="left:${18 + i * 13}%;bottom:${10 + (i % 3) * 14}px;animation-delay:${(i * 0.55).toFixed(2)}s"></span>`;
  return h;
}
function balanceCards(me) {
  return `<div class="balances">
    <div class="card bal f"><div class="stage"><div class="glow"></div>${coinHTML()}${sparks()}</div><div class="num" id="numF">${fmt(me.f)}</div><div class="lbl">ABU F</div></div>
    <div class="card bal t"><div class="stage"><div class="glow"></div>${gemHTML()}${sparks()}</div><div class="num" id="numT">${fmt(me.ton)}</div><div class="lbl">ABU TON</div></div></div>`;
}
function animateNumber(el, from, to) {
  if (!el) return;
  if (from === null || from === to || document.body.classList.contains("lite")) { el.textContent = fmt(to); return; }
  const start = performance.now(), dur = 900;
  el.classList.remove("bump"); void el.offsetWidth; if (to > from) el.classList.add("bump");
  (function tick(now) {
    const p = Math.min(1, (now - start) / dur), e = 1 - Math.pow(1 - p, 3);
    el.textContent = fmt(Math.round(from + (to - from) * e));
    if (p < 1) requestAnimationFrame(tick);
  })(start);
}
async function refreshMe() {
  const me = await api("/me");
  const oldF = state.me ? state.me.f : null, oldT = state.me ? state.me.ton : null;
  state.me = me;
  animateNumber($("#numF"), oldF, me.f); animateNumber($("#numT"), oldT, me.ton);
  return me;
}

// ---------- sahifalar ----------
async function home() {
  const me = await refreshMe();
  const done = me.streak > 0;
  view.innerHTML = `<div class="fade"><h1>Salom, ${esc(me.name)} 👋</h1>
    ${balanceCards(me)}
    <div class="card row between"><div><div class="muted small">ABU ID</div><b>${esc(me.abu_id)}</b></div>
      <div><span class="chip">Level ${me.level}</span> ${me.vip ? `<span class="chip v">${esc(me.vip.name)}</span>` : ""}</div></div>
    <div class="card"><div class="row between"><div><b>🔥 Streak: ${me.streak} kun</b><div class="muted small">Har kuni bonus oling</div></div>
      <button class="btn sm" data-go="bonus">${done ? "Bonus" : "Boshlash"}</button></div></div>
    <div class="card stack"><b>👥 Do'st taklif qiling</b>
      <div class="muted small">Har bir haqiqiy taklif uchun 50 ABU F + 2 ABU TON</div>
      <div class="row"><button class="btn sm grow" data-act="copyref">Havolani nusxalash</button><button class="btn sm ghost" data-act="share">Ulashish</button></div>
      <div class="muted small">Kutilmoqda: ${me.referral.pending} · Mukofotlangan: ${me.referral.rewarded}</div></div>
    <div class="card row between"><div><b>💳 Valyuta sotib olish</b><div class="muted small">Click yoki karta orqali (botda)</div></div>
      <button class="btn sm blue" data-act="closeapp">Botga o'tish</button></div></div>`;
}

async function shop() {
  const [me, data] = await Promise.all([refreshMe(), api("/shop")]);
  const packs = data.packages.filter((p) => p.currency === "ABU_TON");
  const cats = {};
  data.products.forEach((p) => (cats[p.category] = cats[p.category] || []).push(p));
  view.innerHTML = `<div class="fade"><h1>🛍 ABU SHOP</h1>${balanceCards(me)}
    <h2>ABU TON paketlari</h2>
    ${packs.map((p) => `<div class="card row between"><div class="row"><span class="blue">💎</span><div><b>${fmt(p.amount)} ABU TON</b><div class="muted small">${fmt(p.price_uzs)} so'm</div></div></div>
      <button class="btn sm blue" data-act="closeapp">Sotib olish</button></div>`).join("") || `<div class="card muted">Paketlar yo'q</div>`}
    ${Object.keys(cats).map((c) => `<h2>${esc(c)}</h2>` + cats[c].map((p) => `<div class="card"><div class="row between"><div class="grow"><b>${esc(p.name)}</b>
      <div class="muted small">${esc(p.description)}</div><div class="small">${fmt(p.price_uzs)} so'm ${p.discount ? `<span class="chip">−${p.discount}%</span>` : ""}</div></div>
      <button class="btn sm" data-buy="${p.id}" data-name="${esc(p.name)}" data-cost="${p.abu_f}" ${p.stock === 0 ? "disabled" : ""}>🪙 ${fmt(p.abu_f)}</button></div></div>`).join("")).join("") ||
      (packs.length ? "" : `<div class="card muted">Hozircha mahsulotlar yo'q.</div>`)}</div>`;
}

let mq = "", msort = "new";
async function market() {
  const list = await api(`/market?q=${encodeURIComponent(mq)}&sort=${msort}`);
  view.innerHTML = `<div class="fade"><h1>🌐 ABU MARKET</h1>
    <div class="card stack"><input id="mq" placeholder="Qidirish..." value="${esc(mq)}" maxlength="60">
      <div class="row"><select id="msort"><option value="new" ${msort === "new" ? "selected" : ""}>Yangilari</option><option value="cheap" ${msort === "cheap" ? "selected" : ""}>Arzonlari</option></select>
      <button class="btn sm" data-act="msearch">Qidirish</button></div></div>
    <button class="btn ghost" style="width:100%;margin-bottom:12px" data-act="msell">＋ E'lon qo'yish</button>
    ${list.map((l) => `<div class="card"><div class="row between"><div class="grow"><b>${esc(l.title)}</b><div class="muted small">${esc(l.description)}</div>
      <div class="small muted">Sotuvchi: ${esc(l.seller)} · ⭐ ${l.reviews ? l.rating : "—"} (${l.reviews})</div></div>
      ${l.mine ? `<span class="chip">Sizniki</span>` : `<button class="btn sm" data-mbuy="${l.id}" data-name="${esc(l.title)}" data-cost="${l.price}">🪙 ${fmt(l.price)}</button>`}</div></div>`).join("") ||
      `<div class="card muted">E'lonlar topilmadi.</div>`}</div>`;
}
function sellForm() {
  view.innerHTML = `<div class="fade"><h1>＋ Yangi e'lon</h1><div class="card stack">
    <input id="st" placeholder="Nomi" maxlength="100"><input id="sp" type="number" inputmode="numeric" min="1" placeholder="Narx (ABU F)">
    <textarea id="sd" placeholder="Tavsif" maxlength="500"></textarea>
    <div class="muted small">E'lon admin tasdig'idan keyin chiqadi.</div>
    <div class="row"><button class="btn grow" data-act="msubmit">Yuborish</button><button class="btn ghost" data-act="mback">Bekor</button></div></div></div>`;
}

async function bonus() {
  const [b, tasks] = await Promise.all([api("/bonus"), api("/tasks")]);
  const days = [1, 3, 7, 14, 30];
  view.innerHTML = `<div class="fade"><h1>🎁 Bonuslar</h1><div class="card">
    <div class="row between"><div><b>Kunlik bonus</b><div class="muted small">Ketma-ket kirish: ${b.streak} kun</div></div><div class="gold" style="font-size:22px;font-weight:800">+${b.base}</div></div>
    <div class="streak">${days.map((d) => `<div class="dot ${b.streak >= d ? "on" : ""}">${d}<br>kun${b.milestones[d] ? `<br>+${b.milestones[d]}` : ""}</div>`).join("")}</div>
    <button class="btn" style="width:100%" data-act="claim" ${b.claimed_today ? "disabled" : ""}>${b.claimed_today ? "Bugun olingan ✅" : "Bonusni olish"}</button></div>
    <h2>Topshiriqlar</h2>
    ${tasks.map((t) => `<div class="card"><div class="row between"><div class="grow"><b>${esc(t.title)}</b><div class="muted small">${esc(t.description)}</div>
      <div class="small gold">${t.reward_f ? "+" + t.reward_f + " ABU F " : ""}${t.reward_ton ? "+" + t.reward_ton + " ABU TON" : ""} · ${t.repeat === "daily" ? "har kuni" : "bir marta"}</div></div>
      ${t.done ? `<span class="chip">✅</span>` : `<div class="stack">${t.kind === "channel" && t.channel ? `<button class="btn sm ghost" data-link="https://t.me/${esc(t.channel.replace("@", ""))}">Kanal</button>` : ""}<button class="btn sm" data-task="${t.id}">Tekshirish</button></div>`}</div></div>`).join("") || `<div class="card muted">Hozircha topshiriq yo'q.</div>`}</div>`;
}

let histTab = "tx";
async function cabinet() {
  const [me, h] = await Promise.all([refreshMe(), api("/history")]);
  const pct = Math.max(0, Math.min(100, ((me.xp - me.level_base) / (me.level_next - me.level_base)) * 100));
  const lite = document.body.classList.contains("lite");
  const tx = h.transactions.map((t) => `<div class="list-item row between"><div><div>${esc(t.kind)}</div><div class="muted small">${esc(t.at.slice(0, 16).replace("T", " "))}</div></div>
    <b class="${t.amount > 0 ? "plus" : "minus"}">${t.amount > 0 ? "+" : ""}${fmt(t.amount)} ${t.currency === "ABU_F" ? "F" : "TON"}</b></div>`).join("");
  const ord = h.orders.map((o) => `<div class="list-item row between"><div>🛍 ${esc(o.name)}<div class="muted small">#${o.id} · ${esc(o.status)}</div></div><b>${fmt(o.abu_f)} F</b></div>`).join("") +
    h.market.map((o) => `<div class="list-item row between"><div>🌐 ${esc(o.title)}<div class="muted small">#${o.id} · ${o.role === "buyer" ? "xarid" : "sotuv"} · ${esc(o.status)}</div></div><b>${fmt(o.abu_f)} F</b></div>`).join("");
  view.innerHTML = `<div class="fade"><h1>Kabinet</h1>
    <div class="card"><div class="row"><div class="avatar">${esc((me.name || "?").charAt(0).toUpperCase())}</div><div class="grow"><b>${esc(me.name)}</b>
      <div class="muted small">${me.username ? "@" + esc(me.username) : ""} · ${esc(me.abu_id)}</div><div class="muted small">Ro'yxatdan o'tgan: ${esc(me.joined)}</div></div></div>
      <div style="margin-top:14px" class="row between"><span class="chip">Level ${me.level}</span>${me.vip ? `<span class="chip v">👑 ${esc(me.vip.name)} · −${me.vip.discount}%</span>` : `<span class="muted small">VIP yo'q</span>`}</div>
      <div class="bar" style="margin-top:10px"><i style="width:${pct}%"></i></div><div class="muted small" style="margin-top:6px">${fmt(me.xp)} / ${fmt(me.level_next)} XP · 🏅 ${me.achievements.have}/${me.achievements.total}</div></div>
    ${balanceCards(me)}
    <h2>Promo kod</h2><div class="card row"><input id="promo" placeholder="KOD" maxlength="32" autocapitalize="characters"><button class="btn" data-act="promo">Qo'llash</button></div>
    <h2>Tarix</h2><div class="tabs"><button class="btn sm ${histTab === "tx" ? "" : "ghost"}" data-htab="tx">Tranzaksiyalar</button><button class="btn sm ${histTab === "ord" ? "" : "ghost"}" data-htab="ord">Buyurtmalar</button></div>
    <div class="card">${(histTab === "tx" ? tx : ord) || `<div class="muted">Hozircha bo'sh</div>`}</div>
    <h2>Sozlamalar</h2><div class="card row between"><div><b>Yengil animatsiya</b><div class="muted small">Telefonni tejaydi</div></div><button class="btn sm ${lite ? "" : "ghost"}" data-act="lite">${lite ? "Yoqilgan" : "O'chiq"}</button></div></div>`;
}

const pages = { home, shop, market, bonus, cabinet };
async function go(tab) {
  state.tab = tab;
  document.querySelectorAll("nav button").forEach((b) => b.classList.toggle("on", b.dataset.tab === tab));
  try { await pages[tab](); } catch (e) {
    view.innerHTML = `<div class="card fade"><b>Xatolik</b><div class="muted small" style="margin-top:6px">${esc(e.message)}</div></div>`;
  }
  window.scrollTo(0, 0);
}

// ---------- hodisalar ----------
document.addEventListener("click", async (ev) => {
  const el = ev.target.closest("button"); if (!el) return;
  const d = el.dataset;
  try {
    if (d.tab) return go(d.tab);
    if (d.go) return go(d.go);
    if (d.link) return tg && tg.openTelegramLink ? tg.openTelegramLink(d.link) : window.open(d.link, "_blank");
    if (d.htab) { histTab = d.htab; return cabinet(); }
    if (d.buy) {
      if (!(await confirmBox(`${d.name} — ${fmt(d.cost)} ABU F. Sotib olasizmi?`))) return;
      const r = await api("/shop/buy", { id: +d.buy }); haptic("success"); toast("✅ Buyurtma qabul qilindi!"); notify(r.messages); return shop();
    }
    if (d.mbuy) {
      if (!(await confirmBox(`${d.name} — ${fmt(d.cost)} ABU F. Pul escrowda saqlanadi. Davom etamizmi?`))) return;
      await api("/market/buy", { id: +d.mbuy }); haptic("success"); toast("✅ Buyurtma yaratildi. Botda davom eting."); return market();
    }
    if (d.task) { const r = await api(`/tasks/${d.task}/check`, {}); haptic("success"); toast("✅ Topshiriq bajarildi!"); notify(r.messages); return bonus(); }
    switch (d.act) {
      case "copyref": { const l = state.me.referral.link; if (!l) return toast("Havola topilmadi", true);
        try { await navigator.clipboard.writeText(l); toast("Nusxalandi ✅"); } catch (e) { toast(l); } return; }
      case "share": { const l = state.me.referral.link; if (!l) return; const u = "https://t.me/share/url?url=" + encodeURIComponent(l); return tg && tg.openTelegramLink ? tg.openTelegramLink(u) : window.open(u, "_blank"); }
      case "closeapp": return tg ? tg.close() : toast("Botga o'ting");
      case "claim": { const r = await api("/bonus/claim", {}); haptic("success"); toast(`🎁 +${r.reward} ABU F · ${r.streak}-kun`); notify(r.messages); return bonus(); }
      case "msearch": mq = $("#mq").value.trim(); msort = $("#msort").value; return market();
      case "msell": return sellForm();
      case "mback": return market();
      case "msubmit": { const price = parseInt($("#sp").value, 10);
        await api("/market/listings", { title: $("#st").value.trim(), price, description: $("#sd").value.trim() });
        toast("✅ E'lon moderatsiyaga yuborildi"); return market(); }
      case "promo": { const code = $("#promo").value.trim(); if (!code) return;
        const r = await api("/promo/redeem", { code }); haptic("success"); toast(`🎉 +${fmt(r.amount)} ${r.currency === "ABU_F" ? "ABU F" : "ABU TON"}`); return cabinet(); }
      case "lite": { let on = false; try { on = localStorage.getItem(LITE_KEY) === "1"; localStorage.setItem(LITE_KEY, on ? "0" : "1"); } catch (e) {} applyLite(); return cabinet(); }
    }
  } catch (e) { haptic("error"); toast(e.message || "Xatolik", true); }
});

if (!tg || !tg.initData) {
  view.innerHTML = `<div class="card" style="margin-top:20vh;text-align:center"><b>ABU</b><div class="muted small" style="margin-top:8px">Iltimos, Mini App'ni Telegram ichida oching.</div></div>`;
} else { go("home"); }
})();
