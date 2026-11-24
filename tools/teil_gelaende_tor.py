#!/usr/bin/env python3
"""teil_gelaende_tor.py <dicht_a.ply> <dicht_b.ply> --matrix <json mit B_nach_A> --aus <ergebnis.json> [--modell-a <A-Modell>] [--gps <vereinen.json des GPS-Wegs>] [--bilder <Fotos>] [--teil N] [--weg W]

TOR 'TEIL UNTER GELAENDE' FUER JEDEN BINDUNGSWEG (24.11.2026, schwabentor-1122z: der Ost-Teil steckte 6,4 m im Boden, KEIN Tor fand es - der Nutzer sah es im 3D-Viewer).
Das Tor gab es nur in tools/seiten_waende_binden.py (Weg 'gps+waende'). Die anderen Wege, ein Seitenteil einzubinden (Klappung seiten_vereinen, Eckmodell seiten_eck_koppeln,
reines Foto-GPS seiten_gps_vereinen, Querspur seiten_querspur_binden, LoD2 je Teil seiten_lod2_je_teil) pruefen die Hoehe von B gegen den Boden von A nicht. Deshalb hier EINE
Funktion an der Stelle, wo das gebundene Teil in das vereinte Modell und die vereinte dichte Wolke geht (tools/sfm_seiten_modelle.py dicht_vereinen, vor modelle_zusammen),
egal welcher Weg die Matrix B_nach_A geliefert hat.
Pruefung (dieselben Funktionen und Grenzen wie seiten_waende_binden: unter_gelaende, boden_versatz, UNTER_M 1 m, UNTER_ANTEIL 5 %): beide dichten Wolken ins lokale metrische
System von A (z = Lot: Bild-x-Lot der A-Kameras, an den Waenden der A-Wolke nachgeschaerft; Meter je Einheit aus dem GPS-Rahmen von A), B mit B_nach_A dazu; Anteil der
B-Punkte in Strassenzellen von A, die > 1 m unter dem Boden von A liegen. Zum Vergleich derselbe Anteil von A selbst und der Bodenversatz A - B (Hinweis 'B x m zu tief').
rc 0 = bestanden, 3 = B unter Gelaende (ABGELEHNT), 2 = nicht pruefbar (kein Massstab, zu wenig gemeinsame Strassenzellen, Wolke fehlt) - immer mit Logzeile je Teil.
Massstab: GPS-Rahmen von A aus dem GPS-Weg (vereinen.json rahmen_a.massstab); fehlt der (Klappungs-/Eck-Weg, 24.11. Nachtrag), derselbe Rahmen aus Teil A ALLEIN
(seiten_gps_vereinen.rahmen auf den Kameras von A + EXIF-GPS der Fotos, --modell-a + --bilder) - nur wenn er als Lagebeleg taugt (guete leer, Bootstrap-Massstabsfehler
<= MAX_MASS_SD 15 % wie die Annahme-Regel des GPS-Wegs; der ehrliche Fehler steht nur im Bericht); sonst 'nicht pruefbar' (gemeldet, nicht geraten). Der Massstab haengt nicht vom GPS-Ursprung ab, darum gleich dem rahmen_a des GPS-Wegs.
Test: tools/test_teil_gelaende_tor.py. Python: /media/oem/scan/venv-colmap/bin/python -I (pycolmap nur fuer das Kameralot von A; ohne Modell: Lot = z-Achse von A, an den Waenden geschaerft)."""
import os, sys, json, argparse
import numpy as np

T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
from seiten_waende_binden import unter_gelaende, boden_versatz, basis, ply_lesen, UNTER_M, UNTER_ANTEIL
from seiten_querspur_binden import anwenden
from seiten_vereinen import lot_aus_waenden

MAX_PUNKTE = 1500000     # wie seiten_waende_binden.ply_lesen (gleichmaessig ausgeduennt)


def massstab_aus_gps(vj):
    """vereinen.json des GPS-Wegs (seiten_gps_vereinen) -> Meter je Einheit des A-Modells oder None."""
    try: m = float(((vj or {}).get("rahmen_a") or {}).get("massstab") or 0)
    except (TypeError, ValueError): return None
    return m if np.isfinite(m) and m > 0 else None


def massstab_aus_a(namen, C, oben, G, boden=None):
    """Meter je Einheit aus dem GPS-Rahmen von Teil A ALLEIN (seiten_gps_vereinen.rahmen, gleiche Grenzen wie der GPS-Weg). namen/C/oben = Kameras von A, G = {Name: (ost, nord)}.
    -> (Massstab oder None, Begruendung)."""
    import seiten_gps_vereinen as SGV
    try: F = SGV.rahmen(namen, np.asarray(C, float), np.asarray(oben, float), G, boden)
    except Exception as ex: return None, f"GPS-Rahmen von A nicht berechenbar ({type(ex).__name__}: {ex})"
    g = SGV.guete(F)
    if g: return None, "GPS-Rahmen von A taugt nicht: " + "; ".join(g)
    sd = float(F.get("mass_sd_rel", 1.0))                                                # Bootstrap-Streuung wie die Annahme-Regel des GPS-Wegs (b_nach_a); ehrlich nur Bericht
    if not np.isfinite(sd) or sd > SGV.MAX_MASS_SD: return None, f"Massstab aus dem GPS von A nur auf +-{100 * sd:.0f} % belegt (Grenze {100 * SGV.MAX_MASS_SD:.0f} %)"
    m = float(F["massstab"])
    if not (np.isfinite(m) and m > 0): return None, "GPS-Rahmen von A: Massstab ungueltig"
    return m, f"GPS-Rahmen von Teil A allein ({F['inlier']} von {F['n_gps']} GPS-Kameras, Rest {F['rest_median_m']} m, Massstab +-{100 * sd:.1f} %, ehrlich +-{100 * float(F.get('mass_sd_ehrlich_rel', sd)):.1f} %)"


def a_kameras_gps(modell_a, bilder):
    """Kameras von A (seiten_gps_vereinen.kameras) + EXIF-GPS als ENU {Name: (ost, nord)} um den Median der A-Fotos. -> (namen, C, oben, G)."""
    import seiten_gps_vereinen as SGV
    namen, C, oben = SGV.kameras(modell_a); roh = SGV.gps_roh(bilder, namen)
    if not roh: return namen, C, oben, {}
    la0, lo0 = np.median([v[0] for v in roh.values()]), np.median([v[1] for v in roh.values()])
    return namen, C, oben, SGV.enu(roh, la0, lo0)


def pruefen(DA, DB, M, lot, m_je_einheit, teil="B", weg="?"):
    """DA = A-Wolke (A-System), DB = B-Wolke (B-System), M = 4x4 B -> A, lot = Lot in A (zeigt nach oben), m_je_einheit = Meter je A-Einheit.
    -> dict(ok (True/False/None), rc, anteil_b, anteil_a, zellen, boden_versatz_m, meldung)."""
    aus = dict(teil=teil, weg=weg, ok=None, rc=2, anteil_b=None, anteil_a=None, zellen=0, boden_versatz_m=None, grenze_anteil=UNTER_ANTEIL, unter_m=UNTER_M)
    if m_je_einheit is None or not np.isfinite(m_je_einheit) or m_je_einheit <= 0:
        aus["meldung"] = f"GELAENDE-TOR Teil {teil} (Weg {weg}): NICHT PRUEFBAR - kein Massstab (Meter je Einheit) fuer Teil A"; return aus
    if len(DA) < 100 or len(DB) < 100:
        aus["meldung"] = f"GELAENDE-TOR Teil {teil} (Weg {weg}): NICHT PRUEFBAR - zu wenig Punkte (A {len(DA)}, B {len(DB)})"; return aus
    lot = np.asarray(lot, float); lot = lot / np.linalg.norm(lot)
    L = np.eye(4); L[:3, :3] = m_je_einheit * basis(lot)
    la = anwenden(L, DA); lb = anwenden(L @ np.asarray(M, float), DB)
    ug = unter_gelaende(la, lb); bo = boden_versatz(la, lb)
    aus.update(anteil_b=ug["anteil_b"], anteil_a=ug["anteil_a"], zellen=ug["zellen"], boden_versatz_m=bo.get("dz_m"), boden=bo)
    zt = f"; Boden von B {bo['dz_m']:+.2f} m gegen A ({bo['zellen']} Zellen) -> B {abs(bo['dz_m']):.1f} m zu {'tief' if bo['dz_m'] > 0 else 'hoch'}" if bo.get("messbar") and bo.get("dz_m") is not None else ""
    if ug["ok"] is None:
        aus["meldung"] = f"GELAENDE-TOR Teil {teil} (Weg {weg}): NICHT PRUEFBAR - zu wenig B-Punkte in Strassenzellen von A ({ug['zellen']} Zellen){zt}"; return aus
    aus.update(ok=bool(ug["ok"]), rc=0 if ug["ok"] else 3)
    txt = (f"{100 * ug['anteil_b']:.1f} % der B-Punkte in {ug['zellen']} Strassenzellen > {UNTER_M:g} m unter dem Boden von A (Grenze {100 * UNTER_ANTEIL:.0f} %, "
           f"A selbst {100 * (ug['anteil_a'] or 0):.1f} %){zt}")
    aus["meldung"] = f"GELAENDE-TOR Teil {teil} (Weg {weg}): " + ("bestanden - " if ug["ok"] else "ABGELEHNT, Teil unter Gelaende - ") + txt
    return aus


def lot_von_a(DA, modell_a=None):
    """Lot von A: Bild-x-Lot der A-Kameras (seiten_gps_vereinen.lot_aus_bild_achsen, wie seiten_waende_binden), an den Waenden der A-Wolke nachgeschaerft."""
    lot0, quelle = np.array([0, 0, 1.0]), "z-Achse von A (kein Modell)"
    if modell_a:
        try:
            import pycolmap
            from seiten_gps_vereinen import lot_aus_bild_achsen
            r = pycolmap.Reconstruction(modell_a); lot0 = np.asarray(lot_aus_bild_achsen([im.cam_from_world().rotation.matrix() for im in r.images.values() if im.has_pose]), float); quelle = "Kameras von A"
        except Exception as ex: quelle = f"z-Achse von A (Modell nicht lesbar: {type(ex).__name__})"
    u, n = lot_aus_waenden(DA, lot0)
    return np.asarray(u, float), quelle + (f", an {n} Wandnormalen geschaerft" if n else "")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0]); ap.add_argument("dicht_a"); ap.add_argument("dicht_b"); ap.add_argument("--matrix", required=True); ap.add_argument("--aus", required=True)
    ap.add_argument("--modell-a"); ap.add_argument("--gps"); ap.add_argument("--bilder"); ap.add_argument("--teil", default="B"); ap.add_argument("--weg", default="?"); a = ap.parse_args(argv)
    os.makedirs(os.path.dirname(os.path.abspath(a.aus)), exist_ok=True)
    def ende(erg):
        print(erg["meldung"], flush=True); json.dump(erg, open(a.aus, "w"), indent=1, ensure_ascii=False); return erg["rc"]
    basis_erg = dict(teil=a.teil, weg=a.weg, ok=None, rc=2)
    if not (os.path.isfile(a.dicht_a) and os.path.isfile(a.dicht_b)): return ende(dict(basis_erg, meldung=f"GELAENDE-TOR Teil {a.teil} (Weg {a.weg}): NICHT PRUEFBAR - dichte Wolke fehlt"))
    try: M = np.asarray(json.load(open(a.matrix))["B_nach_A"], float); assert M.shape == (4, 4)
    except Exception as ex: return ende(dict(basis_erg, meldung=f"GELAENDE-TOR Teil {a.teil} (Weg {a.weg}): NICHT PRUEFBAR - Matrix B_nach_A nicht lesbar ({type(ex).__name__})"))
    try: m = massstab_aus_gps(json.load(open(a.gps))) if a.gps and os.path.isfile(a.gps) else None
    except Exception: m = None
    DA = ply_lesen(a.dicht_a, MAX_PUNKTE); DB = ply_lesen(a.dicht_b, MAX_PUNKTE); lot, lq = lot_von_a(DA, a.modell_a); mq = a.gps if m else None
    if m is None and a.modell_a and a.bilder and os.path.isdir(a.bilder):                 # kein GPS-Weg: Massstab aus dem GPS-Rahmen von A allein
        try: m, mq = massstab_aus_a(*a_kameras_gps(a.modell_a, a.bilder), boden=DA)
        except Exception as ex: m, mq = None, f"GPS von A nicht lesbar ({type(ex).__name__})"
        print(f"GELAENDE-TOR Teil {a.teil}: Massstab ohne GPS-Weg -> {mq}", flush=True)
        if m is None: mq = "keiner: " + str(mq)
    erg = pruefen(DA, DB, M, lot, m, a.teil, a.weg); erg.update(lot=[round(float(x), 5) for x in lot], lot_quelle=lq, m_je_einheit=m, massstab_quelle=mq)
    if m is None and mq: erg["meldung"] += f" ({mq})"
    return ende(erg)


if __name__ == "__main__": sys.exit(main())
