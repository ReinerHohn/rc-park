#!/usr/bin/env python3
"""Miniaturland-Wirtschaftlichkeit: Kosten, Umsatz, Break-even, Sensitivität.

Stellschrauben als CLI-Argumente. Zwei eingebaute Szenarien (zentral/peripher)
als Presets, alles überschreibbar. Gibt Kostenaufstellung, Gewinn/Verlust,
Break-even (Besucher/Tag) und eine Sensitivitäts-Tabelle aus.

Beispiele:
  python3 tools/miniland_kalk.py                      # beide Presets + Sweep
  python3 tools/miniland_kalk.py --szenario zentral --besucher 100
  python3 tools/miniland_kalk.py --flaeche 300 --eur-m2 22 --eintritt 8
  python3 tools/miniland_kalk.py --sweep-eintritt 6,8,10,12,14
"""
import argparse

# ---- Presets (Jahreswerte in €, wo nicht anders vermerkt) -------------------
PRESETS = {
    "zentral": dict(flaeche=500, eur_m2=18.0, nk=0.25, besucher=90,
                    personal=70000, energie=12000, marketing=18000,
                    verwaltung=15000, instand=10000),
    "peripher": dict(flaeche=500, eur_m2=8.0, nk=0.25, besucher=35,
                     personal=65000, energie=12000, marketing=25000,
                     verwaltung=13000, instand=10000),
}

def miete_jahr(a):
    return a.flaeche * a.eur_m2 * 12 * (1 + a.nk)

def kosten(a):
    m = miete_jahr(a)
    posten = [("Miete warm (inkl. %d%% NK)" % round(a.nk*100), m),
              ("Personal", a.personal),
              ("Energie/Betrieb", a.energie),
              ("Marketing", a.marketing),
              ("Versicherung/Verwaltung/Sonstiges", a.verwaltung),
              ("Instandhaltung/Verbrauch", a.instand)]
    return posten, sum(p[1] for p in posten)

def kit_marge(a):
    cogs = a.kit_material + a.kit_schnitt + a.kit_verpackung
    return a.kit_preis - cogs, cogs      # (Deckungsbeitrag/Kit, COGS/Kit)

def shop_db_pro_besucher(a):
    marge, _ = kit_marge(a)
    return marge * a.kit_quote            # Marge × Kaufquote

def umsatz_pro_besucher(a):
    # Deckungsbeitrag pro Besucher: Eintritt (~0 variable Kosten) + Shop-Marge + manueller Zusatz
    return a.eintritt + shop_db_pro_besucher(a) + a.extra

def rechne(a):
    posten, gesamt = kosten(a)
    pb = umsatz_pro_besucher(a)
    umsatz = a.besucher * a.tage * pb
    gewinn = umsatz - gesamt
    be_jahr = gesamt / pb if pb else float("inf")
    be_tag = be_jahr / a.tage if a.tage else float("inf")
    return dict(posten=posten, gesamt=gesamt, pb=pb, umsatz=umsatz,
                gewinn=gewinn, be_jahr=be_jahr, be_tag=be_tag)

def eur(x):
    return f"{x:>12,.0f} €".replace(",", ".")

def report(name, a):
    r = rechne(a)
    print(f"\n{'='*60}\n  {name.upper()}  —  {a.flaeche:.0f} m² · {a.eur_m2:.0f} €/m² · "
          f"Eintritt ø {a.eintritt:.0f} €{('+%.0f Zusatz'%a.extra) if a.extra else ''} · "
          f"{a.tage} Öffnungstage\n{'='*60}")
    print("  KOSTEN / Jahr")
    for n, v in r["posten"]:
        print(f"    {n:<40}{eur(v)}")
    print(f"    {'─'*40}{'─'*14}")
    print(f"    {'SUMME Kosten':<40}{eur(r['gesamt'])}")
    marge, cogs = kit_marge(a); sdb = shop_db_pro_besucher(a)
    print(f"\n  SHOP (Lasercut-Kit)")
    print(f"    {'Verkaufspreis/Kit':<40}{eur(a.kit_preis)}")
    print(f"    {'− COGS (Material+Schnitt+Verpackung)':<40}{eur(cogs)}")
    print(f"    {'= Deckungsbeitrag/Kit':<40}{eur(marge)}")
    print(f"    {'Kaufquote → DB/Besucher (%.0f%%)'%(a.kit_quote*100):<40}{eur(sdb)}")
    print(f"\n  UMSATZ(=Deckungsbeitrag) / Jahr  ({a.besucher:.0f} Besucher/Tag × {a.tage} Tage × "
          f"{eur(r['pb']).strip()}  [Eintritt {a.eintritt:.0f} + Shop {sdb:.2f}])")
    print(f"    {'Umsatz':<40}{eur(r['umsatz'])}")
    vz = "GEWINN" if r["gewinn"] >= 0 else "VERLUST"
    print(f"\n  >>> {vz}: {eur(r['gewinn']).strip()}   "
          f"(Break-even: {r['be_tag']:.0f} Besucher/Tag = {r['be_jahr']:,.0f}/Jahr)".replace(",", "."))
    return r

def sweep(a, werte):
    print(f"\n{'─'*60}\n  SENSITIVITÄT: Gewinn/Verlust je Besucher/Tag "
          f"({a.flaeche:.0f} m², {a.eur_m2:.0f} €/m², Eintritt ø {a.eintritt:.0f} €)\n{'─'*60}")
    _, gesamt = kosten(a); pb = umsatz_pro_besucher(a)
    print(f"    {'Besucher/Tag':<16}{'Besucher/Jahr':<16}{'Gewinn/Verlust':>16}")
    for b in werte:
        u = b * a.tage * pb; g = u - gesamt
        mark = "  ✓" if g >= 0 else "  ✗"
        print(f"    {b:<16}{b*a.tage:<16,}{eur(g).strip():>16}{mark}".replace(",", "."))

def main():
    ap = argparse.ArgumentParser(description="Miniaturland-Wirtschaftlichkeits-Rechner")
    ap.add_argument("--szenario", choices=list(PRESETS)+["beide"], default="beide")
    ap.add_argument("--flaeche", type=float); ap.add_argument("--eur-m2", type=float, dest="eur_m2")
    ap.add_argument("--nk", type=float, help="Nebenkosten-Aufschlag (0.25=25%)")
    ap.add_argument("--besucher", type=float, help="Besucher/Tag")
    ap.add_argument("--tage", type=int, default=300, help="Öffnungstage/Jahr")
    ap.add_argument("--eintritt", type=float, default=10.0, help="ø Eintritt netto €")
    ap.add_argument("--extra", type=float, default=0.0, help="ø manueller Zusatz-DB/Besucher € (zusätzlich zum Shop)")
    ap.add_argument("--kit-preis", type=float, default=25.0, help="Verkaufspreis Lasercut-Kit €")
    ap.add_argument("--kit-material", type=float, default=5.0, help="Holz/Material je Kit €")
    ap.add_argument("--kit-schnitt", type=float, default=3.0, help="Laserzeit/Strom/Anteil je Kit €")
    ap.add_argument("--kit-verpackung", type=float, default=2.0, help="Verpackung+Anleitung je Kit €")
    ap.add_argument("--kit-quote", type=float, default=0.15, help="Kaufquote (0.15 = 15%% kaufen ein Kit)")
    ap.add_argument("--personal", type=float); ap.add_argument("--energie", type=float)
    ap.add_argument("--marketing", type=float); ap.add_argument("--verwaltung", type=float)
    ap.add_argument("--instand", type=float)
    ap.add_argument("--sweep", default="30,40,50,60,70,80,90,100,120,150",
                    help="Besucher/Tag-Werte für Sensitivität")
    a = ap.parse_args()

    namen = list(PRESETS) if a.szenario == "beide" else [a.szenario]
    for name in namen:
        p = dict(PRESETS[name])
        # CLI-Overrides anwenden
        for k in ("flaeche","eur_m2","nk","besucher","personal","energie",
                  "marketing","verwaltung","instand"):
            v = getattr(a, k)
            if v is not None: p[k] = v
        sa = argparse.Namespace(tage=a.tage, eintritt=a.eintritt, extra=a.extra,
                                kit_preis=a.kit_preis, kit_material=a.kit_material,
                                kit_schnitt=a.kit_schnitt, kit_verpackung=a.kit_verpackung,
                                kit_quote=a.kit_quote, **p)
        r = report(name, sa)
        if len(namen) == 1:
            sweep(sa, [int(x) for x in a.sweep.split(",")])

    if len(namen) > 1:
        # gemeinsamer Sweep mit zentral-Kostenbasis
        p = dict(PRESETS["zentral"]); p.pop("besucher", None)
        for k in ("flaeche","eur_m2","nk","personal","energie","marketing","verwaltung","instand"):
            v = getattr(a, k)
            if v is not None: p[k] = v
        sa = argparse.Namespace(tage=a.tage, eintritt=a.eintritt, extra=a.extra, besucher=0,
                                kit_preis=a.kit_preis, kit_material=a.kit_material,
                                kit_schnitt=a.kit_schnitt, kit_verpackung=a.kit_verpackung,
                                kit_quote=a.kit_quote, **p)
        sweep(sa, [int(x) for x in a.sweep.split(",")])

if __name__ == "__main__":
    main()
