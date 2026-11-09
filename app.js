"use strict";

const DATA = "data/yokyoku/";
const app = document.getElementById("app");

let index = null;
const cache = new Map();
const listState = { q: "", nougara: "" };

/* ---------- 共通 ---------- */

function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function fetchText(path) {
  if (cache.has(path)) return cache.get(path);
  const res = await fetch(path, { cache: "no-cache" });   // データを更新したとき古いものが残らないよう、毎回サーバーに確かめる
  if (!res.ok) throw new Error(`${path} を読み込めませんでした（${res.status}）`);
  const text = await res.text();
  cache.set(path, text);
  return text;
}

async function loadIndex() {
  if (!index) index = JSON.parse(await fetchText(DATA + "index.json"));
  return index;
}

// 検索用に旧字を新字にそろえ、カタカナをひらがなにする（表示は底本のまま）。旧字の表は scripts/collate.py と同じ
const OLD = "淸經國戶吳戀櫻實舍榮關與攝蟬禪曾佛會當龜寢覺樂辨卷萬靜蟲瀨顏賴藏繪鹽郞鐵檜歸髮黑淚亂聲戰鬪靈臺雜遲從將豐兩稱德氣變處數樣續總壽傳圓廣應來祕彌竝隱澤劍姬譽餘覽讀戲驛醫鄕寬邊龍惠圖眞淺壞祿顯團獨單參澁滿舊殘晝狀盡壯專惱擔斷學擧譯聽觀權勸歡齒體髓證據變戀亞惡壓圍爲醉碎濕雙發廢拜賣倂竊竝稻蘆蠶顯勞營螢榮僞謠拔劒卽嚴獸歲靑淨繩虛黃收莊衞遙屆拂擊彈價假冰狹濱渴禮缺盃廳聽鷄雞擴據擇澤鬭畫晉峯嶋埀乘剩擔錢鑄醬鹽奧壹貳參拾鸚";
const NEW = "清経国戸呉恋桜実舎栄関与摂蝉禅曽仏会当亀寝覚楽弁巻万静虫瀬顔頼蔵絵塩郎鉄桧帰髪黒涙乱声戦闘霊台雑遅従将豊両称徳気変処数様続総寿伝円広応来秘弥並隠沢剣姫誉余覧読戯駅医郷寛辺竜恵図真浅壊禄顕団独単参渋満旧残昼状尽壮専悩担断学挙訳聴観権勧歓歯体髄証拠変恋亜悪圧囲為酔砕湿双発廃拝売併窃並稲芦蚕顕労営蛍栄偽謡抜剣即厳獣歳青浄縄虚黄収荘衛遥届払撃弾価仮氷狭浜渇礼欠杯庁聴鶏鶏拡拠択沢闘画晋峰島垂乗剰担銭鋳醤塩奥壱弐参拾鸚";
const VARIANTS = Object.fromEntries([...OLD].map((c, i) => [c, [...NEW][i]]));
function norm(s) {
  return (s || "").normalize("NFKC").replace(/./gu, c => VARIANTS[c] || c)
    .replace(/[\u30a1-\u30f6]/g, c => String.fromCharCode(c.charCodeAt(0) - 0x60)).replace(/\s/g, "")
    .replace(/づ/g, "ず").replace(/ぢ/g, "じ");   // 読みの「づ・ぢ」は「ず・じ」とも書くので同じ扱い
}

// 能柄の先頭（脇能・二番目〜五番目・別曲）を分類に使う
const GROUPS = ["別曲", "脇能", "初番目", "二番目", "三番目", "四番目", "五番目"];
function nougaraGroup(s) {
  const g = GROUPS.find(g => (s || "").startsWith(g));
  return g || (s ? "その他" : "");
}

// 色分け用の役（表示は底本の役名のまま）
function roleKey(role) {
  if (!role) return "";
  if (role.includes("・")) return "同吟";
  if (/ワキ[ヅツ]レ/.test(role)) return "ワキツレ";
  if (/ワキ/.test(role)) return "ワキ";
  if (/シテツレ|ツレ|トモ/.test(role)) return "ツレ";
  if (/[シジ]テ/.test(role)) return "シテ";
  if (role === "地") return "地";
  if (/^子/.test(role)) return "子方";
  if (/狂言|アイ/.test(role)) return "アイ";
  return "その他";
}

function ndlLink(k, page) {
  return `${k.ndl_url}/1/${k.frame_base + Math.floor(page / 2)}`;
}

/* ---------- 一覧画面 ---------- */

async function renderList() {
  app.innerHTML = `<p class="loading">読み込み中…</p>`;
  const all = await loadIndex();
  const groups = [...new Set(all.map(r => nougaraGroup(r.nougara)).filter(Boolean))]
    .sort((a, b) => GROUPS.indexOf(a) - GROUPS.indexOf(b));

  app.innerHTML = `
    <div class="controls">
      <input type="search" id="q" placeholder="曲名・読みで検索（例：清経、きよつね）" value="${esc(listState.q)}" aria-label="曲名で検索">
      ${groups.length > 1 ? `<div class="tabs" role="group" aria-label="能柄">
        ${["", ...groups].map(g => `<button data-g="${esc(g)}" aria-pressed="${listState.nougara === g}">${esc(g || "すべて")}</button>`).join("")}
      </div>` : ""}
      <div class="count" id="count"></div>
    </div>
    <ul class="list" id="list"></ul>`;

  const listEl = document.getElementById("list");
  const countEl = document.getElementById("count");

  function update() {
    const q = norm(listState.q.trim());
    const rows = all.filter(r =>
      (!q || norm(r.title).includes(q) || norm(r.yomi).includes(q)) &&
      (!listState.nougara || nougaraGroup(r.nougara) === listState.nougara));
    countEl.textContent = `${rows.length}曲を表示（本文の確認が済んだ${all.length}曲を収録。謡曲大観の全282曲から順次追加）`;
    listEl.innerHTML = rows.length ? rows.map(r => `
      <li><a href="#/kyoku/${encodeURIComponent(r.title)}">
        <div class="kyoku-title">${esc(r.title)}</div>
        <div class="kyoku-meta">${esc([r.nougara, r.toki].filter(Boolean).join("・") || r.volume)}</div>
      </a></li>`).join("") : `<li class="empty">該当する曲はありません。</li>`;
  }

  document.getElementById("q").addEventListener("input", e => { listState.q = e.target.value; update(); });
  app.querySelectorAll("[data-g]").forEach(b => b.addEventListener("click", () => {
    listState.nougara = b.dataset.g;
    app.querySelectorAll("[data-g]").forEach(x => x.setAttribute("aria-pressed", x === b));
    update();
  }));
  update();
}

/* ---------- 詳細画面 ---------- */

const BACK = `<a href="#/" class="back">← 曲の一覧に戻る</a>`;

function infoBlock(k) {
  const i = k.info || {};
  const rows = [["能柄", i.能柄], ["人物", i.人物], ["所", i.所], ["時", i.時], ["流派", i.流派]].filter(([, v]) => v);
  // 曲情報・梗概は解説の頁（曲の最初の頁とその次）の OCR のまま。原本の画像で確かめられるようにする
  const src = `<p class="meta-src"><a href="${esc(ndlLink(k, k.start_page))}" target="_blank" rel="noopener">解説の原本 ${k.start_page}頁 ↗</a></p>`;
  return `
    <dl class="meta">${rows.map(([t, v]) => `<dt>${t}</dt><dd>${esc(v).replace(/\n/g, "<br>")}</dd>`).join("")}</dl>
    ${i.梗概 ? `<div class="summary"><h2>梗概</h2><p>${esc(i.梗概)}</p></div>` : ""}
    ${src}`;
}

// 本文中の（ト書き）を小さく
function dirs(s) {
  return esc(s).replace(/([(（〔][^)）〕]*[)）〕])/g, `<span class="dir">$1</span>`);
}

function honbunHTML(it, k) {
  if (it.type === "note") return `<p class="note">${esc(it.text)}</p>`;
  if (it.type === "heading") return `<p class="note">${esc(it.text)}</p>`;
  if (it.type === "ai") {
    const [a, b] = it.pages;
    const link = `<a href="${esc(ndlLink(k, a))}" target="_blank" rel="noopener">原本 ${a}${b !== a ? "–" + b : ""}頁 ↗</a>`;
    if (!it.items?.length) return `<p class="ai-head">間狂言（このサイトには未収録。${link}）</p>`;
    return `<div class="ai"><p class="ai-head"><span>間狂言</span>${link}</p>${it.items.map(x => honbunHTML(x, k)).join("")}</div>`;
  }
  const label = [it.role, it.shodan].filter(Boolean).join(" ");
  return `<p class="u" data-role="${esc(roleKey(it.role || it.role_cont))}">${label ? `<span class="sp">${esc(label)}</span>` : ""}${it.paren ? `<span class="dir">${esc(it.paren)}</span>` : ""}${dirs(it.text)}</p>`;
}

function tsuHTML(it) {
  if (it.type === "speech") return `<div class="t"><span class="sp">${esc(it.speaker)}</span>「${esc(it.text)}」</div>`;
  if (it.type === "gloss") return `<div class="t gloss">${esc(it.text.replace(/^[(（]|[)）]$/g, ""))}</div>`;
  return `<div class="t ${esc(it.type)}">${esc(it.text)}</div>`;
}

async function renderKyoku(title) {
  app.innerHTML = `<p class="loading">読み込み中…</p>`;
  const all = await loadIndex();
  if (!all.find(x => x.title === title)) { app.innerHTML = `<p class="empty">曲が見つかりません。<a href="#/">一覧へ戻る</a></p>`; return; }
  const k = JSON.parse(await fetchText(DATA + "kyoku/" + encodeURIComponent(title) + ".json"));
  document.title = `${k.title}｜謡曲リーダー`;

  app.innerHTML = `${BACK}
    <h1 class="kyoku">${esc(k.title)}</h1>
    ${infoBlock(k)}
    <div class="toolbar">
      <div class="row">
        <div class="tabs" role="group" aria-label="表示">
          <button data-view="both" aria-pressed="true">本文と通釈</button>
          <button data-view="gen" aria-pressed="false">本文のみ</button>
          <button data-view="tsu" aria-pressed="false">通釈のみ</button>
        </div>
      </div>
    </div>
    <div id="body" data-view="both">
      ${k.dan.map(d => `
        <section class="dan" id="dan${d.no ?? "ai"}">
          <div class="dan-head"><h2>【${esc(d.label)}】</h2><a href="${esc(ndlLink(k, d.page))}" target="_blank" rel="noopener">原本 ${d.page}頁 ↗</a></div>
          <div class="cols">
            <div class="col-gen"><div class="col-label">本文</div>${d.honbun.map(it => honbunHTML(it, k)).join("")}</div>
            <div class="col-tsu"><div class="col-label">通釈</div>${d.tsushaku.length ? d.tsushaku.map(tsuHTML).join("") : d.ai ? "" : `<p class="note">（大観に通釈なし）</p>`}</div>
          </div>
        </section>`).join("")}
    </div>
    <div class="source">
      <p>本文と通釈は、佐成謙太郎『謡曲大観』${esc(k.volume)}（明治書院 1930–31）${k.pages[0]}–${k.pages[1]}頁の印刷面を、OCR（NDLOCR-Lite）で文字に起こしたものです。
        本文（謡の詞章）は、別の版と照らし合わせて食い違った箇所を原本の画像で確かめました。ト書き・通釈・曲情報・間狂言は OCR のままで、誤りが残っている可能性があります。
        各段や曲情報の下の「原本」から<a href="${esc(k.ndl_url)}" target="_blank" rel="noopener">国立国会図書館デジタルコレクション</a>の画像で確かめられます。話者の色分けは役名からの推定です。</p>
      <p><a href="#/about">凡例</a></p>
    </div>
    ${BACK}`;

  const bodyEl = document.getElementById("body");
  app.querySelectorAll("button[data-view]").forEach(b => b.addEventListener("click", () => {
    bodyEl.dataset.view = b.dataset.view;
    app.querySelectorAll("button[data-view]").forEach(x => x.setAttribute("aria-pressed", x === b));
  }));
  window.scrollTo(0, 0);
}

/* ---------- 説明ページ（docs/taikan_ocr.md を表示） ---------- */

// 説明ページ用の小さな Markdown 変換（見出し・段落・箇条書き・表・リンク・太字・コード）
function inlineMd(s) {
  return esc(s)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, t, u) => `<a href="${/^https?:/.test(u) ? u : "#/about"}"${/^https?:/.test(u) ? ' target="_blank" rel="noopener"' : ""}>${t}</a>`);
}
function md(src) {
  const out = [];
  const lines = src.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    if (!l.trim()) continue;
    let m;
    if ((m = l.match(/^(#{1,4})\s+(.*)$/))) { const n = Math.min(m[1].length + 1, 4); out.push(`<h${n}>${inlineMd(m[2])}</h${n}>`); continue; }
    if (/^\|/.test(l)) {
      const rows = [];
      for (; i < lines.length && /^\|/.test(lines[i]); i++) rows.push(lines[i]);
      i--;
      const cells = r => r.replace(/^\||\|$/g, "").split("|").map(c => c.trim());
      const body = rows.filter(r => !/^\|[\s:|-]+\|$/.test(r));
      out.push(`<div class="table-wrap"><table><thead><tr>${cells(body[0]).map(c => `<th>${inlineMd(c)}</th>`).join("")}</tr></thead><tbody>${
        body.slice(1).map(r => `<tr>${cells(r).map(c => `<td>${inlineMd(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`);
      continue;
    }
    if (/^\s*- /.test(l)) {
      const items = [];
      for (; i < lines.length && /^\s*- /.test(lines[i]); i++) items.push(`<li${/^\s{2,}/.test(lines[i]) ? ' class="sub"' : ""}>${inlineMd(lines[i].replace(/^\s*- /, ""))}</li>`);
      i--;
      out.push(`<ul>${items.join("")}</ul>`);
      continue;
    }
    const para = [l];
    for (i++; i < lines.length && lines[i].trim() && !/^(#|\||\s*- )/.test(lines[i]); i++) para.push(lines[i]);
    i--;
    out.push(`<p>${para.map(inlineMd).join("<br>")}</p>`);
  }
  return out.join("\n");
}

async function renderAbout() {
  app.innerHTML = `<p class="loading">読み込み中…</p>`;
  const src = await fetchText("docs/taikan_ocr.md");
  document.title = "凡例｜謡曲リーダー";
  app.innerHTML = `${BACK}<article class="doc">${md(src)}</article>${BACK}`;
  window.scrollTo(0, 0);
}

/* ---------- ルーティング ---------- */

async function route() {
  const m = location.hash.match(/^#\/kyoku\/(.+)$/);
  try {
    if (m) await renderKyoku(decodeURIComponent(m[1]));
    else if (location.hash === "#/about") await renderAbout();
    else { document.title = "謡曲リーダー"; await renderList(); }
  } catch (e) {
    app.innerHTML = `<p class="notice">${esc(e.message)}<br>ファイルを直接開いた場合は読み込めません。README の手順でローカルサーバーを起動してください。</p>`;
  }
}
window.addEventListener("hashchange", route);
route();
