"""管理ダッシュボード（最小・自己完結HTML, docs/mvp-design.md §8）。

公開パス /dashboard で配信する（秘密は含まない）。管理操作は画面で入力した
管理トークンを X-Admin-Token ヘッダに載せて /admin/* を呼ぶ（トークンはブラウザの
sessionStorage に保持し、サーバには保存しない）。恒久的には IAP 導入を推奨。
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

_HTML = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>JCI専務理事エージェント 管理</title>
<style>
  :root { --navy:#1f3a5f; --blue:#2e5a88; --bg:#f4f6f9; }
  * { box-sizing: border-box; }
  body { font-family: system-ui, sans-serif; margin:0; background:var(--bg); color:#1a1a1a; }
  header { background:var(--navy); color:#fff; padding:14px 18px; font-size:18px; font-weight:600; }
  main { max-width:880px; margin:0 auto; padding:16px; }
  .card { background:#fff; border-radius:10px; padding:16px; margin:12px 0; box-shadow:0 1px 4px rgba(0,0,0,.08); }
  h2 { font-size:15px; margin:0 0 10px; color:var(--navy); }
  input { padding:8px; border:1px solid #ccc; border-radius:6px; width:100%; max-width:420px; }
  button { background:var(--blue); color:#fff; border:0; border-radius:6px; padding:8px 14px; cursor:pointer; font-size:14px; }
  button.warn { background:#b3261e; }
  button.ghost { background:#e7ebf0; color:var(--navy); }
  table { width:100%; border-collapse:collapse; font-size:14px; }
  th,td { text-align:left; padding:7px 6px; border-bottom:1px solid #eee; }
  .muted { color:#777; font-size:13px; }
  .pill { display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px; }
  .on { background:#fde7e7; color:#b3261e; }
  .off { background:#e6f4ea; color:#137333; }
  .rate { font-weight:600; }
</style>
</head>
<body>
<header>JCI専務理事エージェント — 管理ダッシュボード</header>
<main>
  <div class="card" id="auth">
    <h2>管理トークン</h2>
    <p class="muted">役員に共有された管理トークンを入力してください（この端末にのみ保持されます）。</p>
    <input id="token" type="password" placeholder="X-Admin-Token">
    <p><button onclick="saveToken()">接続</button>
       <button class="ghost" onclick="clearToken()">クリア</button></p>
    <p id="authmsg" class="muted"></p>
  </div>

  <div class="card">
    <h2>全体設定</h2>
    <p>キルスイッチ: <span id="kill" class="pill off">-</span>
       <button id="killbtn" class="warn" onclick="toggleKill()">切替</button></p>
    <p class="muted">ON の間、全自動配信は停止します（緊急停止）。</p>
    <p>会員数: <span id="memcount">-</span></p>
  </div>

  <div class="card">
    <h2>イベントと出欠</h2>
    <p><button class="ghost" onclick="loadAll()">再読み込み</button></p>
    <div id="events"><p class="muted">未接続です。</p></div>
  </div>
</main>
<script>
const TKEY = "jci_admin_token";
function token(){ return sessionStorage.getItem(TKEY) || ""; }
function saveToken(){ sessionStorage.setItem(TKEY, document.getElementById("token").value.trim()); loadAll(); }
function clearToken(){ sessionStorage.removeItem(TKEY); document.getElementById("authmsg").textContent="クリアしました。"; }
async function api(path, opts={}){
  opts.headers = Object.assign({"X-Admin-Token": token()}, opts.headers||{});
  const r = await fetch(path, opts);
  if(r.status===401){ throw new Error("認証エラー: トークンを確認してください。"); }
  return r;
}
async function loadAll(){
  const msg = document.getElementById("authmsg");
  try{
    const s = await (await api("/admin/settings")).json();
    const kill = document.getElementById("kill");
    kill.textContent = s.kill_switch ? "ON（停止中）" : "OFF（稼働）";
    kill.className = "pill " + (s.kill_switch ? "on" : "off");
    const members = await (await api("/admin/members")).json();
    document.getElementById("memcount").textContent = members.length + " 名";
    const events = await (await api("/admin/events")).json();
    await renderEvents(events);
    msg.textContent = "接続済み。";
  }catch(e){ msg.textContent = e.message; }
}
async function renderEvents(events){
  const box = document.getElementById("events");
  if(!events.length){ box.innerHTML = '<p class="muted">イベントがありません。</p>'; return; }
  let html = '<table><tr><th>イベント</th><th>日時</th><th>回答/対象</th><th>出席率</th><th></th></tr>';
  for(const ev of events){
    const d = await (await api("/admin/events/"+ev.event_id)).json();
    const su = d.summary;
    html += `<tr>
      <td>${ev.title}</td>
      <td class="muted">${(ev.datetime_start||"").replace("T"," ").slice(0,16)}</td>
      <td>${su.answered}/${su.total_targets}</td>
      <td class="rate">${Math.round(su.attendance_rate*100)}%</td>
      <td><button class="ghost" onclick="remind('${ev.event_id}')">未回答に催促</button></td>
    </tr>`;
  }
  html += "</table>";
  box.innerHTML = html;
}
async function toggleKill(){
  try{
    const s = await (await api("/admin/settings")).json();
    s.kill_switch = !s.kill_switch;
    await api("/admin/settings", {method:"PUT", headers:{"Content-Type":"application/json"}, body:JSON.stringify(s)});
    loadAll();
  }catch(e){ document.getElementById("authmsg").textContent = e.message; }
}
async function remind(eid){
  try{
    const r = await (await api("/admin/events/"+eid+"/remind", {method:"POST"})).json();
    alert("催促ジョブを作成しました（対象 "+ (r.targets?r.targets.length:0) +" 名）。");
  }catch(e){ alert(e.message); }
}
if(token()){ loadAll(); }
</script>
</body>
</html>"""


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return HTMLResponse(_HTML)
