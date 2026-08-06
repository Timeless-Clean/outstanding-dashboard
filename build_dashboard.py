"""
Pulls ALL outstanding (AUTHORISED / awaiting-payment) sales invoices for the
three Timeless entities from the Xero API and builds docs/index.html
(the Outstanding Invoices dashboard, served by GitHub Pages).

Environment variables (provided by GitHub Actions secrets):
    XERO_CLIENT_ID, XERO_CLIENT_SECRET, XERO_REFRESH_TOKEN
The refresh token rotates each run; the new one is written to token.json,
which the workflow commits back to the (private) repo.
"""
import os, json, base64, datetime, html
from zoneinfo import ZoneInfo
import requests

CLIENT_ID = os.environ["XERO_CLIENT_ID"]
CLIENT_SECRET = os.environ["XERO_CLIENT_SECRET"]

# entity display config: match by tenant name substring
ENTITY_ORDER = ["SOR", "TCC", "TPM"]          # tab order
ENTITY_LABEL = {"SOR": "SOR", "TCC": "TCCS", "TPM": "TPM"}
def entity_code(tenant_name):
    n = tenant_name.lower()
    if "property maintenance" in n: return "TPM"
    if "sor services" in n:         return "SOR"
    if "commercial clean" in n:     return "TCC"
    return None

def load_refresh_token():
    if os.path.exists("token.json"):
        return json.load(open("token.json"))["refresh_token"]
    return os.environ["XERO_REFRESH_TOKEN"]

def refresh(rt):
    basic = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    r = requests.post("https://identity.xero.com/connect/token",
        headers={"Authorization": f"Basic {basic}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "refresh_token", "refresh_token": rt})
    r.raise_for_status()
    tok = r.json()
    json.dump({"refresh_token": tok["refresh_token"]}, open("token.json", "w"))
    return tok["access_token"]

def get_tenants(access):
    r = requests.get("https://api.xero.com/connections",
                     headers={"Authorization": f"Bearer {access}",
                              "Content-Type": "application/json"})
    r.raise_for_status()
    return r.json()

def get_unpaid_invoices(access, tenant_id):
    out, page = [], 1
    while True:
        r = requests.get("https://api.xero.com/api.xro/2.0/Invoices",
            headers={"Authorization": f"Bearer {access}",
                     "Xero-tenant-id": tenant_id, "Accept": "application/json"},
            params={"where": 'Type=="ACCREC" AND Status=="AUTHORISED"',
                    "page": page, "pageSize": 100})
        r.raise_for_status()
        inv = r.json().get("Invoices", [])
        if not inv: break
        out.extend(inv)
        if len(inv) < 100: break
        page += 1
    return out

def parse_date(s):
    # Xero returns "/Date(1690000000000+0000)/" or ISO; DateString is ISO
    try: return datetime.date.fromisoformat(s[:10])
    except Exception: return None

def build():
    access = refresh(load_refresh_token())
    tenants = get_tenants(access)
    today = datetime.datetime.now(ZoneInfo("Australia/Sydney")).date()
    rows = []
    for t in tenants:
        code = entity_code(t["tenantName"])
        if not code: continue
        for iv in get_unpaid_invoices(access, t["tenantId"]):
            due = parse_date(iv.get("DueDateString") or iv.get("DueDate", "") or "")
            idt = parse_date(iv.get("DateString") or iv.get("Date", "") or "")
            days = (today - due).days if due and (today - due).days > 0 else None
            rows.append({
                "ent": code,
                "contact": (iv.get("Contact") or {}).get("Name", "").strip(),
                "inv": iv.get("InvoiceNumber", ""),
                "ref": iv.get("Reference", ""),
                "amount": float(iv.get("AmountDue", 0) or 0),
                "days": days,
                "y": idt.year if idt else None,
                "m": idt.month if idt else None,
                "my": idt.strftime("%b %Y") if idt else None,
            })
    # aggregate by (entity, name) with leading "=" merge; display "=" if any variant had it
    groups = {}
    for r in rows:
        key = (r["ent"], r["contact"].lstrip("=").strip())
        groups.setdefault(key, []).append(r)
    agg = []
    for (ent, cleaned), items in groups.items():
        has_eq = any(i["contact"].lstrip().startswith("=") for i in items)
        disp = ("=" + cleaned) if has_eq else cleaned
        dated = [i for i in items if i["y"]]
        oldest = min(dated, key=lambda i: (i["y"], i["m"]))["my"] if dated else None
        invs = sorted(items, key=lambda i: ((i["y"] or 0), (i["m"] or 0), i["amount"]), reverse=True)
        agg.append({"ent": ent, "site": disp, "count": len(items),
                    "total": round(sum(i["amount"] for i in items), 2), "oldest": oldest,
                    "invoices": [{"inv": i["inv"], "ref": i["ref"], "amount": i["amount"],
                                  "days": i["days"], "my": i["my"]} for i in invs]})
    agg.sort(key=lambda x: (-x["count"], -x["total"]))
    now = datetime.datetime.now(ZoneInfo("Australia/Sydney"))
    updated = now.strftime("%-d %b %Y · %-I:%M %p ") + now.tzname()
    asat = now.strftime("%-d %b %Y")
    os.makedirs("docs", exist_ok=True)
    open("docs/index.html", "w", encoding="utf-8").write(
        HTML.replace("__DATA__", json.dumps(agg))
            .replace("__UPDATED__", updated).replace("__ASAT__", asat)
            .replace("__TZ__", now.tzname())
            .replace("__ORDER__", json.dumps(ENTITY_ORDER))
            .replace("__LABEL__", json.dumps(ENTITY_LABEL)))
    print("Built docs/index.html:", len(rows), "invoices across", len(set(a['ent'] for a in agg)), "entities")

HTML = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Outstanding Invoices - Timeless Group</title>
<style>
:root{--bg:#f4f6f8;--card:#fff;--line:#e3e8ee;--txt:#1f2933;--mut:#6b7885;--accent:#1e6fe0;--accent2:#e8f0fd;--red:#d64545;--amb:#c77700;--grn:#2f8f4e}
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;background:var(--bg);color:var(--txt)}
.wrap{max-width:1000px;margin:0 auto;padding:24px 16px 60px}
.topbar{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:16px}
h1{font-size:20px;margin:0 0 2px}.sub{color:var(--mut);font-size:13px}
.updated{display:inline-flex;align-items:center;gap:6px;color:var(--mut);font-size:12px;white-space:nowrap}
.updated .dot{width:7px;height:7px;border-radius:50%;background:var(--grn)}
.ent-tabs{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}
.ent-tabs button{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:9px 16px;font-size:13px;font-weight:600;color:var(--mut);cursor:pointer}
.ent-tabs button.on{background:#101828;color:#fff;border-color:#101828}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}
@media(max-width:640px){.kpis{grid-template-columns:repeat(2,1fr)}}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}
.kpi .v{font-size:22px;font-weight:700}.kpi .l{color:var(--mut);font-size:12px;margin-top:4px}
.controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:14px}
.seg{display:inline-flex;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.seg button{background:none;border:0;color:var(--mut);padding:8px 14px;font-size:13px;cursor:pointer}
.seg button.on{background:var(--accent);color:#fff;font-weight:600}
input#q{flex:1;min-width:160px;background:var(--card);border:1px solid var(--line);color:var(--txt);border-radius:10px;padding:9px 12px;font-size:14px}
.row{background:var(--card);border:1px solid var(--line);border-radius:12px;margin-bottom:8px;overflow:hidden}
.head{display:grid;grid-template-columns:34px 62px 1fr auto;gap:14px;align-items:center;padding:12px 14px;cursor:pointer}
.rank{color:var(--mut);font-weight:700;font-size:14px;text-align:center}
.name{font-weight:600;font-size:14px}
.badge{font-size:12px;color:var(--mut);margin-top:3px}
.since{color:var(--amb);font-weight:600}
.count{display:flex;flex-direction:column;align-items:center;justify-content:center;width:56px;height:56px;border-radius:14px;line-height:1}
.count .num{font-size:24px;font-weight:800}.count .lbl{font-size:9px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;margin-top:3px;opacity:.85}
.c-hi{background:#fdecec;color:var(--red);border:1px solid #f6c9c9}.c-md{background:#fdf1df;color:var(--amb);border:1px solid #f4dcae}.c-lo{background:var(--accent2);color:var(--accent);border:1px solid #cfe0fb}
.amt{font-weight:700;font-size:15px;min-width:104px;text-align:right}
.det{display:none;padding:0 14px 12px 110px}.row.open .det{display:block}
table{width:100%;border-collapse:collapse;font-size:13px}
td,th{padding:6px 8px;border-top:1px solid var(--line);text-align:left}
th{color:var(--mut);font-weight:500}th.n{text-align:right}
td.n{text-align:right;font-variant-numeric:tabular-nums}
.ref{color:var(--mut)}
.det td:nth-child(4),.det th:nth-child(4){width:120px}.det td:nth-child(5),.det th:nth-child(5){width:96px}
.pill{display:inline-block;min-width:40px;text-align:center;padding:2px 9px;border-radius:20px;font-size:12px;font-weight:600}
.pill.od{background:#fdecec;color:var(--red)}.pill.ok{background:#eef1f4;color:#9aa6b2}
.foot{color:var(--mut);font-size:12px;margin-top:18px;line-height:1.5}
.chev{transition:transform .15s;display:inline-block}.row.open .chev{transform:rotate(90deg)}
</style></head><body><div class="wrap">
<div class="topbar">
 <div><h1>Outstanding Invoices</h1>
 <div class="sub">Timeless Group &middot; 3 Xero entities &middot; snapshot as at __ASAT__ (__TZ__)</div></div>
 <span class="updated"><span class="dot"></span>Updated __UPDATED__</span>
</div>
<div class="ent-tabs" id="ents"></div>
<div class="kpis" id="kpis"></div>
<div class="controls">
<div class="seg"><button id="bC" class="on" onclick="setSort('count')">Rank by count</button><button id="bA" onclick="setSort('total')">Rank by $ amount</button></div>
<input id="q" placeholder="Search site..." oninput="render()">
</div>
<div id="list"></div>
<div class="foot">Live from the Xero API across all three entities. Ranked by unpaid-invoice count (ties by amount); badge red 5+, amber 3-4, blue 1-2. Auto-updates on weekdays, morning &amp; midday Sydney time.</div>
</div>
<script>
const DATA=__DATA__;const ORDER=__ORDER__;const LBL=__LABEL__;let sortKey='count';let ent=ORDER[0];
function money(n){return n.toLocaleString('en-AU',{minimumFractionDigits:2,maximumFractionDigits:2})}
function cls(c){return c>=5?'c-hi':c>=3?'c-md':'c-lo'}
function setSort(k){sortKey=k;document.getElementById('bC').classList.toggle('on',k==='count');document.getElementById('bA').classList.toggle('on',k==='total');render()}
function setEnt(e){ent=e;[...document.querySelectorAll('#ents button')].forEach(b=>b.classList.toggle('on',b.dataset.e===e));render()}
function subset(){return DATA.filter(x=>x.ent===ent)}
function tabs(){document.getElementById('ents').innerHTML=ORDER.map(e=>`<button data-e="${e}" class="${e===ent?'on':''}" onclick="setEnt('${e}')">${LBL[e]||e}</button>`).join('')}
function kpis(){const d=subset();const inv=d.reduce((a,b)=>a+b.count,0);const tot=d.reduce((a,b)=>a+b.total,0);
 const od=d.reduce((a,b)=>a+b.invoices.filter(v=>v.days).reduce((s,v)=>s+v.amount,0),0);
 document.getElementById('kpis').innerHTML=`
 <div class="kpi"><div class="v">$${money(tot)}</div><div class="l">Total outstanding</div></div>
 <div class="kpi"><div class="v" style="color:var(--amb)">$${money(od)}</div><div class="l">Overdue</div></div>
 <div class="kpi"><div class="v">${inv}</div><div class="l">Unpaid invoices</div></div>
 <div class="kpi"><div class="v">${d.length}</div><div class="l">Sites</div></div>`}
function render(){kpis();const q=document.getElementById('q').value.toLowerCase();
 let d=subset().filter(x=>x.site.toLowerCase().includes(q));
 d=d.slice().sort((a,b)=>sortKey==='count'?(b.count-a.count||b.total-a.total):(b.total-a.total||b.count-a.count));
 const el=document.getElementById('list');el.innerHTML='';
 d.forEach((s,i)=>{const div=document.createElement('div');div.className='row';
  let inv='<table><tr><th>Number</th><th>Ref</th><th>Month</th><th class="n">Amount</th><th class="n">Overdue</th></tr>';
  s.invoices.forEach(v=>{inv+=`<tr><td>${v.inv||''}</td><td class="ref">${v.ref||'—'}</td><td class="ref">${v.my||'—'}</td><td class="n">$${money(v.amount)}</td><td class="n">${v.days?`<span class="pill od">${v.days}d</span>`:`<span class="pill ok">—</span>`}</td></tr>`});
  inv+='</table>';
  const since=s.oldest?` &middot; <span class="since">unpaid from ${s.oldest}</span>`:'';
  div.innerHTML=`<div class="head" onclick="this.parentNode.classList.toggle('open')">
   <div class="rank">${i+1}</div>
   <div class="count ${cls(s.count)}"><span class="num">${s.count}</span><span class="lbl">unpaid</span></div>
   <div><div class="name">${s.site}</div><div class="badge"><span class="chev">&#9654;</span>${since||' click to expand'}</div></div>
   <div class="amt">$${money(s.total)}</div></div><div class="det">${inv}</div>`;
  el.appendChild(div)})}
tabs();render();
</script></body></html>"""

if __name__ == "__main__":
    build()
