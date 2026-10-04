#!/usr/bin/env python3
"""
build.py — erzeugt eine self-contained businessplan.html aus annahmen.json
und attraktionen/*.json.

Muster wie die anderen Katalog-Projekte: reine Python-Standardbibliothek,
keine Abhaengigkeiten. Das Finanzmodell lebt zusaetzlich als JavaScript in der
HTML, damit die Regler live nachrechnen. Chart.js kommt per CDN.

Aufruf:  python3 build.py        -> schreibt businessplan.html
"""

import json
import glob
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def lade_attraktionen():
    attraktionen = []
    for pfad in sorted(glob.glob(os.path.join(HERE, "attraktionen", "*.json"))):
        with open(pfad, encoding="utf-8") as f:
            attraktionen.append(json.load(f))
    return attraktionen


def lade_annahmen():
    with open(os.path.join(HERE, "annahmen.json"), encoding="utf-8") as f:
        return json.load(f)


def rechne(annahmen, attraktionen):
    """Spiegelbild des JS-Modells – fuer die Konsolen-Zusammenfassung."""
    b = annahmen["besucher"]["besucher_pro_jahr"]
    p = annahmen["preise_eur"]
    bes = annahmen["besucher"]

    avg_ticket = (
        bes["anteil_erwachsene"] * p["ticket_erwachsen"]
        + bes["anteil_kinder"] * p["ticket_kind"]
        + bes["anteil_ermaessigt"] * p["ticket_ermaessigt"]
        + bes["anteil_familienticket_haushalte"] * (p["familienticket_2e_2k"] / 4.0)
    )
    ticket_umsatz = b * avg_ticket
    gastro = b * p["umsatz_gastro_pro_besucher"]
    shop = b * p["umsatz_shop_pro_besucher"]
    jetons = b * p["umsatz_jetons_fahrzeit_pro_besucher"]
    events = p["events_firmen_pro_jahr_eur"]
    umsatz = ticket_umsatz + gastro + shop + jetons + events

    cogs = (
        gastro * annahmen["wareneinsatz"]["gastro_cogs_anteil"]
        + shop * annahmen["wareneinsatz"]["shop_cogs_anteil"]
    )

    pers = (
        annahmen["personal"]["vollzeitstellen"]
        * annahmen["personal"]["kosten_pro_vollzeit_jahr_eur"]
        + annahmen["personal"]["saisonale_aushilfen_jahr_eur"]
    )

    fl = annahmen["standort"]["flaeche_gesamt_m2"]
    miete = fl * annahmen["standort"]["miete_eur_pro_m2_monat"] * 12
    nk = fl * annahmen["standort"]["nebenkosten_eur_pro_m2_monat"] * 12

    betrieb = sum(annahmen["betriebskosten_jahr_eur"].values())

    inv = annahmen["investition"]
    attr_invest = sum(a.get("invest_eur", 0) for a in attraktionen)
    capex = (
        inv["umbau_halle_eur"]
        + inv["gastro_shop_einrichtung_eur"]
        + inv["it_kassensystem_eur"]
        + attr_invest
    )
    abschr = capex / inv["abschreibungsdauer_jahre"]
    fk = max(0, capex - inv["eigenkapital_eur"])
    zins = fk * inv["fremdkapital_zins_pa"]

    fixkosten = pers + miete + nk + betrieb + abschr
    ebit = umsatz - cogs - fixkosten
    gewinn = ebit - zins

    # Break-even in Besuchern
    deckungsbeitrag_pro_besucher = (
        avg_ticket
        + p["umsatz_gastro_pro_besucher"] * (1 - annahmen["wareneinsatz"]["gastro_cogs_anteil"])
        + p["umsatz_shop_pro_besucher"] * (1 - annahmen["wareneinsatz"]["shop_cogs_anteil"])
        + p["umsatz_jetons_fahrzeit_pro_besucher"]
    )
    netto_fix = fixkosten + zins - events
    break_even = netto_fix / deckungsbeitrag_pro_besucher if deckungsbeitrag_pro_besucher else 0

    return {
        "umsatz": umsatz,
        "ticket_umsatz": ticket_umsatz,
        "gastro": gastro,
        "shop": shop,
        "jetons": jetons,
        "events": events,
        "cogs": cogs,
        "personal": pers,
        "miete": miete,
        "nebenkosten": nk,
        "betrieb": betrieb,
        "abschreibung": abschr,
        "zins": zins,
        "capex": capex,
        "attr_invest": attr_invest,
        "ebit": ebit,
        "gewinn": gewinn,
        "break_even": break_even,
        "avg_ticket": avg_ticket,
        "db_pro_besucher": deckungsbeitrag_pro_besucher,
    }


def eur(x):
    return f"{x:,.0f} €".replace(",", ".")


HTML = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RC-Park Freiburg — Businessplan</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg:#0f1720; --card:#1a2530; --ink:#e8eef3; --muted:#8aa0b2;
    --accent:#2dd4bf; --warn:#f59e0b; --good:#34d399; --bad:#f87171;
    --line:#2a3a48;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
         background:var(--bg); color:var(--ink); line-height:1.5; }}
  header {{ padding:28px 20px; background:linear-gradient(135deg,#0d3b3a,#0f1720);
           border-bottom:1px solid var(--line); }}
  h1 {{ margin:0 0 6px; font-size:26px; }}
  header p {{ margin:0; color:var(--muted); max-width:70ch; }}
  .wrap {{ max-width:1180px; margin:0 auto; padding:20px; }}
  .kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:14px; margin:18px 0; }}
  .kpi {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px; }}
  .kpi .label {{ color:var(--muted); font-size:13px; }}
  .kpi .val {{ font-size:26px; font-weight:700; margin-top:4px; }}
  .kpi .sub {{ font-size:12px; color:var(--muted); margin-top:2px; }}
  .good {{ color:var(--good); }} .bad {{ color:var(--bad); }} .warn {{ color:var(--warn); }}
  .grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }}
  @media(max-width:860px){{ .grid2 {{ grid-template-columns:1fr; }} }}
  .panel {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:18px; margin:18px 0; }}
  .panel h2 {{ margin:0 0 14px; font-size:18px; }}
  .slider {{ margin:12px 0; }}
  .slider label {{ display:flex; justify-content:space-between; font-size:14px; margin-bottom:4px; }}
  .slider label b {{ color:var(--accent); }}
  input[type=range] {{ width:100%; accent-color:var(--accent); }}
  table {{ width:100%; border-collapse:collapse; font-size:14px; }}
  th,td {{ text-align:left; padding:9px 8px; border-bottom:1px solid var(--line); }}
  th {{ color:var(--muted); font-weight:600; }}
  td.num, th.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  .pill {{ display:inline-block; font-size:11px; padding:2px 8px; border-radius:20px;
          background:#0d3b3a; color:var(--accent); border:1px solid #1d5a56; }}
  .wow {{ color:var(--warn); letter-spacing:1px; }}
  .attr-card {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
              padding:16px; }}
  .attr-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:14px; }}
  .attr-card h3 {{ margin:0 0 6px; font-size:16px; }}
  .attr-card .meta {{ font-size:12px; color:var(--muted); margin:8px 0; }}
  .attr-card ul {{ margin:8px 0 0; padding-left:18px; font-size:13px; color:#cdd8e1; }}
  .chartbox {{ position:relative; height:280px; }}
  footer {{ color:var(--muted); font-size:12px; padding:30px 20px; text-align:center; }}
  .note {{ font-size:12px; color:var(--muted); margin-top:8px; }}
</style>
</head>
<body>
<header>
  <h1>🏎️ RC-Park Freiburg — Businessplan</h1>
  <p>Indoor-Erlebniswelt zum <b>Selbststeuern</b> von RC-Fahrzeugen, -Schiffen und -Flugobjekten.
     Wetterunabhängiges Ganzjahresziel für Freiburgs ~1 Mio Tagesgäste und 2,17 Mio Übernachtungen.
     Alle Zahlen sind editierbare Annahmen — zieh an den Reglern.</p>
</header>
<div class="wrap">

  <div class="kpis" id="kpis"></div>

  <div class="panel">
    <h2>⚙️ Annahmen (live)</h2>
    <div class="grid2">
      <div>
        <div class="slider"><label>Besucher / Jahr <b id="l_bes"></b></label>
          <input type="range" id="s_bes" min="40000" max="200000" step="5000"></div>
        <div class="slider"><label>Ticket Erwachsene <b id="l_terw"></b></label>
          <input type="range" id="s_terw" min="12" max="32" step="1"></div>
        <div class="slider"><label>Gastro-Umsatz / Besucher <b id="l_gastro"></b></label>
          <input type="range" id="s_gastro" min="0" max="15" step="0.5"></div>
      </div>
      <div>
        <div class="slider"><label>Miete €/m²·Monat <b id="l_miete"></b></label>
          <input type="range" id="s_miete" min="5" max="22" step="0.5"></div>
        <div class="slider"><label>Fläche (m²) <b id="l_flaeche"></b></label>
          <input type="range" id="s_flaeche" min="1000" max="4000" step="100"></div>
        <div class="slider"><label>Vollzeitstellen <b id="l_fte"></b></label>
          <input type="range" id="s_fte" min="10" max="40" step="1"></div>
      </div>
    </div>
    <p class="note" id="reset_note">Tipp: <a href="#" id="reset" style="color:var(--accent)">Annahmen zurücksetzen</a></p>
  </div>

  <div class="grid2">
    <div class="panel"><h2>💶 Umsatz-Struktur</h2><div class="chartbox"><canvas id="umsatzChart"></canvas></div></div>
    <div class="panel"><h2>📉 Kostenblöcke (p.a.)</h2><div class="chartbox"><canvas id="kostenChart"></canvas></div></div>
  </div>

  <div class="panel">
    <h2>⚖️ Break-even: Gewinn in Abhängigkeit der Besucherzahl</h2>
    <div class="chartbox"><canvas id="beChart"></canvas></div>
    <p class="note" id="be_note"></p>
  </div>

  <div class="panel">
    <h2>🎢 Attraktionen & Investition</h2>
    <table id="attrTable">
      <thead><tr>
        <th>Attraktion</th><th>Kategorie</th><th class="num">Fläche m²</th>
        <th class="num">Invest</th><th>Wow</th>
      </tr></thead>
      <tbody></tbody>
    </table>
  </div>

  <div class="panel">
    <h2>📋 Attraktionen im Detail</h2>
    <div class="attr-grid" id="attrCards"></div>
  </div>

</div>
<footer>
  rc-park · build.py · Zahlen = begründete Schätzungen (Stand 2026), keine Finanzberatung.
  Benchmarks: Miniatur Wunderland Hamburg (>1 Mio Besucher, 42,7 Mio € Umsatz), Freiburg-Tourismus (2,17 Mio Übernachtungen 2024).
</footer>

<script>
const ANNAHMEN = __ANNAHMEN__;
const ATTRAKTIONEN = __ATTRAKTIONEN__;

function eur(x){{ return Math.round(x).toLocaleString('de-DE') + ' €'; }}
function eurk(x){{ return Math.round(x/1000).toLocaleString('de-DE') + 'k €'; }}

// --- Finanzmodell (Spiegel von rechne() in build.py) ---
function modell(ov){{
  const a = ANNAHMEN, p = a.preise_eur, bes = a.besucher, w = a.wareneinsatz;
  const b        = ov.besucher;
  const t_erw    = ov.ticket_erwachsen;
  const gastroPB = ov.gastro_pb;
  const miete_m2 = ov.miete_m2;
  const flaeche  = ov.flaeche;
  const fte      = ov.fte;

  const avg_ticket = bes.anteil_erwachsene*t_erw
    + bes.anteil_kinder*p.ticket_kind
    + bes.anteil_ermaessigt*p.ticket_ermaessigt
    + bes.anteil_familienticket_haushalte*(p.familienticket_2e_2k/4);

  const ticket = b*avg_ticket;
  const gastro = b*gastroPB;
  const shop   = b*p.umsatz_shop_pro_besucher;
  const jetons = b*p.umsatz_jetons_fahrzeit_pro_besucher;
  const events = p.events_firmen_pro_jahr_eur;
  const umsatz = ticket+gastro+shop+jetons+events;

  const cogs = gastro*w.gastro_cogs_anteil + shop*w.shop_cogs_anteil;
  const personal = fte*a.personal.kosten_pro_vollzeit_jahr_eur + a.personal.saisonale_aushilfen_jahr_eur;
  const miete = flaeche*miete_m2*12;
  const nk    = flaeche*a.standort.nebenkosten_eur_pro_m2_monat*12;
  const betrieb = Object.values(a.betriebskosten_jahr_eur).reduce((s,x)=>s+x,0);

  const attrInvest = ATTRAKTIONEN.reduce((s,x)=>s+(x.invest_eur||0),0);
  const inv = a.investition;
  const capex = inv.umbau_halle_eur + inv.gastro_shop_einrichtung_eur + inv.it_kassensystem_eur + attrInvest;
  const abschr = capex/inv.abschreibungsdauer_jahre;
  const fk = Math.max(0, capex - inv.eigenkapital_eur);
  const zins = fk*inv.fremdkapital_zins_pa;

  const fixkosten = personal+miete+nk+betrieb+abschr;
  const ebit = umsatz-cogs-fixkosten;
  const gewinn = ebit-zins;

  const dbPB = avg_ticket
    + gastroPB*(1-w.gastro_cogs_anteil)
    + p.umsatz_shop_pro_besucher*(1-w.shop_cogs_anteil)
    + p.umsatz_jetons_fahrzeit_pro_besucher;
  const nettoFix = fixkosten+zins-events;
  const breakEven = dbPB>0 ? nettoFix/dbPB : 0;

  return {{umsatz,ticket,gastro,shop,jetons,events,cogs,personal,miete,nk,betrieb,
           abschr,zins,capex,attrInvest,ebit,gewinn,breakEven,dbPB,avg_ticket}};
}}

const DEFAULTS = {{
  besucher: ANNAHMEN.besucher.besucher_pro_jahr,
  ticket_erwachsen: ANNAHMEN.preise_eur.ticket_erwachsen,
  gastro_pb: ANNAHMEN.preise_eur.umsatz_gastro_pro_besucher,
  miete_m2: ANNAHMEN.standort.miete_eur_pro_m2_monat,
  flaeche: ANNAHMEN.standort.flaeche_gesamt_m2,
  fte: ANNAHMEN.personal.vollzeitstellen,
}};
let state = {{...DEFAULTS}};

let umsatzChart, kostenChart, beChart;

function renderKpis(m){{
  const marge = (m.gewinn/m.umsatz*100);
  const sicherheit = ((state.besucher-m.breakEven)/state.besucher*100);
  const payback = m.gewinn>0 ? (ANNAHMEN.investition.eigenkapital_eur/m.gewinn) : Infinity;
  const cards = [
    ['Umsatz p.a.', eur(m.umsatz), 'Tickets + Gastro + Shop + Events', ''],
    ['Gewinn vor Steuer', eur(m.gewinn), 'Marge ' + marge.toFixed(1) + '%', m.gewinn>=0?'good':'bad'],
    ['Break-even', Math.round(m.breakEven).toLocaleString('de-DE') + ' Besucher',
       (sicherheit>=0?'+':'') + sicherheit.toFixed(0) + '% Sicherheitspuffer', sicherheit>=10?'good':(sicherheit>=0?'warn':'bad')],
    ['Investition (CapEx)', eur(m.capex), 'davon Attraktionen ' + eur(m.attrInvest), ''],
    ['Ø Ticket', eur(m.avg_ticket), 'Deckungsbeitrag ' + eur(m.dbPB) + '/Besucher', ''],
    ['Amortisation EK', isFinite(payback)? payback.toFixed(1)+' Jahre':'—', 'auf ' + eur(ANNAHMEN.investition.eigenkapital_eur) + ' Eigenkapital', payback<=5?'good':'warn'],
  ];
  document.getElementById('kpis').innerHTML = cards.map(c=>
    `<div class="kpi"><div class="label">${{c[0]}}</div>
     <div class="val ${{c[3]}}">${{c[1]}}</div><div class="sub">${{c[2]}}</div></div>`).join('');
}}

function renderCharts(m){{
  const uData = [m.ticket, m.gastro, m.shop, m.jetons, m.events];
  const uLabels = ['Tickets','Gastronomie','Shop','Jetons/Fahrzeit','Events/Firmen'];
  const kData = [m.cogs, m.personal, m.miete+m.nk, m.betrieb, m.abschr, m.zins];
  const kLabels = ['Wareneinsatz','Personal','Miete+NK','Betrieb','Abschreibung','Zins'];
  const palette = ['#2dd4bf','#34d399','#60a5fa','#f59e0b','#f87171','#a78bfa'];

  if(!umsatzChart){{
    umsatzChart = new Chart(document.getElementById('umsatzChart'), {{
      type:'doughnut',
      data:{{labels:uLabels, datasets:[{{data:uData, backgroundColor:palette, borderColor:'#1a2530'}}]}},
      options:{{plugins:{{legend:{{labels:{{color:'#e8eef3'}}}},
        tooltip:{{callbacks:{{label:c=>c.label+': '+eur(c.raw)}}}}}}, maintainAspectRatio:false}}
    }});
    kostenChart = new Chart(document.getElementById('kostenChart'), {{
      type:'bar',
      data:{{labels:kLabels, datasets:[{{data:kData, backgroundColor:palette}}]}},
      options:{{plugins:{{legend:{{display:false}},
        tooltip:{{callbacks:{{label:c=>eur(c.raw)}}}}}},
        scales:{{x:{{ticks:{{color:'#8aa0b2'}}}},y:{{ticks:{{color:'#8aa0b2',callback:v=>eurk(v)}}}}}},
        maintainAspectRatio:false}}
    }});
  }} else {{
    umsatzChart.data.datasets[0].data = uData; umsatzChart.update();
    kostenChart.data.datasets[0].data = kData; kostenChart.update();
  }}

  // Break-even Linie
  const xs=[], ys=[];
  for(let b=0; b<=200000; b+=10000){{
    const mm = modell({{...state, besucher:b}});
    xs.push((b/1000)+'k'); ys.push(Math.round(mm.gewinn));
  }}
  if(!beChart){{
    beChart = new Chart(document.getElementById('beChart'), {{
      type:'line',
      data:{{labels:xs, datasets:[{{label:'Gewinn p.a.', data:ys, borderColor:'#2dd4bf',
        backgroundColor:'rgba(45,212,191,.12)', fill:true, tension:.2, pointRadius:0}}]}},
      options:{{plugins:{{legend:{{labels:{{color:'#e8eef3'}}}},
        tooltip:{{callbacks:{{label:c=>eur(c.raw)}}}}}},
        scales:{{x:{{ticks:{{color:'#8aa0b2'}}}},
          y:{{grid:{{color:ctx=>ctx.tick.value===0?'#f87171':'#2a3a48'}},
             ticks:{{color:'#8aa0b2',callback:v=>eurk(v)}}}}}},
        maintainAspectRatio:false}}
    }});
  }} else {{
    beChart.data.datasets[0].data = ys; beChart.update();
  }}
  document.getElementById('be_note').textContent =
    'Gewinnschwelle bei ~' + Math.round(m.breakEven).toLocaleString('de-DE') +
    ' Besuchern/Jahr. Geplant: ' + state.besucher.toLocaleString('de-DE') + '.';
}}

function renderAttraktionen(){{
  const rows = ATTRAKTIONEN.slice().sort((a,b)=>(b.invest_eur||0)-(a.invest_eur||0));
  document.querySelector('#attrTable tbody').innerHTML = rows.map(a=>
    `<tr><td>${{a.icon||''}} ${{a.name}}</td><td><span class="pill">${{a.kategorie}}</span></td>
     <td class="num">${{a.flaeche_m2}}</td><td class="num">${{eur(a.invest_eur||0)}}</td>
     <td class="wow">${{'★'.repeat(a.wow||0)}}</td></tr>`).join('') +
    `<tr><td><b>Summe Attraktionen</b></td><td></td>
     <td class="num"><b>${{rows.reduce((s,a)=>s+(a.flaeche_m2||0),0)}}</b></td>
     <td class="num"><b>${{eur(rows.reduce((s,a)=>s+(a.invest_eur||0),0))}}</b></td><td></td></tr>`;

  document.getElementById('attrCards').innerHTML = rows.map(a=>
    `<div class="attr-card"><h3>${{a.icon||''}} ${{a.name}}</h3>
      <div><span class="pill">${{a.kategorie}}</span> <span class="wow">${{'★'.repeat(a.wow||0)}}</span></div>
      <p style="font-size:13px;color:#cdd8e1;margin:10px 0">${{a.beschreibung}}</p>
      <div class="meta">💡 <b>USP:</b> ${{a.usp||''}}</div>
      <div class="meta">${{a.flaeche_m2}} m² · Invest ${{eur(a.invest_eur||0)}} · Zielgruppe: ${{(a.zielgruppe||[]).join(', ')}}</div>
      <ul>${{(a.highlights||[]).map(h=>`<li>${{h}}</li>`).join('')}}</ul>
    </div>`).join('');
}}

function syncLabels(){{
  document.getElementById('l_bes').textContent = state.besucher.toLocaleString('de-DE');
  document.getElementById('l_terw').textContent = eur(state.ticket_erwachsen);
  document.getElementById('l_gastro').textContent = state.gastro_pb.toFixed(1)+' €';
  document.getElementById('l_miete').textContent = state.miete_m2.toFixed(1)+' €';
  document.getElementById('l_flaeche').textContent = state.flaeche.toLocaleString('de-DE');
  document.getElementById('l_fte').textContent = state.fte;
}}

function update(){{
  const m = modell(state);
  syncLabels(); renderKpis(m); renderCharts(m);
}}

function bind(id, key, parse){{
  const el = document.getElementById(id);
  el.value = state[key];
  el.addEventListener('input', ()=>{{ state[key] = parse(el.value); update(); }});
}}

bind('s_bes','besucher',parseFloat);
bind('s_terw','ticket_erwachsen',parseFloat);
bind('s_gastro','gastro_pb',parseFloat);
bind('s_miete','miete_m2',parseFloat);
bind('s_flaeche','flaeche',parseFloat);
bind('s_fte','fte',parseFloat);

document.getElementById('reset').addEventListener('click', e=>{{
  e.preventDefault(); state={{...DEFAULTS}};
  ['s_bes','s_terw','s_gastro','s_miete','s_flaeche','s_fte'].forEach((id,i)=>{{
    document.getElementById(id).value = Object.values(DEFAULTS)[i];
  }});
  update();
}});

renderAttraktionen();
update();
</script>
</body>
</html>
"""


def main():
    annahmen = lade_annahmen()
    attraktionen = lade_attraktionen()
    m = rechne(annahmen, attraktionen)

    html = (
        HTML.replace("__ANNAHMEN__", json.dumps(annahmen, ensure_ascii=False))
        .replace("__ATTRAKTIONEN__", json.dumps(attraktionen, ensure_ascii=False))
    )
    out = os.path.join(HERE, "businessplan.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    print("== RC-Park Freiburg — Businessplan ==")
    print(f"Attraktionen:        {len(attraktionen)}")
    print(f"Investition (CapEx): {eur(m['capex'])}  (davon Attraktionen {eur(m['attr_invest'])})")
    print(f"Umsatz p.a.:         {eur(m['umsatz'])}")
    print(f"  Tickets            {eur(m['ticket_umsatz'])}  (Ø {eur(m['avg_ticket'])}/Besucher)")
    print(f"  Gastro/Shop/Jetons {eur(m['gastro'] + m['shop'] + m['jetons'])}")
    print(f"  Events/Firmen      {eur(m['events'])}")
    print(f"Kosten:              Personal {eur(m['personal'])}, Miete+NK {eur(m['miete'] + m['nebenkosten'])},")
    print(f"                     Betrieb {eur(m['betrieb'])}, Abschr. {eur(m['abschreibung'])}, Zins {eur(m['zins'])}")
    print(f"EBIT:                {eur(m['ebit'])}")
    print(f"Gewinn vor Steuer:   {eur(m['gewinn'])}  (Marge {m['gewinn'] / m['umsatz'] * 100:.1f} %)")
    print(f"Break-even:          {m['break_even']:,.0f} Besucher/Jahr".replace(",", "."))
    print(f"\n-> geschrieben: {out}")


if __name__ == "__main__":
    main()
