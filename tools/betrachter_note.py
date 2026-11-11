#!/usr/bin/env python3
"""betrachter_note.py - Betrachter-Note (SPEC_BETRACHTER_NOTE, Nutzer 11.11.): Prozent der fuer das Auge SICHTBAREN Merkmale, die stimmen.
Zwei Stufen: Besucher (Sichtschwelle 0,25 m real) und Experte (0,08 m real). Kann 100 % erreichen (anders als Foto-F1, Decke ~85 %).

Eingaenge (alles generisch aus objekt.json, kein Objektname im Code):
  modelle/<objekt>/objekt.json            Bauteile (typ) - nur Teile MIT Eintrag in der Formliste haben ein Gewicht
  modelle/<objekt>/masstabelle.json       beobachtungen_offen (merkmal/teil/art/erledigt) -> Fund-Merkmale
  <kreis>/<objekt>/fotoform/*.json        neueste Formliste: sicht_px je Teil und Foto (Gewicht, Sichtbarkeit)
  <kreis>/<objekt>/*/kreis.jsonl          Protokoll: Runde angenommen UND pruefer.annehmen (Beleg fuer Status 1)
  git log                                 Revert-Commits ("Revert ... kreis <lauf> r<n>") nehmen den Beleg zurueck
  <feinsuche>/<objekt>/bericht.json       OPTIONAL (SPEC_FEINSUCHE). Erwartet: Liste oder {"cluster"|"funde"|"treffer": [..]} mit je
                                          {id|name, teil?, groesse_m?, flaeche_px?|px?, anzahl?}; jeder Eintrag = Merkmal status 0, quelle feinsuche.
                                          Fehlt die Datei: weggelassen. Eigener Pfad: --feinsuche <datei>.
Ausgabe: modelle/<objekt>/merkmale.json (Handfelder groesse_m/anzahl/status_hand+beleg_hand bleiben bei Neuerzeugung erhalten).

Status (ehrlich): 1 NUR mit Beleg (angenommene Kreis-Runde mit Pruefer 'annehmen' fuer dieses Teil, oder erledigter Fund, der auf eine
solche Runde verweist, oder status_hand=1 mit beleg_hand = Nutzer-Abnahme); 0,5 = Teil da, aber offener Fund oder kein Beleg; 0 = Fund 'fehlt' offen.
Gewicht = (mittlere sichtbare Pixel je Foto ueber ALLE Fotos der Formliste) ^ 0,5.  Fund-Gewicht = Gewicht des Teils x FUND_FAKTOR.
ANNAHMEN (Parameter unten, alle als ANNAHME gekennzeichnet): Sichtschwellen, FUND_FAKTOR, unbekannte Groesse zaehlt in BEIDEN Stufen.
Keine Tor-Wirkung: reine Anzeige/Planung.
  python3 tools/betrachter_note.py <objekt> [--trocken] [--feinsuche datei] [--top N]
"""
import sys, os, json, re, glob, subprocess, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KD = "/media/oem/scan/rc-park_kreis"
FEIN = "/media/oem/scan/rc-park_tmp/feinsuche"
SCHWELLE = {"besucher": 0.25, "experte": 0.08}   # ANNAHME: Sehschaerfe ~1 Bogenminute bei 1 m (H0 1:87 -> 87 m) bzw. 0,3 m (26 m); Parameter, nicht gemessen
FUND_FAKTOR = 0.3          # ANNAHME: ein Detail-Fund wiegt 30 % der Pixelwurzel seines Teils (kein Messwert; Pixel des Fundes sind nicht getrennt messbar)
GROESSE_UNBEKANNT_ZAEHLT = True   # ANNAHME: Merkmal ohne groesse_m zaehlt in BEIDEN Stufen (konservativ; Handfeld groesse_m setzt es)
# ANNAHME (Stichwort -> kleinste Abmessung in m real, Schaetzung aus allgemeinem Bauwissen, NICHT gemessen; Handfeld groesse_m in merkmale.json hat Vorrang,
# danach bleibt das Merkmal 'unbekannt' = zaehlt in beiden Stufen). Reihenfolge: erste Treffer-Regel gewinnt.
GROESSE_STICHWORT = [(r"decke|dachflaeche|giebel|helm|erker|fassade|rumpf|wand|dach\b|laube\b|bogenreihe|gesims", 1.0),
                     (r"rippe|sprosse|kreuzstock|falz|fuge|schindel|ziegel|rinne|gitter|rosette|krabbe|wimperg|kapitell|profil|kehle|fase\b|baluster|schaefte|schildbogen|anfaenger|steg|zierat|ornament", 0.12),
                     (r"dienst|schaft|saeule|figur|baldachin|fiale|konsole|bruestung|gaube|fenster|tuer|nische|sockel|balkon|bogen|gewoelbe", 0.4)]
NICHT_SICHTBAR_ART = {"werkzeug", "druck"}   # Funde ohne Bildwirkung (Werkzeug-/Druckthemen) sind keine Merkmale


def schluessel(t):
    """Teilname -> Formlisten-Schluessel (typ 'a:b' -> 'a__b'; Klammerzusaetze weg)."""
    return re.sub(r"\s*\(.*$", "", str(t or "")).strip().replace(":", "__")


def neueste_formliste(obj):
    fs = [f for f in glob.glob(os.path.join(KD, obj, "fotoform", "*.json")) if not f.endswith(".tmp.teil")]
    for f in sorted(fs, key=os.path.getmtime, reverse=True):
        try:
            J = json.load(open(f))
            if J.get("teile"):
                return f, J
        except Exception:
            pass
    return None, None


def gewichte(J):
    """je Teil: (gewicht, sichtbarkeit, mittel_px). Mittel ueber ALLE Fotos der Liste (fehlend = 0)."""
    nf = max(1, len(J.get("fotos") or {}))
    out = {}
    for k, v in J["teile"].items():
        px = [e.get("sicht_px", (e.get("mk_px", 0) + e.get("fk_px", 0))) for fo, e in v.items() if fo != "_gesamt" and isinstance(e, dict)]
        px = [p for p in px if p]
        mittel = sum(px) / nf
        out[k] = (mittel ** 0.5, len(px) / nf, mittel)
    return out


def kreis_belege(obj):
    """{(lauf, runde): zeile} der angenommenen Runden mit Pruefer 'annehmen'; Reverts (git log) ausgenommen."""
    ok = {}
    for p in glob.glob(os.path.join(KD, obj, "*", "kreis.jsonl")):
        lauf = os.path.basename(os.path.dirname(p))
        for l in open(p):
            try:
                z = json.loads(l)
            except Exception:
                continue
            if z.get("angenommen") and (z.get("pruefer") or {}).get("annehmen"):
                ok[(lauf, z.get("runde"))] = z
    rev = subprocess.run(["git", "log", "--format=%s", "--grep=^Revert"], cwd=ROOT, capture_output=True, text=True).stdout
    for lauf, r in list(ok):
        if re.search(re.escape(lauf) + r"\s+r" + str(r) + r"\b", rev):
            del ok[(lauf, r)]
    hashes = {}
    for h, s in (x.split(" ", 1) for x in subprocess.run(["git", "log", "--format=%h %s", "--grep=nach main"], cwd=ROOT, capture_output=True, text=True).stdout.splitlines() if " " in x):
        m = re.search(r"kreis (\S+) r(\d+)", s)
        if m:
            hashes.setdefault((m.group(1), int(m.group(2))), h)
    return ok, hashes


def laeufe_in(text, ok):
    """Kreis-Laeufe, auf die ein Freitext verweist (voller Lauf-Name oder Kurzform a141718) -> Liste (lauf, runde) angenommener Runden."""
    res = []
    for m in re.finditer(r"(\d{8}_\d{4,6}[A-Za-z0-9]*|\ba\d{6}\b)(?:\s+r(\d+))?", str(text)):
        tok, r = m.group(1), m.group(2)
        for (lauf, rr) in ok:
            if (lauf == tok or (tok.startswith("a") and lauf.endswith(tok))) and (r is None or int(r) == rr):
                res.append((lauf, rr))
    return sorted(set(res))


def feinsuche_lesen(obj, pfad=None):
    f = pfad or os.path.join(FEIN, obj, "bericht.json")
    if not os.path.exists(f):
        return [], None
    try:
        J = json.load(open(f))
    except Exception as e:
        return [], f"unlesbar: {e}"
    L = J if isinstance(J, list) else next((J[k] for k in ("cluster", "funde", "treffer") if isinstance(J.get(k), list)), [])
    return [e for e in L if isinstance(e, dict)], f


def erzeuge(obj, feinsuche=None, schwelle=None):
    S = dict(SCHWELLE, **(schwelle or {}))
    O = json.load(open(os.path.join(ROOT, "modelle", obj, "objekt.json")))
    M = json.load(open(os.path.join(ROOT, "modelle", obj, "masstabelle.json")))
    ff, J = neueste_formliste(obj)
    if J is None:
        raise SystemExit("keine Formliste unter %s/%s/fotoform" % (KD, obj))
    G = gewichte(J)
    ok, hashes = kreis_belege(obj)
    pfad = os.path.join(ROOT, "modelle", obj, "merkmale.json")
    alt = {}
    if os.path.exists(pfad):
        try:
            alt = json.load(open(pfad))
        except Exception:
            alt = {}
    altm = {m["id"]: m for m in alt.get("merkmale", [])}
    heute = time.strftime("%Y-%m-%d")
    bauteile = {schluessel(b.get("typ")) for b in O.get("bauteile", []) if b.get("typ")}
    funde = [b for b in M.get("beobachtungen_offen", []) if b.get("merkmal") and b.get("art") not in NICHT_SICHTBAR_ART
             and not str(b.get("teil") or "").startswith("alle")]
    # Belege je Teil: erledigte Funde mit Verweis auf angenommene Runde + angenommene Runden mit ziel.teil
    teil_beleg = {}
    for (lauf, r), z in ok.items():
        teil_beleg.setdefault(schluessel(z["ziel"]["teil"]), []).append((lauf, r))
    for b in M.get("beobachtungen_offen", []):
        if b.get("erledigt") and b.get("teil"):
            for lr in laeufe_in(b["erledigt"], ok):
                teil_beleg.setdefault(schluessel(b["teil"]), []).append(lr)
    offen_je_teil = {}
    for b in funde:
        if not b.get("erledigt"):
            offen_je_teil.setdefault(schluessel(b.get("teil")), []).append(b)

    def teil_zu(k):   # Fund-Teil -> Formlisten-Teil (exakt oder Praefix-Familie)
        if k in G: return k
        c = [t for t in G if t.startswith(k + "_") or t.startswith(k)] if k else []
        return c[0] if c else None

    M_out = []

    def hand(i, m):
        h = altm.get(i, {})
        if h.get("groesse_m") is None:
            txt = (m.get("text") or m.get("id") or "").lower()
            for rx, gm in GROESSE_STICHWORT:
                if re.search(rx, txt):
                    m["groesse_m"], m["groesse_quelle"] = gm, "ANNAHME Stichwort"; break
        for f in ("groesse_m", "anzahl"):
            if h.get(f) is not None: m[f] = h[f]; m["groesse_quelle"] = "Hand" if f == "groesse_m" else m.get("groesse_quelle")
        if h.get("status_hand") is not None and h.get("beleg_hand"):
            m["status"], m["beleg"] = h["status_hand"], "Hand: " + h["beleg_hand"]; m["status_hand"] = h["status_hand"]; m["beleg_hand"] = h["beleg_hand"]
        m["erstmals"] = h.get("erstmals", heute)
        return m

    ohne_gewicht = []
    for k, (gw, sb, px) in sorted(G.items()):
        if "__ausschnitt" in k: continue
        offen = offen_je_teil.get(k, [])
        bel = sorted(set(teil_beleg.get(k, [])))
        if offen:
            st, gr = 0.5, "offener Fund: " + "; ".join(str(b["merkmal"])[:70] for b in offen[:3])
            bl = None
        elif bel:
            st, bl = 1.0, "Kreis angenommen+Pruefer annehmen: " + ", ".join("%s r%s%s" % (l, r, " (main %s)" % hashes[(l, r)] if (l, r) in hashes else "") for l, r in bel[-3:])
            gr = None
        else:
            st, bl, gr = 0.5, None, "kein Beleg (kein angenommener Kreis-Commit mit Pruefer-Urteil fuer dieses Teil)"
        m = dict(id="teil:" + k, art="teil", teil=k, groesse_m=None, anzahl=None, sichtbarkeit=round(sb, 3), gewicht=round(gw, 2),
                 sicht_px_mittel=round(px), status=st, beleg=bl, grund=gr, in_objekt=k in bauteile)
        M_out.append(hand(m["id"], m))
    ausser = sorted(b for b in bauteile if b not in G and not any(k.startswith(b) for k in G))
    for i, b in enumerate(funde):
        mt = str(b["merkmal"]).strip()
        if str(b.get("erledigt") or "").startswith(("ersetzt durch", "zusammengefuehrt")):
            continue   # Duplikat-Verweis, kein eigenes Merkmal
        tk = teil_zu(schluessel(b.get("teil")))
        gw = G[tk][0] * FUND_FAKTOR if tk else None
        mid = "fund:%s:%s" % (b.get("datum", "?"), re.sub(r"[^a-z0-9]+", "_", mt.lower())[:48])
        if gw is None:
            ohne_gewicht.append(mt[:70]); continue
        er = b.get("erledigt")
        bel = laeufe_in(er, ok) if er else []
        fehlt = b.get("art") == "fehlteil" or re.search(r"\bfehl(t|en)\b", mt, re.I)
        if er and bel and not re.search(r"\bOFFEN\b|\boffen\b", str(er)):
            st, bl, gr = 1.0, "Kreis angenommen+Pruefer annehmen: " + ", ".join("%s r%s" % x for x in bel[-2:]), None
        elif er and bel:
            st, bl, gr = 0.5, None, "erledigt mit Rest (OFFEN im Erledigt-Text)"
        elif er:
            st, bl, gr = 0.5, None, "als erledigt eingetragen, aber kein Beleg im Protokoll"
        elif mt.startswith("Pruefer-Rest"):
            st, bl, gr = 0.5, None, "Pruefer-Rest einer angenommenen Runde (offen)"
        elif fehlt:
            st, bl, gr = 0.0, None, "Fund 'fehlt', offen"
        else:
            st, bl, gr = 0.5, None, "Fund offen (Form/Lage nicht stimmig)"
        m = dict(id=mid, art="fund", teil=tk, quelle="masstabelle:" + str(b.get("wer", ""))[:60], text=mt[:160], groesse_m=None, anzahl=None,
                 sichtbarkeit=round(G[tk][1], 3), gewicht=round(gw, 2), status=st, beleg=bl, grund=gr, datum=b.get("datum"))
        M_out.append(hand(mid, m))
    fl, fpfad = feinsuche_lesen(obj, feinsuche)
    for i, e in enumerate(fl):
        nm = str(e.get("id") or e.get("name") or "f%d" % i)
        px = e.get("flaeche_px") or e.get("px")
        tk = teil_zu(schluessel(e.get("teil"))) if e.get("teil") else None
        gw = (float(px) ** 0.5) if px else (G[tk][0] * FUND_FAKTOR if tk else None)
        if gw is None: ohne_gewicht.append("feinsuche:" + nm); continue
        m = dict(id="fein:" + nm, art="feinsuche", teil=tk, groesse_m=e.get("groesse_m"), anzahl=e.get("anzahl"), sichtbarkeit=None,
                 gewicht=round(gw, 2), status=0.0, beleg=None, grund="Feinsuche-Cluster, kein Modellteil", datum=heute)
        M_out.append(hand(m["id"], m))
    # Stufen
    for m in M_out:
        g = m.get("groesse_m")
        m["stufen"] = [s for s, th in S.items() if (g is None and GROESSE_UNBEKANNT_ZAEHLT) or (g is not None and g >= th)]
        if m["status"] == 1 and not m.get("beleg"):
            raise SystemExit("Merkmal %s status 1 ohne Beleg - verboten" % m["id"])
    return dict(objekt=obj, formliste=os.path.basename(ff), feinsuche=fpfad, schwellen_m=S,
                annahmen=["Sichtschwellen Besucher 0,25 m / Experte 0,08 m (ANNAHME Sehschaerfe)",
                          "FUND_FAKTOR %.1f: Fund-Gewicht = Teil-Gewicht x Faktor (ANNAHME)" % FUND_FAKTOR,
                          "Merkmal ohne groesse_m zaehlt in beiden Stufen (ANNAHME)",
                          "Teil ohne offenen Fund und ohne Pruefer-annehmen-Beleg = 0,5 'kein Beleg' (Regel, keine Messung)"],
                bauteile_ohne_formliste=ausser, funde_ohne_teilgewicht=ohne_gewicht, merkmale=M_out,
                verlauf=alt.get("verlauf", [])), altm


def noten(D):
    r = {}
    for s in D["schwellen_m"]:
        L = [m for m in D["merkmale"] if s in m["stufen"]]
        n = sum(m["gewicht"] for m in L)
        r[s] = dict(note=round(100 * sum(m["gewicht"] * m["status"] for m in L) / n, 1) if n else None, n=len(L),
                    status={str(v): sum(m["status"] == v for m in L) for v in (1.0, 0.5, 0.0)},
                    fehlend=[(round(m["gewicht"] * (1 - m["status"]), 2), m["id"], m["status"], m.get("text") or m.get("grund")) for m in sorted(
                        L, key=lambda m: -m["gewicht"] * (1 - m["status"])) if m["status"] < 1])
    return r


def kurzzeile(obj):
    """fuer realitaet_prozent.py: nur lesen/rechnen, NICHTS schreiben (sonst schmutziger Baum, blockiert Kreis-Merges)."""
    try:
        D, _ = erzeuge(obj)
    except (SystemExit, Exception):
        return None
    n = noten(D)
    return "BETRACHTER-NOTE Besucher %.1f %% | Experte %.1f %% (%d/%d Merkmale; Sichtschwelle 0,25/0,08 m = ANNAHME; Anzeige, kein Tor)" % (
        n["besucher"]["note"], n["experte"]["note"], n["besucher"]["n"], n["experte"]["n"])


def selbsttest():
    """Synthetik: bekannte Status/Gewichte -> erwartete Noten exakt; Beleg-Pflicht; Stufenfilter."""
    D = dict(schwellen_m={"besucher": 0.25, "experte": 0.08}, merkmale=[
        dict(id="a", gewicht=4.0, status=1.0, stufen=["besucher", "experte"]),
        dict(id="b", gewicht=2.0, status=0.5, stufen=["besucher", "experte"]),
        dict(id="c", gewicht=2.0, status=0.0, stufen=["besucher", "experte"]),
        dict(id="d", gewicht=2.0, status=0.0, stufen=["experte"])])
    n = noten(D)
    assert n["besucher"]["note"] == 62.5, n["besucher"]["note"]       # (4+1)/8
    assert n["experte"]["note"] == 50.0, n["experte"]["note"]         # 5/10
    assert [x[1] for x in n["experte"]["fehlend"]][:2] == ["c", "d"] or [x[1] for x in n["experte"]["fehlend"]][:2] == ["d", "c"]
    D["merkmale"] = [dict(m, status=1.0) for m in D["merkmale"]]
    assert all(v["note"] == 100.0 for v in noten(D).values())          # 100 % erreichbar
    assert laeufe_in("kreis a141718 r1", {("20261111_141719a141718", 1): {}}) == [("20261111_141719a141718", 1)]
    assert laeufe_in("kreis a141718 r2", {("20261111_141719a141718", 1): {}}) == []
    print("Selbsttest bestanden (62,5 / 50,0 / 100,0; Laufzuordnung)")
    return 0


def main():
    a = sys.argv
    if "--selbsttest" in a: return selbsttest()
    if len(a) < 2: print(__doc__); return 1
    obj = a[1]; top = int(a[a.index("--top") + 1]) if "--top" in a else 10
    fs = a[a.index("--feinsuche") + 1] if "--feinsuche" in a else None
    D, altm = erzeuge(obj, fs)
    n = noten(D)
    neu = [m["id"] for m in D["merkmale"] if m["id"] not in altm and altm]
    D["verlauf"].append(dict(zeit=time.strftime("%Y-%m-%d %H:%M:%S"), besucher=n["besucher"]["note"], experte=n["experte"]["note"],
                             n=len(D["merkmale"]), neu_entdeckt=len(neu)))
    D["verlauf"] = D["verlauf"][-50:]
    D["noten"] = {s: {k: v for k, v in x.items() if k != "fehlend"} for s, x in n.items()}
    if "--trocken" not in a:
        json.dump(D, open(os.path.join(ROOT, "modelle", obj, "merkmale.json"), "w"), ensure_ascii=False, indent=1)
    for s in D["schwellen_m"]:
        x = n[s]
        print(f"{s.upper():9s} {x['note']:.1f} %  ({x['n']} Merkmale: status 1 = {x['status']['1.0']}, 0,5 = {x['status']['0.5']}, 0 = {x['status']['0.0']})")
    for s in D["schwellen_m"]:
        print(f"-- Top {top} fehlend ({s}), Gewicht x (1-status):")
        for g, i, st, t in n[s]["fehlend"][:top]:
            print(f"   {g:6.2f}  st {st}  {i}  | {str(t)[:90]}")
    if neu: print("NEU ENTDECKT seit letztem Lauf (%d, Nenner waechst, getrennt von Fortschritt): %s" % (len(neu), ", ".join(neu[:8])))
    if D["bauteile_ohne_formliste"]: print("ohne Formliste (kein Gewicht, nicht gezaehlt):", len(D["bauteile_ohne_formliste"]))
    if D["funde_ohne_teilgewicht"]: print("Funde ohne zuordenbares Teil (nicht gezaehlt):", len(D["funde_ohne_teilgewicht"]))
    if not D["feinsuche"]: print("Feinsuche-Bericht: nicht vorhanden (weggelassen)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
