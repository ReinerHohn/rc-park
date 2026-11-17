#!/usr/bin/env python3
"""druck_luft.py <teil.stl> [--schicht_mm 0.08] [--winkel_grad 45] [--min_mm2 2] [--unterfuettern AUS.stl] - Luftinseln je Schicht finden (Druck-Vorpruefung, Masse in Druck-mm, z = Druckrichtung).

Anlass 17.11.2026: Uhr als Klipsteil auf dem Bambu wurde Spaghetti. Die Zeiger schwebten im Modell ueber dem Zifferblatt (78 mm2 bei z 2,2 mm, 30 mm2 bei z 2,9 mm ohne Halt);
der Drucker legte sie in die Luft, die Faeden rissen die Ziffern mit ab. Keine Pruefung hatte das gemeldet (druck_vorcheck misst Wanddicke, druck_teilung den Ueberhang
nur als Flaechenanteil der Aussenhaut).
Verfahren: waagerechte Schnitte im Schichtabstand; frei = Schnitt(z) minus Schnitt(z - Schicht) um Schicht x tan(winkel) verbreitert. Eine Flaeche, die mehr als --min_mm2
frei liegt UND an einer Stelle weiter als --bruecke_mm (5) vom tragenden Material entfernt ist (kuerzere Stuecke ueberbrueckt der Drucker), steht in der Liste mit Hoehe, Flaeche und Lage.
rc 3, wenn eine Luftinsel gefunden wurde; rc 0 sonst.
--unterfuettern AUS.stl: jede Luftinsel wird senkrecht bis auf das Material darunter (oder das Bett) verlaengert - fuer Reliefteile, die mit der Schauseite nach oben
liegen (Zeiger, Schilder, Wappen ueber einem Grund). NICHT fuer Teile mit Durchblicken (Boegen, Fenster): dort wuerde die Oeffnung zugegossen.
"""
import sys, os, argparse, numpy as np, trimesh
from manifold3d import Manifold as M, Mesh, CrossSection as CS, JoinType, OpType
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "tools"))


def luftinseln(modell, schicht=0.08, winkel=45.0, min_mm2=2.0, bruecke=5.0):
    bb = modell.bounding_box(); zs = np.arange(bb[2] + schicht / 2, bb[5], schicht); S = [modell.slice(float(z)) for z in zs]; weit = schicht * np.tan(np.radians(winkel)); out = []
    for i in range(1, len(zs)):
        if S[i].is_empty(): continue
        frei = S[i] - S[i - 1].offset(weit, JoinType.Round, 2.0, 12)
        traeger = S[i - 1].offset(weit + bruecke, JoinType.Round, 2.0, 12)
        for g in frei.decompose():
            if g.area() >= min_mm2 and (g - traeger).area() > 0.05:                   # nur, was weiter als 'bruecke' von tragendem Material liegt (Fensterstuerze/Rippenansaetze ueberbrueckt der Drucker)
                b_ = g.bounds(); out.append(dict(i=i, z=float(zs[i]), flaeche=float(g.area()), mitte=[(b_[0] + b_[2]) / 2, (b_[1] + b_[3]) / 2], cs=g))
    return out, zs, S


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("stl"); ap.add_argument("--schicht_mm", type=float, default=0.08); ap.add_argument("--winkel_grad", type=float, default=45.0)
    ap.add_argument("--min_mm2", type=float, default=2.0); ap.add_argument("--bruecke_mm", type=float, default=5.0, help="bis zu diesem Abstand vom Traeger gilt frei Gedrucktes als Bruecke/kurzer Ueberhang"); ap.add_argument("--unterfuettern", default=""); a = ap.parse_args()
    m = trimesh.load(a.stl, process=True); mo = M(Mesh(vert_properties=np.asarray(m.vertices, np.float32), tri_verts=np.asarray(m.faces, np.uint32)))
    if mo.is_empty(): print("FEHLER: kein geschlossener Koerper"); return 2
    li, zs, S = luftinseln(mo, a.schicht_mm, a.winkel_grad, a.min_mm2, a.bruecke_mm)
    for x in li[:30]: print(f"  LUFTINSEL z {x['z']:.2f} mm: {x['flaeche']:.1f} mm2 frei bei x {x['mitte'][0]:.1f} / y {x['mitte'][1]:.1f}")
    print(f"{os.path.basename(a.stl)}: {len(li)} Luftinsel(n) (Schicht {a.schicht_mm} mm, {a.winkel_grad:g} Grad, ab {a.min_mm2:g} mm2)" + (" - NICHT ohne Stuetzen druckbar" if li else " - frei haengt nichts"))
    if a.unterfuettern:
        if not li: import shutil; shutil.copy(a.stl, a.unterfuettern); print("nichts zu unterfuettern ->", a.unterfuettern); return 0
        bb = mo.bounding_box(); erg = mo; li2 = li; runde = 0
        while li2 and runde < 6:                                                  # 17.11.2026: eine Runde endete an der ersten TEILWEISEN Auflage - Rest hing weiter frei
            runde += 1; stuetz = []
            for x in li2:
                z_oben = x["z"]; z_unten = bb[2]
                for j in range(x["i"] - 1, -1, -1):                               # bis zur ersten Schicht darunter, die unter der Insel Material hat
                    if not (S[j] ^ x["cs"]).is_empty(): z_unten = float(zs[j]); break
                stuetz.append(x["cs"].offset(0.2, JoinType.Round, 2.0, 12).extrude(z_oben - z_unten + 0.02).translate((0, 0, z_unten - 0.01)))
            erg = erg + M.batch_boolean(stuetz, OpType.Add)
            li2, zs, S = luftinseln(erg, a.schicht_mm, a.winkel_grad, a.min_mm2, a.bruecke_mm)
        from bauteile import stl_schreiben; stl_schreiben(erg, a.unterfuettern, b"rcpark unterfuettert")
        print(f"unterfuettert: +{(erg.volume() - mo.volume()):.1f} mm3, danach {len(li2)} Luftinsel(n) -> {a.unterfuettern}"); return 3 if li2 else 0
    return 3 if li else 0


if __name__ == "__main__":
    sys.exit(main())
