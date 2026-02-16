from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["crm"])


@router.get("/crm", response_class=HTMLResponse)
async def crm_page() -> str:
    return """
<!doctype html>
<html lang="uk">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Student Bot CRM</title>
  <style>
    :root { --bg:#0b1220; --panel:#121a2b; --line:#263149; --text:#e7eefc; --muted:#9fb0cc; --accent:#4f8cff; }
    * { box-sizing:border-box; font-family: ui-sans-serif, -apple-system, Segoe UI, Roboto, sans-serif; }
    body { margin:0; background:var(--bg); color:var(--text); }
    .wrap { max-width: 1480px; margin: 0 auto; padding: 18px; }
    .grid { display:grid; grid-template-columns: repeat(6,minmax(140px,1fr)); gap:10px; margin-bottom:14px; }
    .card { background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:10px; }
    .k { color:var(--muted); font-size:12px; }
    .v { font-size:22px; font-weight:700; }
    .row { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px; }
    input, select, button { background:#0f1627; color:var(--text); border:1px solid var(--line); border-radius:8px; padding:8px 10px; }
    input, select { min-width: 130px; }
    button { cursor:pointer; }
    .btn { background:#14213a; }
    .btn.primary { background:var(--accent); border-color:var(--accent); color:white; }
    .table-wrap { overflow:auto; border:1px solid var(--line); border-radius:10px; background:var(--panel); }
    table { border-collapse: collapse; width:100%; min-width: 1400px; }
    th, td { border-bottom:1px solid var(--line); padding:8px; font-size:13px; white-space:nowrap; }
    th { text-align:left; color:#c8d7f0; position:sticky; top:0; background:#1b2742; }
    .muted { color:var(--muted); }
    .actions button { margin-right:4px; margin-bottom:4px; }
    .ok { color:#6be28f; }
    .bad { color:#ff7f7f; }
  </style>
</head>
<body>
<div class="wrap">
  <h2>Student Bot CRM</h2>
  <div class="row">
    <input id="token" placeholder="X-Admin-Token" style="min-width:340px" />
    <button class="btn primary" onclick="saveToken()">Зберегти токен</button>
    <span id="status" class="muted"></span>
  </div>

  <div class="grid" id="stats"></div>

  <div class="row">
    <input id="search" placeholder="Пошук: id/username/мова/план" />
    <select id="plan">
      <option value="">Всі плани</option>
      <option value="free">free</option>
      <option value="student">student</option>
      <option value="pro">pro</option>
    </select>
    <select id="banned">
      <option value="">ban: всі</option>
      <option value="false">not banned</option>
      <option value="true">banned</option>
    </select>
    <select id="sortBy">
      <option value="created_at">created_at</option>
      <option value="telegram_id">telegram_id</option>
      <option value="username">username</option>
      <option value="language">language</option>
      <option value="plan">plan</option>
      <option value="is_banned">is_banned</option>
      <option value="monthly_requests_used">monthly_requests_used</option>
      <option value="monthly_tokens_used">monthly_tokens_used</option>
      <option value="monthly_images_used">monthly_images_used</option>
      <option value="monthly_photo_analyses_used">monthly_photo_analyses_used</option>
      <option value="monthly_long_texts_used">monthly_long_texts_used</option>
      <option value="bonus_image_credits">bonus_image_credits</option>
    </select>
    <select id="sortOrder">
      <option value="desc">desc</option>
      <option value="asc">asc</option>
    </select>
    <input id="limit" type="number" value="100" min="1" max="500" style="width:90px" />
    <button class="btn primary" onclick="loadAll()">Оновити</button>
    <button class="btn" onclick="syncSheets('pull')">Sheets Pull</button>
    <button class="btn" onclick="syncSheets('push')">Sheets Push</button>
    <button class="btn" onclick="syncSheets('both')">Sheets Both</button>
  </div>

  <div class="muted" id="totalInfo"></div>

  <div class="table-wrap">
    <table id="usersTable">
      <thead>
        <tr>
          <th>telegram_id</th><th>username</th><th>lang</th><th>plan</th><th>banned</th>
          <th>price_usd</th><th>req_m</th><th>tok_m</th><th>img_m</th><th>photo_m</th><th>long_m</th><th>bonus_img</th><th>created</th><th>actions</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
  </div>
</div>

<script>
const $ = (id) => document.getElementById(id);

function getToken(){ return $('token').value.trim(); }
function headers(){ return { 'X-Admin-Token': getToken(), 'Content-Type':'application/json' }; }
function setStatus(msg, isErr=false){ const s=$('status'); s.textContent=msg; s.className=isErr?'bad':'muted'; }

function saveToken(){
  localStorage.setItem('crm_admin_token', getToken());
  setStatus('Токен збережено');
}

async function api(url, opts={}){
  const r = await fetch(url, { ...opts, headers: { ...headers(), ...(opts.headers||{}) } });
  if(!r.ok){
    const t = await r.text();
    throw new Error(`HTTP ${r.status}: ${t}`);
  }
  return r.json();
}

async function loadStats(){
  const data = await api('/admin/stats');
  const u = data.users; const l = data.logs;
  const cards = [
    ['Users', u.total_users], ['Free', u.free_users], ['Student', u.student_users], ['Pro', u.pro_users], ['Banned', u.banned_users], ['Req/Month', u.monthly_requests_used],
    ['Tokens/Month', u.monthly_tokens_used], ['Images/Month', u.monthly_images_used], ['Photo/Month', u.monthly_photo_analyses_used], ['LongText/Month', u.monthly_long_texts_used], ['Bonus Img', u.bonus_image_credits], ['Logs', l.total_logs], ['Errors', l.error_logs]
  ];
  $('stats').innerHTML = cards.map(([k,v]) => `<div class="card"><div class="k">${k}</div><div class="v">${v ?? 0}</div></div>`).join('');
}

function rowActions(u){
  return `
    <button class="btn" onclick="setPlan(${u.telegram_id},'free')">FREE</button>
    <button class="btn" onclick="setPlan(${u.telegram_id},'student')">STUDENT</button>
    <button class="btn" onclick="setPlan(${u.telegram_id},'pro')">PRO</button>
    <button class="btn" onclick="toggleBan(${u.telegram_id}, ${u.is_banned})">${u.is_banned ? 'UNBAN':'BAN'}</button>
    <button class="btn" onclick="resetLimits(${u.telegram_id},'daily')">reset day</button>
    <button class="btn" onclick="resetLimits(${u.telegram_id},'monthly')">reset month</button>
    <button class="btn" onclick="addCredits(${u.telegram_id},1)">+1 img</button>
    <button class="btn" onclick="addCredits(${u.telegram_id},5)">+5 img</button>
  `;
}

async function loadUsers(){
  const p = new URLSearchParams();
  p.set('limit', $('limit').value || '100');
  p.set('offset', '0');
  p.set('sort_by', $('sortBy').value);
  p.set('sort_order', $('sortOrder').value);
  if($('search').value.trim()) p.set('search', $('search').value.trim());
  if($('plan').value) p.set('plan', $('plan').value);
  if($('banned').value) p.set('is_banned', $('banned').value);

  const data = await api('/admin/users?' + p.toString());
  const revenue = data.items.reduce((sum, u) => sum + Number(u.plan_price_usd || 0), 0);
  $('totalInfo').textContent = `Показано: ${data.items.length} / Всього: ${data.total} / Підписка (поточний фільтр): $${revenue}`;

  const rows = data.items.map(u => `
    <tr>
      <td>${u.telegram_id}</td>
      <td>${u.username ?? ''}</td>
      <td>${u.language}</td>
      <td>${u.plan}</td>
      <td>${u.is_banned}</td>
      <td>$${u.plan_price_usd ?? 0}</td>
      <td>${u.monthly_requests_used}</td>
      <td>${u.monthly_tokens_used}</td>
      <td>${u.monthly_images_used}</td>
      <td>${u.monthly_photo_analyses_used}</td>
      <td>${u.monthly_long_texts_used ?? 0}</td>
      <td>${u.bonus_image_credits}</td>
      <td>${u.created_at}</td>
      <td class="actions">${rowActions(u)}</td>
    </tr>
  `).join('');

  document.querySelector('#usersTable tbody').innerHTML = rows;
}

async function setPlan(id, plan){ await api(`/admin/users/${id}/plan/${plan}`, { method:'POST' }); await loadAll(); }
async function toggleBan(id, isBanned){ await api(`/admin/users/${id}/${isBanned ? 'unban':'ban'}`, { method:'POST' }); await loadAll(); }
async function resetLimits(id, scope){ await api(`/admin/users/${id}/reset-limits?scope=${scope}`, { method:'POST' }); await loadAll(); }
async function addCredits(id, amount){ await api(`/admin/users/${id}/grant-image-credits?amount=${amount}`, { method:'POST' }); await loadAll(); }
async function syncSheets(direction){
  const r = await api(`/admin/sync/google-sheets?direction=${direction}`, { method:'POST' });
  setStatus(`Sheets ${direction}: push=${r.pushed_rows}, pull_upd=${r.pulled_updated}, pull_new=${r.pulled_created}`);
  await loadAll();
}

async function loadAll(){
  try {
    await Promise.all([loadStats(), loadUsers()]);
    setStatus('Оновлено');
  } catch(e){
    setStatus(String(e.message || e), true);
  }
}

(function init(){
  $('token').value = localStorage.getItem('crm_admin_token') || '';
})();
</script>
</body>
</html>
"""
