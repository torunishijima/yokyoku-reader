"use strict";

const DATA = "data/yokyoku/";
const app = document.getElementById("app");

let index = null;
const cache = new Map();
const listState = { q: "", series: "すべて", season: "", taikanOnly: false };

/* ---------- 共通 ---------- */

function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function fetchText(path) {
  if (cache.has(path)) return cache.get(path);
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path} を読み込めませんでした（${res.status}）`);
  const text = await res.text();
  cache.set(path, text);
  return text;
}

async function loadIndex() {
  if (!index) index = JSON.parse(await fetchText(DATA + "index.json"));
  return index;
}

// 検索用に旧字・異体字をそろえる（表示は底本のまま）
const VARIANTS = { "龍": "竜", "經": "経", "戀": "恋", "櫻": "桜", "鐵": "鉄", "國": "国", "實": "実", "與": "与", "鬪": "闘", "髙": "高" };
function norm(s) {
  return (s || "").replace(/./g, c => VARIANTS[c] || c);
}

/* ---------- 原文の解析 ---------- */

// 役名表記から色分け用の役を推定する。表示には底本の表記をそのまま使う。
function roleOf(label, prev) {
  if (!label) return prev;
  if (/^(二人|三人|同吟)/.test(label) || /二人|三人/.test(label)) return "同吟";
  if (/^(後|前)?シテツレ/.test(label)) return "ツレ";
  if (/^(後|前)?シテ/.test(label)) return "シテ";
  if (/^ワキツレ/.test(label)) return "ワキツレ";
  if (/^ワキ/.test(label)) return "ワキ";
  if (/^(ツレ|トモ)/.test(label)) return "ツレ";
  if (/^子(方)?/.test(label)) return "子方";
  if (/^(地|ロンギ地|キリ地|クセ地)/.test(label) || /^[^「]*地$/.test(label)) return "地";
  if (/^(狂言|アイ|間|中入間|来序中入間|本間|替間)/.test(label)) return "アイ";
  // 小段名だけの表記は直前の話者が続いているものとみなす
  if (/^(詞|サシ|上歌|下歌|歌|上|下|次第|一セイ|一声|セイ|クリ|クセ|ロンギ|キリ|道行|ワカ|ノリ|待謡|名ノリ|カカル|呼掛|上ゲ歌|下ゲ歌|二ノ句|中ノリ|大ノリ)/.test(label)) return prev;
  return "その他";
}

// 半魚文庫のテキストを発言の配列にする。行頭「役名「」で新しい発言、それ以外の行（改ページ等）は直前の発言につなぐ。
function parseUtterances(body, prevRole, prevLabel) {
  const out = [];
  let role = prevRole || null;
  for (const raw of body.split("\n")) {
    const line = raw.replace(/\s+$/, "");
    if (!line.trim()) continue;
    const m = line.match(/^([^「」。、\s]{1,14})「(.*)$/);
    if (m) {
      role = roleOf(m[1], role);
      out.push({ label: m[1], role, text: m[2] });
    } else if (out.length) {
      out[out.length - 1].text += line.trim();
    } else {
      out.push({ label: prevLabel ? prevLabel + "（続き）" : null, role, text: line.trim() });
    }
  }
  return out;
}

function splitHeader(text) {
  const i = text.indexOf("――――");
  return i < 0 ? { head: "", body: text } : { head: text.slice(0, i), body: text.slice(i + 4) };
}

/* ---------- 一覧画面 ---------- */

const MONTHS = ["正", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二"];
function seasonOrder(s) {
  if (!s) return 999;
  const m = s.match(/(十一|十二|正|一|二|三|四|五|六|七|八|九|十)月/);
  if (m) return MONTHS.indexOf(m[1]) === 0 ? 1 : MONTHS.indexOf(m[1]);
  return 100;
}

async function renderList() {
  app.innerHTML = `<p class="loading">読み込み中…</p>`;
  const all = await loadIndex();
  const seasons = [...new Set(all.map(r => r.season).filter(Boolean))].sort((a, b) => seasonOrder(a) - seasonOrder(b) || a.localeCompare(b, "ja"));
  const noSeason = all.filter(r => !r.season).length;
  const taikanCount = all.filter(r => r.taikan).length;

  app.innerHTML = `
    <div class="controls">
      <input type="search" id="q" placeholder="曲名で検索" value="${esc(listState.q)}" aria-label="曲名で検索">
      <div class="row">
        <div class="tabs" role="group" aria-label="種別">
          ${["すべて", "本編", "番外", "追加"].map(s => `<button data-series="${s}" aria-pressed="${listState.series === s}">${s}</button>`).join("")}
        </div>
        <select id="season" aria-label="季節">
          <option value="">季節：すべて</option>
          ${seasons.map(s => `<option value="${esc(s)}" ${listState.season === s ? "selected" : ""}>${esc(s)}</option>`).join("")}
          <option value="__none" ${listState.season === "__none" ? "selected" : ""}>季節なし（${noSeason}曲）</option>
        </select>
        <label class="check"><input type="checkbox" id="taikanOnly" ${listState.taikanOnly ? "checked" : ""}> 通釈ありのみ</label>
      </div>
      <div class="count" id="count"></div>
    </div>
    <ul class="list" id="list"></ul>`;

  const listEl = document.getElementById("list");
  const countEl = document.getElementById("count");

  function update() {
    const q = norm(listState.q.trim());
    const rows = all.filter(r =>
      (!q || norm(r.title).includes(q)) &&
      (listState.series === "すべて" || r.series === listState.series) &&
      (!listState.season || (listState.season === "__none" ? !r.season : r.season === listState.season)) &&
      (!listState.taikanOnly || r.taikan)
    );
    countEl.textContent = `${rows.length}曲を表示（全${all.length}曲中、通釈あり${taikanCount}曲）`;
    listEl.innerHTML = rows.length ? rows.map(r => `
      <li><a href="#/kyoku/${encodeURIComponent(r.file.replace(/\.txt$/, ""))}">
        <div class="kyoku-title">${esc(r.title)}${r.taikan ? `<span class="badge">通釈</span>` : ""}</div>
        <div class="kyoku-meta">${esc(r.series)}・${esc(r.season || "季節なし")}${r.cast?.length ? "・シテ " + esc((r.cast.find(c => c.role === "シテ") || r.cast[0]).name) : ""}</div>
      </a></li>`).join("") : `<li class="empty">該当する曲はありません。</li>`;
  }

  document.getElementById("q").addEventListener("input", e => { listState.q = e.target.value; update(); });
  document.getElementById("season").addEventListener("change", e => { listState.season = e.target.value; update(); });
  document.getElementById("taikanOnly").addEventListener("change", e => { listState.taikanOnly = e.target.checked; update(); });
  app.querySelectorAll("[data-series]").forEach(b => b.addEventListener("click", () => {
    listState.series = b.dataset.series;
    app.querySelectorAll("[data-series]").forEach(x => x.setAttribute("aria-pressed", x === b));
    update();
  }));
  update();
}

/* ---------- 詳細画面 ---------- */

function metaBlock(r) {
  const cast = (r.cast || []).map(c => `${esc(c.role)}　${esc(c.name)}`).join("<br>");
  return `
    <dl class="meta">
      <dt>種別</dt><dd>${esc(r.series)}（${esc(r.number)}）</dd>
      <dt>季節</dt><dd>${r.season ? esc(r.season) : "なし"}</dd>
      <dt>配役</dt><dd>${cast || "なし"}</dd>
      <dt>底本</dt><dd>${r.source_text ? esc(r.source_text) : "なし"}</dd>
    </dl>`;
}

function markIssues(html, issues) {
  for (const is of issues || []) {
    const s = esc(is.hangyo);
    if (html.includes(s)) {
      html = html.split(s).join(`<mark class="issue" title="${esc("謡曲大観本文：" + is.taikan_honbun)}">${s}</mark>`);
    }
  }
  return html;
}

function utteranceHTML(u, issues) {
  return `<p class="u" data-role="${esc(u.role || "")}">${u.label ? `<span class="sp">${esc(u.label)}</span>` : ""}${markIssues(esc(u.text), issues)}</p>`;
}

function roleFilterHTML(utts) {
  const roles = [...new Set(utts.map(u => u.role).filter(Boolean))];
  if (roles.length < 2) return "";
  return `<div class="tabs" role="group" aria-label="話者で絞り込み">
    <button class="chip" data-role-filter="" aria-pressed="true">全員</button>
    ${roles.map(r => `<button class="chip" data-role-filter="${esc(r)}" aria-pressed="false">${esc(r)}</button>`).join("")}
  </div>`;
}

function bindRoleFilter() {
  app.querySelectorAll("[data-role-filter]").forEach(b => b.addEventListener("click", () => {
    const r = b.dataset.roleFilter;
    app.querySelectorAll("[data-role-filter]").forEach(x => x.setAttribute("aria-pressed", x === b));
    app.querySelectorAll(".u").forEach(u => u.classList.toggle("hidden", !!r && u.dataset.role !== r));
  }));
}

// 歌の通釈（gloss）をはさんで台詞が続く場合は、かぎ括弧を前後でつなげる
function tsuHTML(it, i, items) {
  const text = esc(it.text).replace(/\n/g, "<br>");
  if (it.type === "speech") {
    const open = it.continued ? "" : `<span class="sp">${esc(it.speaker)}</span>「`;
    const close = items[i + 2]?.continued ? "" : "」";
    return `<div class="t">${open}${text}${close}</div>`;
  }
  return `<div class="t ${esc(it.type)}">${text}</div>`;
}

function ndlLink(src, page) {
  if (!src.frame_ref) return src.ndl_url;
  const f = src.frame_ref.frame + Math.ceil((page - src.frame_ref.page) / 2);
  return `${src.ndl_url}/1/${f}`;
}

async function renderKyoku(id) {
  app.innerHTML = `<p class="loading">読み込み中…</p>`;
  const all = await loadIndex();
  const r = all.find(x => x.file === id + ".txt");
  if (!r) { app.innerHTML = `<p class="empty">曲が見つかりません。<a href="#/">一覧へ戻る</a></p>`; return; }

  const [raw, tk] = await Promise.all([
    fetchText(DATA + "hangyo/" + r.file),
    r.taikan ? fetchText(DATA + "taikan/" + r.taikan).then(JSON.parse) : null,
  ]);
  const { body } = splitHeader(raw);
  document.title = `${r.title}｜謡曲リーダー`;

  let html = `<a href="#/" class="back">← 一覧へ</a>
    <h1 class="kyoku">${esc(r.title)}</h1>
    ${metaBlock(r)}`;

  if (!tk) {
    const utts = parseUtterances(body);
    html += `<p class="notice">原文のみ（現代語訳はありません）</p>
      <div class="toolbar">${roleFilterHTML(utts)}</div>
      <div class="col-gen">${utts.map(u => utteranceHTML(u)).join("")}</div>
      <p class="count">原文出典：半魚文庫「謡曲三百五十番集」（${esc(r.file)}）。話者の色分けは役名表記からの推定です。</p>`;
    app.innerHTML = html;
    bindRoleFilter();
    window.scrollTo(0, 0);
    return;
  }

  // 段ごとに原文を切り分ける
  const starts = tk.dan.map(d => body.indexOf(d.hangyo_anchor));
  if (starts.some((p, i) => p < 0 || (i && p < starts[i - 1]))) {
    app.innerHTML = html + `<p class="notice">通釈データの段の位置が原文と合いません（${esc(r.taikan)}）。データを確認してください。</p>`;
    return;
  }
  const head = parseUtterances(body.slice(0, starts[0]));
  let prev = head.length ? head[head.length - 1] : null;
  const chunks = tk.dan.map((d, i) => {
    const u = parseUtterances(body.slice(starts[i], starts[i + 1] ?? body.length), prev?.role, prev?.label?.replace(/（続き）$/, ""));
    if (u.length) prev = u[u.length - 1];
    return u;
  });
  const allUtts = head.concat(...chunks);

  html += `<p class="notice">通釈は佐成謙太郎『謡曲大観』（${esc(tk.source.book.replace(/^.*』/, ""))}、${esc(tk.source.pages)}頁）による。段（【一】【二】…）も同書の区切り。書き起こしは画像からの読み取りで${esc(tk.transcription.status)}です。各段の「原本」から国立国会図書館の画像で確認できます。</p>
    <div class="toolbar">
      <div class="row">
        <div class="tabs" role="group" aria-label="表示">
          <button data-view="both" aria-pressed="true">原文と通釈</button>
          <button data-view="gen" aria-pressed="false">原文のみ</button>
          <button data-view="tsu" aria-pressed="false">通釈のみ</button>
        </div>
        ${roleFilterHTML(allUtts)}
      </div>
    </div>
    <div id="body" data-view="both">
      ${head.length ? `<section class="dan"><div class="cols"><div class="col-gen">${head.map(u => utteranceHTML(u, tk.text_issues)).join("")}</div></div></section>` : ""}
      ${tk.dan.map((d, i) => `
        <section class="dan" id="dan${d.no}">
          <div class="dan-head"><h2>【${esc(d.label)}】</h2><a href="${esc(ndlLink(tk.source, d.page))}" target="_blank" rel="noopener">原本 ${esc(d.page)}頁 ↗</a></div>
          <div class="cols">
            <div class="col-gen"><div class="col-label">原文</div>${chunks[i].map(u => utteranceHTML(u, tk.text_issues)).join("")}</div>
            <div class="col-tsu"><div class="col-label">通釈（謡曲大観）</div>${d.items.map(tsuHTML).join("")}</div>
          </div>
        </section>`).join("")}
    </div>
    ${tk.omitted?.length ? `<p class="count">通釈を収録していない箇所：${tk.omitted.map(o => `${esc(o.content)}（${esc(o.pages)}頁）`).join("、")}</p>` : ""}
    ${tk.text_issues?.length ? `<div class="issues"><h2>原文の異同</h2><ul>${tk.text_issues.map(is => `
      <li>半魚文庫「<mark class="issue">${esc(is.hangyo)}</mark>」→ 謡曲大観本文「${esc(is.taikan_honbun)}」（${esc(is.page)}頁）<br><span class="count">${esc(is.note)}</span></li>`).join("")}</ul></div>` : ""}
    <p class="count">原文出典：半魚文庫「謡曲三百五十番集」（${esc(r.file)}）。通釈：${esc(tk.source.book)}（${esc(tk.source.publisher)} ${esc(tk.source.year)}）、<a href="${esc(tk.source.ndl_url)}" target="_blank" rel="noopener">国立国会図書館デジタルコレクション</a>。書き起こし：${esc(tk.transcription.by)}、${esc(tk.transcription.date)}。</p>`;

  app.innerHTML = html;
  const bodyEl = document.getElementById("body");
  app.querySelectorAll("[data-view]").forEach(b => {
    if (b.id === "body") return;
    b.addEventListener("click", () => {
      bodyEl.dataset.view = b.dataset.view;
      app.querySelectorAll("button[data-view]").forEach(x => x.setAttribute("aria-pressed", x === b));
    });
  });
  bindRoleFilter();
  window.scrollTo(0, 0);
}

/* ---------- ルーティング ---------- */

async function route() {
  const m = location.hash.match(/^#\/kyoku\/(.+)$/);
  try {
    if (m) await renderKyoku(decodeURIComponent(m[1]));
    else { document.title = "謡曲リーダー"; await renderList(); }
  } catch (e) {
    app.innerHTML = `<p class="notice">${esc(e.message)}<br>ファイルを直接開いた場合は読み込めません。README の手順でローカルサーバーを起動してください。</p>`;
  }
}
window.addEventListener("hashchange", route);
route();
