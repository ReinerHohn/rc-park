#!/usr/bin/env python3
"""wandlage_fotokanten.py - KOERPERWAND AUF DIE FOTOKANTEN-EBENE (24.11.2026, Kettenstufe 'bauplan', nach bauplan_ebenen, vor bauen_mit_bauplan).

Befund 1122x (audit/ebenen_abweichung.json, Fassade f00 'erfunden 0,98 / Form fehlt 0,73'): die Koerperwand lag auf der LoD2-Fassadenebene (w = 0), die triangulierten
Fotokanten 0,32-0,38 m DAHINTER, die dichte Wolke ebenfalls (-0,40). Gemessen an allen Fassaden des Schwabentors: f00 -0,32 / f01 -0,27 (beide Wolke bestaetigt),
f02 nicht belastbar (Wolke -0,36), f03 +0,10 (Wolke 0,00, Fotokanten-Median -0,05: widerspruechlich). KERNMETHODE: Form = Fotokanten, LoD2/Wolke nur Lage-Veto.
Je Wand-Ebene aus <ebenen>/ebenen.json (tools/ebenen_bauplan.py: w = RANSAC-Wandebene der Fotokanten-Sweepzellen, fassade_tiefe 'wand_ebene'):
  UEBERNOMMEN nur, wenn
    (a) Fotokanten-Ebene belastbar: Wandebene vorhanden ('neigung' = RANSAC-Ebene, sonst w = 0 Ersatz), Sweep-Punkte >= --min_punkte, Anteil auf der Ebene (+-tol) >= --min_anteil,
        Streuung (Median |w - w_ebene| der Punkte) <= tol;
    (b) |w| >= --min_versatz (sonst liegt die Wand schon auf der Ebene - nichts zu tun);
    (c) dichte Wolke bestaetigt DIESELBE Seite: Modus der Wolken-Tiefe im Wandfeld hat dasselbe Vorzeichen wie w und liegt <= tol von w.
  Sonst bleibt die alte Ebene (LoD2) und die Zeile nennt den Grund.
Uebernommene Waende werden als Korrektur art 'wandversatz' (id 'wl_<fassade>', quelle dieses Werkzeug) in audit/schleife_korrekturen.json geschrieben; eigene Eintraege
eines frueheren Laufs werden ersetzt, fremde (tools/ebenen_schleife.py) bleiben. Dort liest sie schon jeder Verbraucher:
  bauteile.korrekturen_aus_json(art='wandversatz') setzt die Wand am GRUNDKOERPER (vor Relief/Fenster/Vorbau) als durchgehende Scheibe ueber die ganze Wandbreite zurueck ->
  die Nachbarwaende enden an der neuen Flucht (Ecke ohne Spalt/Ueberlappung); Reliefs/Fotosteine/Ortsteine sitzen per Stab-Sonde auf der gebauten Koerperflaeche
  (fassaden_kette.koerper_flaeche), Uhr (uhren_aus_json) und Zusatzkaesten reichen bis hinter die neue Wand, fenster_aus_json schneidet ab der neuen Wand
  (bauteile.wandversatz_fassade), der Messkoerper (fassade_ortho --messflaeche eben) liegt im naechsten Lauf auf der neuen Wand.
  ANNAHME: das Dach bleibt auf dem LoD2-Grundriss (Traufe steht dann |w| ueber - Dachueberstand); die Scheibe endet an der Fassaden-Oberkante.
Ausgabe: je Fassade EINE Zeile 'WANDLAGE fNN: alt w ..., neu w ..., Beleg ..., uebernommen ja/nein (Grund)' (Kettenlog) + audit/wandlage_fotokanten.json.
Aufruf: wandlage_fotokanten.py <objekt.json> <ebenen-ordner> [--wolke npy] [--fassade <fassade-ordner>] [--tol 0.15] [--trocken]     rc 0 (Bericht; auch wenn nichts uebernommen), rc 3 = keine ebenen.json.
"""
import sys, os, json, argparse, time, numpy as np

HIER = os.path.dirname(os.path.abspath(__file__))
QUELLE = "tools/wandlage_fotokanten.py"


def wolke_modus(WO, e, schritt=0.04, reich=2.5, rand=0.5):
    """Modus der Wolken-Tiefe w (gegen die Fassadenebene o/n, + = aussen) im Wandfeld (Zone um 'rand' eingerueckt, |w| < reich). None, wenn < 100 Punkte."""
    if WO is None: return None, 0
    o = np.array(e["o"], float); d = np.array(e["d"], float); n = np.array(e["n"], float); u0, u1, z0, z1 = e["zone"]
    u = (WO[:, :2] - o) @ d; w = (WO[:, :2] - o) @ n; z = WO[:, 2]
    m = (u > u0 + rand) & (u < u1 - rand) & (z > max(z0, 0.0) + rand) & (z < z1 - rand) & (np.abs(w) < reich)
    if m.sum() < 100: return None, int(m.sum())
    h, b = np.histogram(w[m], bins=np.arange(-reich, reich + schritt, schritt)); k = int(np.argmax(h))
    return round(float(b[k] + schritt / 2), 3), int(m.sum())


def kanten_beleg(e):
    """Fotokanten-Beleg der Wandebene: (punkte, anteil auf der Ebene, Streuung = Median |w - w_ebene|). Punkte aus e['sweep'] (falls lesbar), sonst aus ebenen.json."""
    n_ = int(e.get("punkte") or 0); anteil = e.get("auf_ebene_anteil"); streu = None
    if e.get("sweep") and os.path.exists(e["sweep"]):
        try:
            P = np.load(e["sweep"])["P"].astype(float); o = np.array(e["o"], float); d = np.array(e["d"], float); n = np.array(e["n"], float); u0, u1, z0, z1 = e["zone"]
            u = (P[:, :2] - o) @ d; z = P[:, 2]; w = (P[:, :2] - o) @ n - float(e["w"])
            ne = e.get("neigung")
            if ne: w = w - (ne["b_u"] * (u - ne["u_ref"]) + ne["c_z"] * (z - ne["z_ref"]))
            m = (u >= u0) & (u <= u1) & (z >= max(z0, 0.0)) & (z <= z1); w = w[m]; n_ = int(m.sum())
            if n_: streu = round(float(np.median(np.abs(w))), 3)
        except Exception: pass
    return n_, anteil, streu


def entscheiden(e, w_wolke, tol=0.15, min_punkte=300, min_anteil=0.5, min_versatz=0.08, w_alt=0.0):
    """Eine Wand: -> dict(alt_w, neu_w, uebernommen, grund, beleg). Gueltigkeits-Guard (a)-(c) siehe Kopf; alt_w = Koerperwand (LoD2-Fassadenebene, w 0)."""
    w = float(e["w"]); n_, anteil, streu = kanten_beleg(e)
    beleg = dict(w_fotokanten=round(w, 3), punkte=n_, auf_ebene_anteil=anteil, streuung=streu, ransac=bool(e.get("neigung")), w_wolke=w_wolke)
    gr = []
    if not e.get("neigung"): gr.append("keine RANSAC-Wandebene der Fotokanten (fassade_tiefe nicht belastbar)")
    if n_ < min_punkte: gr.append(f"nur {n_} Fotokantenpunkte (< {min_punkte})")
    if anteil is None or anteil < min_anteil: gr.append(f"Anteil auf der Ebene {anteil} (< {min_anteil})")
    if streu is None or streu > tol: gr.append(f"Streuung {streu} m (> {tol})")
    if abs(w - w_alt) < min_versatz: gr.append(f"Versatz {w - w_alt:+.3f} m unter {min_versatz} m - Wand liegt schon auf der Ebene")
    if w_wolke is None: gr.append("keine Wolken-Gegenprobe (zu wenig Wolkenpunkte im Wandfeld)")
    elif not ((w_wolke - w_alt) * (w - w_alt) > 0 and abs(w_wolke - w) <= tol): gr.append(f"Wolke bestaetigt nicht (Wolke {w_wolke:+.3f}, Fotokanten {w:+.3f}, Toleranz {tol})")
    ok = not gr
    return dict(id=e["id"], fassade=e["fassade"], alt_w=round(w_alt, 3), neu_w=round(w if ok else w_alt, 3), uebernommen=ok, grund="; ".join(gr) if gr else "Fotokanten belastbar, Wolke bestaetigt", beleg=beleg)


def ecken_u(e, nachbarn, winkel=5.0, such=1.0, ueber=0.05):
    """Wandenden an den AUSSENECKEN: je Ende die Nachbarfassade (fassaden.json), deren Normale um < winkel Grad in Richtung -d (Ende u0) bzw. +d (Ende u1) zeigt und deren
    Ebene die Wandlinie innerhalb 'such' m vom Zonenende schneidet -> u der Nachbarebene + 'ueber' (Scheibe reicht 5 cm in die Luft ueber die Ecke, kein Restgrat, kein
    koplanarer Schnitt). Die Zone der Fassade endet oft vor/hinter der Ecke (Schwabentor f00: Zone -6,02, Ecke f02 -6,19). Ohne passenden Nachbarn (Innenecke, Freiende):
    Zonenende. -> (u0, u1, belege)."""
    o = np.array(e["o"], float); d = np.array(e["d"], float); u0, u1 = float(e["zone"][0]), float(e["zone"][1]); c = np.cos(np.radians(winkel)); bel = {}
    for ende, s_ in (("u0", -1.0), ("u1", 1.0)):
        best = None
        for F in nachbarn:
            nb = np.array(F["n"], float); dn = float(d @ nb)
            if s_ * dn < c: continue
            u_ = float((np.array(F["o"], float) - o) @ nb / dn); ue = u0 if ende == "u0" else u1
            if abs(u_ - ue) <= such and (best is None or abs(u_ - ue) < abs(best[0] - ue)): best = (u_, F.get("id"))
        if best:
            bel[ende] = dict(nachbar=best[1], u_ecke=round(best[0], 3))
            if ende == "u0": u0 = best[0] - ueber
            else: u1 = best[0] + ueber
    return u0, u1, bel


def korrektur(e, E, nachbarn=()):
    """Korrektureintrag art 'wandversatz' (Format wie tools/ebenen_schleife.py) fuer bauteile.korrekturen_aus_json: Scheibe ueber die GANZE Wand bis an die Aussenecken
    (ecken_u), z vom Boden (5 cm darunter, kein Restsplitter an der Grundflaeche) bis zur Fassaden-Oberkante."""
    _, _, z0, z1 = e["zone"]; u0, u1, bel = ecken_u(e, nachbarn); E["beleg"]["ecken"] = bel
    return dict(id=f"wl_{e['fassade']}", ebene=e["id"], art="wandversatz", schluessel=None, fassade=e["fassade"], o=e["o"], d=e["d"], n=e["n"], u0=round(u0, 3), u1=round(u1, 3), z0=min(z0, 0.0) - 0.05, z1=z1,
                w_ist=E["alt_w"], w_soll=E["neu_w"], angenommen=True, quelle=QUELLE, zeit=time.strftime("%Y-%m-%d %H:%M"),
                grund=f"Wandebene {e['id']} aus Fotokanten {E['neu_w']:+.2f} m gegen die Koerperwand (Wolke {E['beleg']['w_wolke']:+.2f}); {E['beleg']['punkte']} Kantenpunkte, Streuung {E['beleg']['streuung']} m")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("ebenen"); ap.add_argument("--wolke"); ap.add_argument("--fassade", help="Fassaden-Ordner (fassaden.json): Nachbarebenen fuer die Wandenden an den Ecken"); ap.add_argument("--tol", type=float, default=0.15)
    ap.add_argument("--min_punkte", type=int, default=300); ap.add_argument("--min_anteil", type=float, default=0.5); ap.add_argument("--min_versatz", type=float, default=0.08)
    ap.add_argument("--trocken", action="store_true", help="nur messen und Zeilen ausgeben, nichts schreiben"); a = ap.parse_args()
    ej = os.path.join(a.ebenen, "ebenen.json"); od = os.path.dirname(os.path.abspath(a.objekt)); A = os.path.join(od, "audit"); kp = os.path.join(A, "schleife_korrekturen.json")
    if not os.path.exists(ej):
        if os.path.exists(kp) and not a.trocken:      # Altstand: eigene Eintraege eines frueheren Laufs entfernen (ohne Beleg dieses Laufs gilt die alte Ebene)
            KO = json.load(open(kp)); KO["korrekturen"] = [k for k in KO.get("korrekturen", []) if k.get("quelle") != QUELLE]; json.dump(KO, open(kp, "w"), indent=1)
        print(f"WANDLAGE: {ej} fehlt - Koerperwaende bleiben auf der LoD2-Ebene"); return 3
    os.makedirs(A, exist_ok=True)
    WO = np.asarray(np.load(a.wolke, mmap_mode="r")[::4, :3], dtype=np.float64) if a.wolke and os.path.exists(a.wolke) else None
    fj = os.path.join(a.fassade, "fassaden.json") if a.fassade else ""; NB = json.load(open(fj))["fassaden"] if fj and os.path.exists(fj) else []
    ER = []; KN = []
    for e in json.load(open(ej))["ebenen"]:
        if e.get("art") != "wand": continue
        ww, nw = wolke_modus(WO, e); E = entscheiden(e, ww, a.tol, a.min_punkte, a.min_anteil, a.min_versatz); E["beleg"]["wolke_punkte"] = nw; ER.append(E)
        if E["uebernommen"]: KN.append(korrektur(e, E, [F for F in NB if F.get("id") != e["fassade"]]))
        b = E["beleg"]
        print(f"WANDLAGE {E['fassade']}: alt w {E['alt_w']:+.3f} m, neu w {E['neu_w']:+.3f} m, Beleg Fotokanten {b['w_fotokanten']:+.3f} ({b['punkte']} Pkt, {b['auf_ebene_anteil']} auf Ebene, "
              f"Streuung {b['streuung']}) Wolke {('%+.3f' % b['w_wolke']) if b['w_wolke'] is not None else '-'} ({nw} Pkt), uebernommen {'ja' if E['uebernommen'] else 'nein'} ({E['grund']})"
              + (f", Ecken {b['ecken']}" if b.get("ecken") else ""), flush=True)
    if a.trocken: print(f"-> TROCKEN: {len(KN)} von {len(ER)} Waenden wuerden auf die Fotokanten-Ebene gesetzt (nichts geschrieben)"); return 0
    KO = json.load(open(kp)) if os.path.exists(kp) else dict(quelle=QUELLE, korrekturen=[])
    KO["korrekturen"] = [k for k in KO.get("korrekturen", []) if k.get("quelle") != QUELLE] + KN
    json.dump(KO, open(kp, "w"), indent=1)
    json.dump(dict(quelle=QUELLE, zeit=time.strftime("%Y-%m-%d %H:%M"), tol=a.tol, waende=ER), open(os.path.join(A, "wandlage_fotokanten.json"), "w"), indent=1)
    print(f"-> {len(KN)} von {len(ER)} Waenden auf die Fotokanten-Ebene gesetzt ({kp})"); return 0


if __name__ == "__main__": sys.exit(main())
