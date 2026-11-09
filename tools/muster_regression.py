#!/usr/bin/env python3
"""Regression des Kanten-Tors gegen Handmessungen M-6120-001..005 (+006 Pfosten) auf der Laubenrueckwand (Bogen 3).
  muster_regression.py bauen OUT.json     grobe Rechteck-Hypothese (Ebene 0,33471889/0,94231803/0=6,54 aus Gitter/Messprotokoll, Lage ~0,2-0,3 m daneben) im Format von koerper_kantenliste.py export (ohne Parameterpfad)
  muster_regression.py vergleichen KT.json HYPO.json  Tabelle Handwert / Automatik / Differenz / Status (Messprotokolle als Handwert; Schwelle 0,06 m = Messunsicherheit der Handmessung)
Die groben Startwerte sind ANNAHME: gerundete Augenmasswerte (0,25-m-Raster), NICHT die Handwerte."""
import sys, json, os, numpy as np
MP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "modelle", "kaufhaus_grob3", "messprotokoll")
U = np.array([0.94231803, -0.33471889]); N = np.array([0.33471889, 0.94231803]); EBENE = 6.54      # Ebene der Handmessung (+-0,3 m, NICHT gemessen); die Regression sucht die echte Rueckwandebene in der Wolke (ebene_suchen) und rechnet die Handpixel dorthin
def P3(al, z, off=EBENE): return [float(al * U[0] + off * N[0]), float(al * U[1] + off * N[1]), float(z)]
def mp(i): return json.load(open(os.path.join(MP, "M-6120-%03d.json" % i)))
def ebene_suchen(wolke="/media/oem/scan/rc-park_daten/kaufhaus_alle/kanten3d_k80.npz", al=(5.0, 11.0), z=(2.0, 6.0)):
    """Rueckwandebene = schaerfstes Histogramm-Maximum (1 cm) der Wolkenpunkte im Bogenbereich, Fenster 6..8 m Tiefe (Gitterebene 6,54 +- 1)."""
    P = np.load(wolke)["P"][:, :3]; a = U @ P[:, :2].T; m = (P[:, 2] > z[0]) & (P[:, 2] < z[1]) & (a > al[0]) & (a < al[1]); o = N @ P[m][:, :2].T; o = o[(o > 6.0) & (o < 8.0)]
    h, e = np.histogram(o, bins=np.arange(6.0, 8.0, 0.02)); h = np.convolve(h, np.ones(3) / 3, "same"); j = int(np.argmax(h)); sel = o[(o > e[j] - 0.1) & (o < e[j] + 0.12)]; return float(np.median(sel))
def pixel_zu_ebene(F, f, px, off, start=(8.0, 5.0)):
    """Pixel (u,v) -> (along, z) auf der Ebene n.P = off (Gauss-Newton mit Vorwaertsprojektion der Kamera)."""
    x = np.array(start, float)
    for _ in range(30):
        def pr(x_): u, v, _z = F.proj(f, np.array([P3(x_[0], x_[1], off)])); return np.array([float(u[0]), float(v[0])])
        r = pr(x) - np.array(px, float); J = np.column_stack([(pr(x + [1e-3, 0]) - pr(x)) / 1e-3, (pr(x + [0, 1e-3]) - pr(x)) / 1e-3]); x = x - np.linalg.solve(J, r)
        if np.abs(r).max() < 0.05: break
    return float(x[0]), float(x[1])
def hand(off, F):
    """Handwerte = Handpixel der Messprotokolle M-6120-001..005 (mess_px), auf die echte Ebene `off` gerechnet. Auf der Protokollebene 6,54 steht der Wert im Protokoll (z1/z2); die Differenz zeigt den Ebenenfehler."""
    f = [x for x in F.KAM if "6120" in x][0]; q = lambda i: mp(i)["mess_px"]; h = {}
    a1, z1 = pixel_zu_ebene(F, f, q(1)[:2], off); a2, z2 = pixel_zu_ebene(F, f, q(1)[2:], off, (6.0, 5.0)); unc = mp(1)["unsicherheit_m"]
    h["fenster_oben"] = ("z", 0.5 * (z1 + z2), unc); h["fenster_links"] = ("along", min(a1, a2), unc); h["fenster_rechts"] = ("along", max(a1, a2), unc)
    _, z1 = pixel_zu_ebene(F, f, q(2)[:2], off); _, z2 = pixel_zu_ebene(F, f, q(2)[2:], off, (6.0, 4.0)); h["fenster_unten"] = ("z", 0.5 * (z1 + z2), mp(2)["unsicherheit_m"])
    _, z1 = pixel_zu_ebene(F, f, q(3)[:2], off); h["fenster_kaempfer"] = ("z", z1, mp(3)["unsicherheit_m"])
    a1, z1 = pixel_zu_ebene(F, f, q(4)[:2], off, (5.0, 2.0)); a2, z2 = pixel_zu_ebene(F, f, q(4)[2:], off, (3.5, 2.0)); h["tuer_unten"] = ("z", 0.5 * (z1 + z2), mp(4)["unsicherheit_m"]); h["tuer_links"] = ("along", min(a1, a2), mp(4)["unsicherheit_m"]); h["tuer_rechts"] = ("along", max(a1, a2), mp(4)["unsicherheit_m"])
    _, z1 = pixel_zu_ebene(F, f, q(5)[:2], off, (5.0, 4.0)); h["tuer_kaempfer"] = ("z", z1, mp(5)["unsicherheit_m"]); return h
# grobe Hypothese (ANNAHME: Augenmass, 0,25-m-Raster)
ROH = dict(fenster_oben=("h", 6.75, 6.5, 8.0), fenster_unten=("h", 3.0, 6.5, 8.0), fenster_kaempfer=("h", 5.25, 6.5, 8.0), tuer_unten=("h", 1.5, 3.75, 4.75), tuer_kaempfer=("h", 3.75, 3.75, 4.75),
           fenster_links=("v", 6.5, 3.25, 6.5), fenster_rechts=("v", 8.0, 3.25, 6.5), tuer_links=("v", 3.75, 1.75, 3.75), tuer_rechts=("v", 4.75, 1.75, 3.75))
def bauen(out, off):
    seg = []
    for i, (nm, (t, w, a, b)) in enumerate(ROH.items()):
        p0, p1 = (P3(a, w, off), P3(b, w, off)) if t == "h" else (P3(w, a, off), P3(w, b, off))
        seg.append(dict(id=i, p0=p0, p1=p1, gruppe_id="m6120." + nm, instanz=0, spiegel_partner=None))
    json.dump(dict(rahmen=dict(n=[float(N[0]), float(N[1]), 0.0]), segmente=seg, gruppen={}, ebene=off), open(out, "w"), indent=1); print("geschrieben", out, len(seg), "Kanten, Ebene %.3f" % off)
def vergleichen(kt, hypo):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.argv = sys.argv[:1]
    from kanten_tor import Fotos
    off = json.load(open(hypo))["ebene"]; D = "/media/oem/scan/rc-park_daten/kaufhaus_alle"; F = Fotos(D + "/sfm/kam_lot2.json", D + "/stabil", D + "/bilder"); R = json.load(open(kt)); K = {k["id"]: k for k in R["kanten"]}; C = {c["id"]: c for c in R["korrigiert"]}; H = hand(off, F); zeilen = []; ok = 0
    for i, (nm, (t, w, a, b)) in enumerate(ROH.items()):
        ach, hw, unc = H[nm]; c = C.get(str(i)) or C.get(i); r = K.get(str(i)) or K.get(i); d = r["dofs"]["versatz_ebene"]; stat = d["status"]
        auto = (0.5 * (c["A"][2] + c["B"][2]) if ach == "z" else float(U @ np.array(c["A"][:2]))) if c else float("nan")
        diff = auto - hw; erg = "GRUEN" if abs(diff) <= 0.06 else ("KORRIGIERT-NICHT-ERREICHT" if stat == "KORRIGIERT" else stat)
        if abs(diff) <= 0.06: ok += 1
        zeilen.append((nm, ach, w, hw, auto, diff, stat, erg, d.get("grund", "")[:160]))
    print("%-18s %-6s %8s %8s %8s %7s  %-11s %s" % ("Kante", "Achse", "Start", "Hand", "Auto", "Diff", "Tor-Status", "Ergebnis"))
    for z in zeilen: print("%-18s %-6s %8.3f %8.3f %8.3f %+7.3f  %-11s %s" % z[:8])
    for z in zeilen: print(" ", z[0], "-", z[8])
    print("Treffer (|Diff| <= 0,06 m): %d von %d" % (ok, len(zeilen)))
if __name__ == "__main__":
    if sys.argv[1] == "bauen": bauen(sys.argv[2], ebene_suchen())
    elif sys.argv[1] == "vergleichen": vergleichen(sys.argv[2], sys.argv[3])
