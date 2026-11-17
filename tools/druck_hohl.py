#!/usr/bin/env python3
"""druck_hohl.py <ein.stl> <aus.stl> [--wand_mm 1.0] [--schritt_mm 0.5] [--min_mm 3] [--schliess_mm 7] [--dach_grad 45] [--boden zu] [--bild PFAD.png]
MASSIVE Bereiche eines Druckmodells nachtraeglich aushoehlen (Druck-Nachlauf, der Generator und das abgenommene STL bleiben unberuehrt). Alle Masse in Druck-mm.

Anlass 17.11.2026: der Turm ist unter 8 m massiv (Generator hoehlt erst ab z_min = 8 m aus); das unterste Druckteil brauchte 8 h / 382 cm3. Der Sockel soll hohl sein,
Tordurchfahrt und Fenster bleiben.
Verfahren (generisch, aus waagerechten Schnitten des Modells - braucht kein Wissen ueber das Gebaeude):
  1. Scheiben der Hoehe --schritt_mm. Je Scheibe: Schnitt S; vorhandener Hohlraum V = Loecher des Schnitts (Fenster bis 2 x --schliess_mm ueberbrueckt, rund geoeffnet),
     soweit darueber irgendwo Material liegt (ein oben offener Hof ist kein Hohlraum) und ringsum ueberwiegend Wand steht (mindestens 40 % eines Bandes von 1,5 x Wand
     um den Hohlraum sind Material - eine offene Laterne auf Pfosten ist kein Hohlraum).
  2. Aushoehlbar R = Material, das waagerecht UND senkrecht mindestens --wand_mm von jeder Aussenflaeche entfernt ist (gemessen an S + V, die Wand zum vorhandenen Hohlraum zaehlt
     nicht als Aussenhaut -> der Boden zwischen neuem und altem Hohlraum faellt weg) und im Schnitt selbst mindestens --wand_mm tief im Material liegt
     (duenne Innenwaende, Laibungen, Innenschichten bleiben). Stellen schmaler als --min_mm entfallen.
  3. Druckbarkeit: von OBEN nach UNTEN - ein neuer Hohlraum darf je Scheibe nur um Scheibenhoehe x tan(--dach_grad) breiter sein als der Hohlraum darueber (neu oder vorhanden).
     Es entstehen also nur Hohlraeume UNTER vorhandenen Hohlraeumen, mit hoechstens 45 Grad geneigter Decke - keine flachen Decken, keine Bruecken im Inneren.
  4. Modell minus Hohlraum; Pruefung: wasserdicht, Koerperzahl, Volumen vorher/nachher. Unten offen (Standard) - mit --boden zu bleibt ein Boden von --wand_mm.
rc 3, wenn das Ergebnis nicht wasserdicht ist oder in mehr Koerper zerfaellt als das Modell.
Grenzen: nur fuer aufrecht gedruckte Modelle (z = Druckrichtung); ein ganz massives Modell ohne vorhandenen Hohlraum bleibt massiv (kein Ansatz fuer Schritt 3);
Wandstaerke gilt im Schnitt (waagerecht) und senkrecht, schraege Flaechen werden bis zu 30 % duenner; innere Geschossdecken (waagerechte Platten dicker als 2 x Wand) werden mit ausgehoehlt.
"""
import sys, os, argparse, numpy as np, trimesh
from manifold3d import Manifold as M, Mesh, CrossSection as CS, FillRule, JoinType, OpType
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "tools"))
RUND = JoinType.Round


def _fl(q):
    return 0.5 * float(np.sum(q[:, 0] * np.roll(q[:, 1], -1) - np.roll(q[:, 0], -1) * q[:, 1]))


def hohlraum(modell, wand, schritt=0.5, mind=3.0, schliess=7.0, dach_grad=45.0, boden_zu=False, melde=None):
    """-> (Hohlraumkoerper, Liste (z, Flaeche neu) je Scheibe). modell: Manifold in Druck-mm, z nach oben."""
    bb = modell.bounding_box(); zs = np.arange(bb[2], bb[5], schritt); n = len(zs); S = []; V = []
    for z in zs: S.append(modell.slice(float(z + schritt / 2)).simplify(0.02))
    decke = CS(); A = [None] * n                                                # von oben: was liegt ueber der Scheibe? (oben offener Hof = kein Hohlraum)
    for i in range(n - 1, -1, -1):
        v = CS()
        if not S[i].is_empty() and not decke.is_empty():
            lo = [q[::-1] for q in S[i].offset(schliess, JoinType.Miter).to_polygons() if _fl(q) < -0.01]      # Vorzeichen nur am verdickten Schnitt lesen (nach dem Zurueckversetzen kneift Clipper Ringe zusammen)
            if lo:
                gut = []
                for c in CS(lo, FillRule.Positive).offset(schliess, RUND, 2.0, 24).decompose():      # umschlossen nur, wenn ringsum ueberwiegend WAND steht: eine Laterne auf vier Pfosten (Turmspitze) schloss sich beim Ueberbruecken auch zum "Hohlraum" - Knaufboden und Helmdeckel bekamen Loecher
                    band = c.offset(1.5 * wand, RUND, 2.0, 12) - c
                    if (band ^ S[i]).area() >= 0.4 * band.area(): gut.append(c)
                if gut: v = (CS.batch_boolean(gut, OpType.Add) - S[i]) ^ decke
        V.insert(0, v); A[i] = S[i] + v; decke = (decke + S[i]).simplify(0.05)
    E = [a.offset(-wand, RUND, 2.0, 12) if not a.is_empty() else CS() for a in A]                      # waagerecht >= Wand von der Aussenhaut
    k = int(np.ceil(wand / schritt)); R = [CS()] * n
    for i in range(n):
        if E[i].is_empty() or i + k >= n: continue                             # oben: Decke von Wandstaerke
        r = E[i]
        for j in range(i - k, i + k + 1):
            if j == i or (j < 0 and not boden_zu): continue                     # unten offen: unter dem Modell gilt die unterste Scheibe
            if j < 0 or E[j].is_empty(): r = CS(); break
            r = r ^ E[j]
        if r.is_empty(): continue
        r = r ^ S[i].offset(-wand, RUND, 2.0, 12)                               # nur MASSIVES Material (duenne Innenwaende bleiben)
        if not r.is_empty(): r = r.offset(-mind / 2, RUND, 2.0, 8).offset(mind / 2, RUND, 2.0, 8)
        R[i] = r
    weit = schritt * np.tan(np.radians(dach_grad)); I = [CS()] * n; teile = []; prot = []
    for i in range(n - 2, -1, -1):                                             # von oben nach unten: nur unter einem Hohlraum, hoechstens dach_grad geneigte Decke
        if R[i].is_empty(): continue
        oben = I[i + 1] + V[i + 1]
        if oben.is_empty(): continue
        c = (R[i] ^ oben.offset(weit, RUND, 2.0, 8)).simplify(0.02)
        if c.is_empty(): continue
        I[i] = c; teile.append(c.extrude(schritt * 1.25).translate((0, 0, float(zs[i]) - schritt * 0.25))); prot.append((float(zs[i]), c.area()))      # Scheiben ueberlappen um ein Viertel nach unten (keine Mikrometer-Stufen; ein Boden wird bis 0,25 x Schritt duenner)
        if melde and len(teile) % 100 == 0: melde(f"  {len(teile)} Scheiben mit neuem Hohlraum ...")
    return (M.batch_boolean(teile, OpType.Add) if teile else M()), prot, (zs, S, V, I)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ein"); ap.add_argument("aus"); ap.add_argument("--wand_mm", type=float, default=1.0); ap.add_argument("--schritt_mm", type=float, default=0.5)
    ap.add_argument("--min_mm", type=float, default=3.0, help="schmalere Hohlraeume lohnen nicht"); ap.add_argument("--schliess_mm", type=float, default=7.0, help="Fenster bis zur doppelten Breite gelten beim Suchen der vorhandenen Hohlraeume als geschlossen")
    ap.add_argument("--dach_grad", type=float, default=45.0); ap.add_argument("--boden", default="offen", choices=["offen", "zu"]); ap.add_argument("--bild", default="", help="Laengsschnitte + Querschnitte vorher/nachher als PNG"); a = ap.parse_args()
    m = trimesh.load(a.ein, process=True); modell = M(Mesh(vert_properties=np.asarray(m.vertices, np.float32), tri_verts=np.asarray(m.faces, np.uint32)))
    if modell.is_empty(): print(f"FEHLER: {a.ein} ist kein geschlossener Koerper ({modell.status()})"); return 2
    v0 = modell.volume(); n0 = len(modell.decompose()); print(f"Modell {os.path.basename(a.ein)}: {modell.num_tri()} Dreiecke, {v0 / 1000:.1f} cm3, {n0} Koerper")
    hohl, prot, (zs, S, V, I) = hohlraum(modell, a.wand_mm, a.schritt_mm, a.min_mm, a.schliess_mm, a.dach_grad, a.boden == "zu", print)
    if hohl.is_empty(): print("kein massiver Bereich unter einem vorhandenen Hohlraum gefunden - nichts geaendert"); return 0
    erg = modell - hohl; st = sorted(erg.decompose(), key=lambda x: -x.volume())
    if len(st) > n0 and sum(x.volume() for x in st[n0:]) < 1e-4 * v0: erg = M.batch_boolean(st[:n0], OpType.Add) if n0 > 1 else st[0]      # Splitter
    v1 = erg.volume(); n1 = len(erg.decompose()); from bauteile import stl_schreiben; stl_schreiben(erg, a.aus, b"rcpark hohl")
    w = trimesh.load(a.aus, process=True); dicht = bool(w.is_watertight)
    print(f"neuer Hohlraum: z {prot[-1][0]:.1f}..{prot[0][0] + a.schritt_mm:.1f} mm, {hohl.volume() / 1000:.1f} cm3; Wand {a.wand_mm} mm, Decke hoechstens {a.dach_grad:.0f} Grad, Boden {a.boden}")
    zz = sorted(p_[0] for p_ in prot); ber = []; 
    for z in zz:
        if ber and z - ber[-1][1] < 1.5 * a.schritt_mm: ber[-1][1] = z
        else: ber.append([z, z])
    print("  Hoehenbereiche mit neuem Hohlraum (mm): " + "; ".join(f"{b0:.1f}..{b1 + a.schritt_mm:.1f} (bis {max(p_[1] for p_ in prot if b0 <= p_[0] <= b1) / 100:.1f} cm2)" for b0, b1 in ber))
    print(f"Volumen vorher {v0 / 1000:.1f} cm3 -> nachher {v1 / 1000:.1f} cm3 ({(v0 - v1) / v0 * 100:.0f} % weniger); {n1} Koerper (vorher {n0}); wasserdicht: {'ja' if dicht else 'NEIN'}; {len(w.faces)} Dreiecke -> {a.aus}")
    if a.bild:
        import cv2
        bb = modell.bounding_box(); px = 0.25; rand = 4.0; bl = []
        def schnitt(k, achse, wert):                                           # Laengsschnitt: Koerper drehen, dass die Schnittebene waagerecht liegt
            T = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0.0]]) if achse == 0 else (np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0.0]]) if achse == 1 else np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0.0]]))
            return k.transform(T).slice(float(wert)).to_polygons()
        def bild(achse, wert, titel):
            a0, a1 = [(1, 2), (0, 2), (0, 1)][achse]; W = int((bb[3 + a0] - bb[a0] + 2 * rand) / px); H = int((bb[3 + a1] - bb[a1] + 2 * rand) / px); im = np.full((H, 2 * W, 3), 255, np.uint8)
            for nr, k in enumerate((modell, erg)):
                po = schnitt(k, achse, wert); cc = [np.stack([(q[:, 0] - bb[a0] + rand) / px + nr * W, H - (q[:, 1] - bb[a1] + rand) / px], 1).astype(np.int32) for q in po]; mk = np.zeros((H, 2 * W), np.uint8)
                for c, q in sorted(zip(cc, po), key=lambda t_: -abs(_fl(t_[1]))): cv2.fillPoly(mk, [c], 1 if _fl(q) > 0 else 0)
                im[mk > 0] = (200, 160, 60)
            cv2.putText(im, titel + "   links vorher, rechts nachher", (8, 22), 0, 0.6, (0, 0, 0), 2); return im
        zi = [p[0] for p in prot]; zm = float(np.median(zi)); xm = float(0.5 * (bb[0] + bb[3])); ym = float(0.5 * (bb[1] + bb[4]))
        bl = [bild(0, xm, f"Laengsschnitt x = {xm:.0f} mm"), bild(1, ym, f"Laengsschnitt y = {ym:.0f} mm"), bild(2, zm, f"Querschnitt z = {zm:.0f} mm"), bild(2, max(zi) - 1.0, f"Querschnitt z = {max(zi) - 1.0:.0f} mm")]
        Wm = max(b.shape[1] for b in bl); bl = [cv2.copyMakeBorder(b, 0, 6, 0, Wm - b.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255)) for b in bl]; cv2.imwrite(a.bild, np.vstack(bl)); print(f"Bild (ansehen): {a.bild}")
    return 0 if (dicht and n1 <= n0) else 3


if __name__ == "__main__":
    sys.exit(main())
