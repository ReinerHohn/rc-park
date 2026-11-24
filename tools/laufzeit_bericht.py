#!/usr/bin/env python3
"""laufzeit_bericht.py <kettenlog> [--vorlauf <kettenlog>] [--aus <json>] [--ab-zeile N]

LAUFZEIT JE STUFE + DOPPELARBEIT (Erkenntnis 24.11.2026, modelle/ERKENNTNISSE.md): dichte Wolke 2x fusioniert (470 + 450 s), Modell 6x voll
gebaut (38 min), Schnelltest 2 -> 13 min - alles blieb unbemerkt, bis der Nutzer fragte "warum dauert das so lange". Pruefung am ersten Tag:
Zeit je Stufe aus dem Kettenlog summieren, gegen den Vorlauf vergleichen und wiederholte teure Arbeit benennen.

Liest Zeilen "[hh:mm:ss] <stufe>: <befehl>" + "    rc N (S s) ..." (gesamtkette.lauf). Stufen werden zu FAMILIEN zusammengefasst:
Suffixe je Wand/Foto/Teil (_f00, _w03, _eigen__..., _teil1) fallen weg; 'bauen_mit_x' -> 'bauen'. Doppelarbeit:
  - FUSION: jede "TEILFUSION"-/"Fusion:"-Meldung mit Laufzeit im Log zaehlt; >= 2 echte Fusionen in einem Lauf = Doppelarbeit.
  - FAMILIE: eine Familie mit >= 2 Laeufen, die je >= TEUER_S dauern (z. B. 6 volle Bauten) = Hinweis "Wiederholung".
Vergleich: Familie >= WACHS_FAKTOR x Vorlauf und >= WACHS_MIN_S mehr = "gewachsen"; neue teure Familie = "neu".
rc 0 = Bericht geschrieben (auch mit Hinweisen: Bericht, kein Tor), rc 2 = Log nicht lesbar.
"""
import argparse, json, os, re, sys
from collections import OrderedDict

TEUER_S = 120          # ANNAHME: unter 2 min je Lauf lohnt das Zusammenlegen nicht (Kette 1122x: 163 min Summe, Stufen < 2 min zusammen ~25 %)
WACHS_FAKTOR = 1.5     # ANNAHME: Laufzeitschwankung gleicher Stufe zwischen Laeufen bisher <= 1,3x (1122x vs. 1122z fototor_bezug 168 / 150 s)
WACHS_MIN_S = 120

KOPF = re.compile(r"^(?:\[\d\d:\d\d:\d\d\] ([^:\s][^:]*):|=== (\S+)\s+\[)")   # Job-Log "[hh:mm:ss] stufe:" oder gesamtkette.log "=== stufe  [datum]"
RC = re.compile(r"^\s+rc (-?\d+) \((\d+) s\)")
FUSION = re.compile(r"TEILFUSION [0-9]+ Punkte aus [0-9]+ Teilen \((\d+) s\)")
SUFFIX = re.compile(r"_(f\d\d|w\d\d|teil\d+|l0neu|eigen__.*|netz_.*|commons.*|online.*|video.*|dl_.*|IMG.*)$")


def familie(stufe):
    s = SUFFIX.sub("", stufe)
    if s.startswith("bauen"): return "bauen"
    return s


ZEIT = re.compile(r"^=== (\S+)\s+\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\]")


def lesen(pfad, ab_zeile=0, bis_zeile=None):
    """-> (laeufe [(stufe, rc, sekunden)], fusionen [sekunden]) aus einem Kettenlog. gesamtkette.log ('=== stufe  [datum]') hat nicht fuer jede
    Stufe eine rc-Zeile -> Dauer = Abstand zur naechsten Kopfzeile (Wartezeiten zaehlen mit, das ist gewollt: Laufzeit, nicht Rechenzeit)."""
    import datetime as _dt
    kz = []
    with open(pfad, errors="ignore") as f:
        for i, z in enumerate(f):
            if i < ab_zeile: continue
            if bis_zeile is not None and i >= bis_zeile: break
            m = ZEIT.match(z)
            if m: kz.append((m.group(1), _dt.datetime.strptime(m.group(2), "%Y-%m-%d %H:%M:%S")))
    if kz:
        fus = lesen_fusionen(pfad, ab_zeile, bis_zeile)
        return [(n, 0, int((kz[k + 1][1] - t0).total_seconds())) for k, (n, t0) in enumerate(kz[:-1])], fus
    laeufe, fus, st = [], [], None
    with open(pfad, errors="ignore") as f:
        for i, z in enumerate(f):
            if i < ab_zeile: continue
            if bis_zeile is not None and i >= bis_zeile: break
            m = KOPF.match(z)
            if m: st = (m.group(1) or m.group(2)).strip(); continue
            m = RC.match(z)
            if m and st:
                laeufe.append((st, int(m.group(1)), int(m.group(2)))); st = None
            for m in FUSION.finditer(z): fus.append(int(m.group(1)))
    return laeufe, fus


def lesen_fusionen(pfad, ab_zeile=0, bis_zeile=None):
    fu = []
    with open(pfad, errors="ignore") as f:
        for i, z in enumerate(f):
            if i < ab_zeile: continue
            if bis_zeile is not None and i >= bis_zeile: break
            fu += [int(m.group(1)) for m in FUSION.finditer(z)]
    return fu


def summen(laeufe):
    d = OrderedDict()
    for st, rc, s in laeufe:
        e = d.setdefault(familie(st), dict(sekunden=0, laeufe=0, teuer=0))
        e["sekunden"] += s; e["laeufe"] += 1; e["teuer"] += s >= TEUER_S
    return d


def vorlauf_abschnitt(pfad, ab_zeile):
    """gesamtkette.log waechst ueber alle Laeufe: Vorlauf = von der letzten frueheren Kopfzeile mit derselben ERSTEN Stufe wie dieser Lauf bis ab_zeile."""
    kopf = []
    with open(pfad, errors="ignore") as f:
        for i, z in enumerate(f):
            m = KOPF.match(z)
            if m: kopf.append((i, (m.group(1) or m.group(2)).strip()))
    erste = next((n for i, n in kopf if i >= ab_zeile), None)
    vor = [i for i, n in kopf if i < ab_zeile and n == erste]
    return (vor[-1], ab_zeile) if (erste and vor) else None


def unterlog_fusionen(pfad, job):
    """Fusionen im Unterlog (pipe/pipeline.log, waechst ueber viele Laeufe) erst ab der ersten Zeile, die den Jobnamen nennt."""
    fu, dabei = [], False
    with open(pfad, errors="ignore") as f:
        for z in f:
            if not dabei and job in z: dabei = True
            if dabei: fu += [int(m.group(1)) for m in FUSION.finditer(z)]
    return fu


def bericht(log, vorlauf=None, ab_zeile=0, unterlog=None, job=None):
    la, fu = lesen(log, ab_zeile); S = summen(la); ges = sum(e["sekunden"] for e in S.values())
    if unterlog and job and os.path.exists(unterlog): fu = unterlog_fusionen(unterlog, job) + fu
    hinweise = []
    fu = list(dict.fromkeys(fu))                                             # dieselbe Meldung in Kettenlog und Unterlog zaehlt einmal (gleiche Sekundenzahl)
    if len(fu) >= 2: hinweise.append(f"DOPPELARBEIT Fusion: {len(fu)} Fusionen in einem Lauf ({' + '.join(str(x) for x in fu)} s) - Ausschlusslisten vor der ersten Fusion festlegen")
    for k, e in S.items():
        if e["teuer"] >= 2: hinweise.append(f"WIEDERHOLUNG {k}: {e['teuer']} teure Laeufe (je >= {TEUER_S} s), zusammen {e['sekunden'] / 60:.1f} min - Zwischenstaende wiederverwenden?")
    vgl = {}
    va = vorlauf_abschnitt(log, ab_zeile) if (not vorlauf and ab_zeile) else None
    if va: vorlauf = f"{log} Zeilen {va[0]}-{va[1]}"
    if va or (vorlauf and os.path.exists(vorlauf)):
        V = summen(lesen(log, va[0], va[1])[0] if va else lesen(vorlauf)[0])
        for k, e in S.items():
            v = V.get(k, {}).get("sekunden")
            if v is None:
                if e["sekunden"] >= TEUER_S: hinweise.append(f"NEU {k}: {e['sekunden'] / 60:.1f} min (im Vorlauf nicht)")
                continue
            vgl[k] = dict(vorher_s=v, jetzt_s=e["sekunden"])
            if e["sekunden"] >= WACHS_FAKTOR * v and e["sekunden"] - v >= WACHS_MIN_S:
                hinweise.append(f"GEWACHSEN {k}: {v / 60:.1f} -> {e['sekunden'] / 60:.1f} min")
    top = sorted(S.items(), key=lambda kv: -kv[1]["sekunden"])[:12]
    return dict(werkzeug="laufzeit_bericht.py", log=log, vorlauf=vorlauf, summe_min=round(ges / 60, 1), fusionen_s=fu,
                familien=[dict(familie=k, minuten=round(e["sekunden"] / 60, 1), anteil=round(e["sekunden"] / max(ges, 1), 3), laeufe=e["laeufe"]) for k, e in top],
                vergleich=vgl, hinweise=hinweise)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("log"); ap.add_argument("--vorlauf", default=""); ap.add_argument("--aus", default="")
    ap.add_argument("--ab-zeile", type=int, default=0)
    ap.add_argument("--unterlog", default="", help="pipe/pipeline.log (Fusionen der SfM-Stufe)"); ap.add_argument("--job", default="", help="Jobname (RCPARK_JOB) zum Abschnitt im Unterlog")
    a = ap.parse_args(argv)
    if not os.path.exists(a.log): print(f"Log fehlt: {a.log}"); return 2
    r = bericht(a.log, a.vorlauf or None, a.ab_zeile, a.unterlog or None, a.job or None)
    print(f"LAUFZEIT: {r['summe_min']} min Rechenzeit; " + " | ".join(f"{f['familie']} {f['minuten']} min ({100 * f['anteil']:.0f} %)" for f in r["familien"][:6]))
    for h in r["hinweise"]: print("  " + h)
    if a.aus:
        os.makedirs(os.path.dirname(os.path.abspath(a.aus)), exist_ok=True); json.dump(r, open(a.aus, "w"), indent=1, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
