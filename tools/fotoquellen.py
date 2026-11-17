#!/usr/bin/env python3
"""fotoquellen.py - ALLE Fotoordner eines Objekts finden (fuer die Gesamtkette: Fremdquellen -> bilder_vorpruefen -> fotos_sammeln).
  python3 -I tools/fotoquellen.py <fotos_dir> [--ziel <datenordner der Kette>] [--ausschluss muster ...]
GRUND (kaufhaus_gk 17.11.2026, Vergleich mit dem Handmodell kaufhaus_grob3): die Kette nahm als 'eigene Fotos' nur fotos_dir (daten/kaufhaus/fotos, 333 Bilder)
plus Commons/YouTube. Unter rc-park_daten lagen fuer dasselbe Gebaeude weitere ~107 iPhone-Fotos (kaufhaus_iphone/fotos_jpg), ~280 Handyfotos (kaufhaus/fotos_eingang/handy_*),
Nutzerfotos (kaufhaus_nutzerfotos_2026-11-08, kaufhaus_grob3/nutzerfotos_*), 364 iPhone-Videobilder und Mapillary - nie gesammelt.
Regel: Basis = Ordnername ueber fotos_dir unter rc-park_daten (z. B. 'kaufhaus'). Durchsucht werden rc-park_daten/<basis> und rc-park_daten/<basis>_* (Symlinks auf andere Platten folgen).
Fotoordner = Pfad (relativ zum Basisordner, einschliesslich dessen Namen) enthaelt ein Glied fotos*, fotos_eingang, *nutzerfotos*, mapillary*, video_frames, und KEIN abgeleitetes/privates Glied
(agent_scratch, overlay, vorschau, ortho, kanten, fassade, sfm, dicht, quarantaene, kontaktboegen, nicht_<basis>, handy_phone, ...) und mindestens 3 Bilder (.jpg/.jpeg/.png).
Ausgeschlossen: fotos_dir selbst und alles unter --ziel (Sammelordner der Kette). Ob ein Bild das Objekt zeigt, entscheidet danach bilder_vorpruefen.py (Inlier gegen die Referenz) - hier nur Ordnerwahl.
"""
import os, re, sys, argparse

FOTO = re.compile(r"(^|_)(fotos|fotos_eingang|nutzerfotos|mapillary|video_frames)(_|$)|^fotos|nutzerfotos|^mapillary|^gewaehlt$", re.I)
WEG = re.compile(r"agent_scratch|overlay|vorschau|ortho|kanten|fassade|^sfm$|dicht|quarantaene|kontaktboegen|handy_phone|^aus$|maske|render|_test|^test|limap|undistort|eignung", re.I)
BILD = (".jpg", ".jpeg", ".png")


def daten_wurzel(p):
    """Datenwurzel + Basisname. Symlinks STUFENWEISE aufloesen und den ERSTEN Pfad mit /rc-park_daten/ nehmen: daten/kaufhaus/fotos -> /media/oem/scan/rc-park_daten/kaufhaus/fotos
    -> (ausgelagert) /media/oem/Volume/rc-park_auslagern/... - realpath sprang sofort auf die Auslagerungsplatte, dort fehlen die Geschwisterordner."""
    q = os.path.abspath(p)
    for _ in range(12):
        if "/rc-park_daten/" in q: return q.split("/rc-park_daten/")[0] + "/rc-park_daten", q.split("/rc-park_daten/")[1].split("/")[0]
        teile = q.split(os.sep); neu = None
        for i in range(2, len(teile) + 1):
            c = os.sep.join(teile[:i])
            if os.path.islink(c): neu = os.path.normpath(os.path.join(os.path.dirname(c), os.readlink(c), *teile[i:])); break
        if neu is None: break
        q = neu
    return None, None


def finden(fotos_dir, ziel=None, ausschluss=(), max_tiefe=4, wurzel=None, basis=None):
    if wurzel is None: wurzel, basis = daten_wurzel(fotos_dir)
    if not wurzel or not basis or not os.path.isdir(wurzel): return []
    ohne = {os.path.realpath(fotos_dir)}; zr = os.path.realpath(ziel) if ziel else None
    weg_extra = [re.compile(re.escape(x), re.I) for x in ausschluss] + [re.compile(r"^nicht_" + re.escape(basis), re.I)]
    starts = sorted(d for d in os.listdir(wurzel) if (d == basis or d.startswith(basis + "_")) and os.path.isdir(os.path.join(wurzel, d)))
    gef = []; gesehen = set()
    for s in starts:
        for dp, dn, fn in os.walk(os.path.join(wurzel, s), followlinks=True):
            rel = os.path.relpath(dp, wurzel).split(os.sep); rp = os.path.realpath(dp)
            if len(rel) > max_tiefe or rp in gesehen or any(WEG.search(g) or any(w.search(g) for w in weg_extra) for g in rel) or (zr and (rp == zr or rp.startswith(zr + os.sep))):
                dn[:] = []; continue
            gesehen.add(rp)
            if rp in ohne or not any(FOTO.search(g) for g in rel): continue
            n = 0 if any(d.lower() == "gewaehlt" for d in dn) else sum(f.lower().endswith(BILD) for f in fn)      # Ordner mit Auswahl 'gewaehlt' (Videobilder): nur die Auswahl, nicht alle Rohbilder
            if n >= 3: gef.append((dp, n))
    return gef


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("fotos_dir"); ap.add_argument("--ziel"); ap.add_argument("--ausschluss", nargs="*", default=[])
    a = ap.parse_args(); g = finden(a.fotos_dir, a.ziel, a.ausschluss)
    for d, n in g: print(f"{n:5d}  {d}")
    print(f"{len(g)} Ordner, {sum(n for _, n in g)} Bilder (ohne {a.fotos_dir})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
