#!/usr/bin/env python3
"""freiraum_oeffnungen.py - aus den Freiraum-Tiefenkarten (freiraum_fassaden.py) allgemeine Bauanweisungen machen, OHNE Bauteilregel:
  1. Jedes erkannte Fassadenelement (fassade_parsing elemente.json) bekommt die gemessene Freiraumtiefe in seinem Kasten (p75 der Zellen > --min-tiefe),
     Umriss bleibt der des Elements (Pfeiler zwischen Boegen bleiben stehen; schraege Strahlen verschmelzen sonst benachbarte Oeffnungen).
  2. Freiraumfelder, die KEIN Element ueberdeckt (zusammenhaengend, >= --min-flaeche m2), werden neue Elemente 'oeffnung' mit Umriss = Feld-Rechteck.
     Beispiel Kaufhaus: Seitendurchgang West unter dem Erker, den die Fenstererkennung nicht fand.
Ausgabe: elemente-Datei im Format von fassade_parsing (+ Felder tiefe_m, quelle_tiefe) - Eingang fuer den Generator (nach Laufende null5i).
  /media/oem/scan/venv-seg/bin/python -I tools/freiraum_oeffnungen.py <freiraum_fassaden.json> <elemente.json> <aus.json> [--min-tiefe 0.5] [--min-flaeche 1.5]
"""
import json, argparse, numpy as np
from scipy import ndimage


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("karten"); ap.add_argument("elemente"); ap.add_argument("aus"); ap.add_argument("--fassaden", help="fassaden.json (fassade_ortho): Felder, die bis an die Oberkante der Fassade reichen, sind Umriss-Widersprueche (Giebel/Dach), keine Oeffnungen")
    ap.add_argument("--min-breite", type=float, default=1.0, help="schmalere Felder = Strahlen schraeg hinter Pfeilern/Laibungen, keine Oeffnung")
    ap.add_argument("--min-tiefe", type=float, default=0.5); ap.add_argument("--min-flaeche", type=float, default=1.5); ap.add_argument("--min-zellen-anteil", type=float, default=0.3)
    ap.add_argument("--rand-element", type=float, default=0.5, help="Elementkasten um so viel (m) erweitert, bevor Restfelder gesucht werden")
    ap.add_argument("--min-kameras-feld", type=int, default=6, help="Feld gilt nur, wenn mind. so viele verschiedene Kameras in einer Zelle durchsehen (Westseite f01: 7 Fotos gesamt)")
    ap.add_argument("--boden-z", type=float, default=2.5, help="Feld beginnt unterhalb dieser Hoehe (m) -> oeffnung (Durchgang); sonst ruecksprung")
    ap.add_argument("--max-z0", type=float, default=1e9, help="nur Felder, die unterhalb dieser Hoehe beginnen (m); Vorgabe aus")
    a = ap.parse_args(argv); K = json.load(open(a.karten))["fassaden"]; E = json.load(open(a.elemente)); n_alt, n_neu = 0, 0; wid = []
    FA = {v["id"]: v for v in json.load(open(a.fassaden))["fassaden"]} if a.fassaden else {}
    def oben(fid, u):   # Oberkante der Fassade bei u aus polys_uz (hoechster Punkt der Teilflaechen, die u ueberdecken)
        zs = [max(z for _, z in P) for P in FA.get(fid, {}).get("polys_uz", []) if min(x for x, _ in P) <= u <= max(x for x, _ in P)]
        return max(zs) if zs else 1e9
    for fid, F in E["fassaden"].items():
        if fid not in K: continue
        k = K[fid]; M = np.array(k["raster"]); NK = np.array(k.get("kameras", np.full_like(M, 99))); z_ = k["zelle"]; u0, z0 = k["u"][0], k["z"][0]; offen = M > a.min_tiefe; belegt = np.zeros_like(offen)
        ui = lambda u: int(np.clip((u - u0) / z_, 0, M.shape[1])); zi = lambda z: int(np.clip((z - z0) / z_, 0, M.shape[0]))
        for e in F["elemente"]:
            sl = (slice(zi(e["z0"]), zi(e["z1"])), slice(ui(e["u0"]), ui(e["u1"]))); w = M[sl]; belegt[sl] = True
            if w.size and (w > a.min_tiefe).mean() >= a.min_zellen_anteil:
                e["tiefe_m"] = round(float(np.percentile(w[w > a.min_tiefe], 75)), 2); e["quelle_tiefe"] = f"freiraum: {int((w > a.min_tiefe).sum())} Zellen, Sichtstrahlen >= 3 Kameras"; n_alt += 1
        belegt = ndimage.binary_dilation(belegt, iterations=max(1, int(round(a.rand_element / z_))))   # schraege Strahlen neben Elementen (Pfeiler, Laibung) gehoeren zum Element
        lab, n = ndimage.label(offen & ~belegt)
        for i in range(1, n + 1):
            q = lab == i; fl = q.sum() * z_ ** 2
            if fl < a.min_flaeche: continue
            zz, uu = np.where(q)
            if (uu.max() - uu.min() + 1) * z_ < a.min_breite: continue
            nk = int(NK[q].max())
            if nk < a.min_kameras_feld: print(f"  {fid}: Feld u {u0 + uu.min() * z_:.2f}..{u0 + (uu.max() + 1) * z_:.2f} z {z0 + zz.min() * z_:.2f}..{z0 + (zz.max() + 1) * z_:.2f} nur {nk} Kameras -> unsicher, keine Oeffnung"); continue
            um = u0 + (uu.min() + uu.max() + 1) / 2 * z_
            if z0 + (zz.max() + 1) * z_ > oben(fid, um) - 1.0:
                wid.append(dict(fassade=fid, u=[round(u0 + uu.min() * z_, 2), round(u0 + (uu.max() + 1) * z_, 2)], z=[round(z0 + zz.min() * z_, 2), round(z0 + (zz.max() + 1) * z_, 2)], tiefe_p75=round(float(np.percentile(M[q], 75)), 2)))
                print(f"  {fid}: Freiraum reicht an die Oberkante (u {wid[-1]['u']}, z {wid[-1]['z']}) -> Umriss-WIDERSPRUCH Foto vs Modell, keine Oeffnung"); continue
            kl_ = "oeffnung" if z0 + zz.min() * z_ <= a.boden_z else "ruecksprung"   # vom Boden aus begehbar = Durchgang/Arkade; hoeher = Ruecksprung ODER falsche Wandlage (Widerspruch, nicht automatisch schneiden)
            e = dict(klasse=kl_, u0=round(u0 + uu.min() * z_, 2), u1=round(u0 + (uu.max() + 1) * z_, 2), z0=round(z0 + zz.min() * z_, 2), z1=round(z0 + (zz.max() + 1) * z_, 2),
                                         tiefe_m=round(float(np.percentile(M[q], 75)), 2), stimmen=3, kameras=nk, quelle=f"freiraum_oeffnungen: Freiraumfeld {fl:.1f} m2 ohne erkanntes Element, bis {nk} Kameras")
            if e["z0"] > a.max_z0: continue
            F["elemente"].append(e); n_neu += 1; print(f"  {fid}: neue {e['klasse']} u {e['u0']}..{e['u1']} z {e['z0']}..{e['z1']} Tiefe {e['tiefe_m']} m ({fl:.1f} m2)")
    E["quelle_freiraum"] = a.karten; E["umriss_widersprueche"] = wid; json.dump(E, open(a.aus, "w"), indent=1); print(f"{n_alt} Elemente mit gemessener Tiefe, {n_neu} neue Oeffnungen -> {a.aus}")


if __name__ == "__main__":
    main()
