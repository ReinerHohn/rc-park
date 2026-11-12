#!/usr/bin/env python3
"""test_foto_luecken.py - Beweistest fuer tools/foto_luecken.py (synthetisch, GPU). Ausgabe BESTANDEN / DURCHGEFALLEN, Exit 0/1.

Fall A  Quader-Haus mit Erker, Kameras nur auf 3 Seiten:
        - Westseite (-x, vierte Seite) muss 'fehlt' sein (>= 90 % der Flaeche), Erker-Unterseite 'nicht gut' (Kameras sehen sie nur streifend),
        - Standpunkte: einer vor der Westseite (x < -15) mit Blick nach Osten (+-45 Grad), einer unter dem Erker (Blick nach oben >= 20 Grad),
        - Kameras dort ergaenzen -> Westseite und Erker-Unterseite nicht mehr 'fehlt'.
Fall B  OHNE STL: nur Quader-Huelle als LoD2-Ersatz + synthetische Fotowolke nur auf 3 Seiten: Westseite 'fehlt' und 'Wolke duenn' (>= 90 %), die drei anderen Seiten nicht duenn.
Fall C  Fotonetz nur auf 3 Seiten + Quader-LoD2: Netz allein hat auf der Westseite KEINE Flaeche (Falle), mit netz_mit_lod2 bleibt sie als 'fehlt' drin.
Fall D  Georeferenz: bekannte Starrkoerper-Transformation eines asymmetrischen Grundrisses wird auf < 0,05 m / 0,3 Grad wiedergefunden; UTM<->WGS84-Rundlauf < 1 mm.
"""
import sys, os, math, json, numpy as np, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import foto_luecken as FL
from shapely.geometry import Polygon, box as sbox

OUT = "/media/oem/scan/rc-park_daten/_test_foto_luecken"; os.makedirs(OUT, exist_ok=True)
FEHLER = []
def pruefe(name, ok, info=""):
    print(("  ok   " if ok else "  FEHL ") + name + (("  -> " + info) if info else ""), flush=True)
    if not ok: FEHLER.append(name)

def cam(pos, ziel, W=4032, H=3024, f=3100.0, name="c"):
    pos = np.asarray(pos, float); fw = np.asarray(ziel, float) - pos; fw /= np.linalg.norm(fw); x = np.cross(fw, [0, 0, 1.0]); x /= np.linalg.norm(x); y = np.cross(fw, x)
    R = np.vstack([x, y, fw]); t = -R @ pos
    return dict(name=name, R=R, t=t, C=pos, f=f, cx=W / 2, cy=H / 2, W=W, H=H, quelle="synthetisch")

def haus(erker=True):
    b = [trimesh.creation.box(extents=(20, 12, 10), transform=trimesh.transformations.translation_matrix((0, 0, 5)))]
    if erker: b.append(trimesh.creation.box(extents=(4, 2, 3), transform=trimesh.transformations.translation_matrix((0, 7, 7.5))))   # Erker z 6..9, y 6..8
    m = trimesh.util.concatenate(b); m.merge_vertices(); return m

def ring(zentrum, winkel_mitte, spreizung=20, n=12, r=26, h=1.6, ziel=(0, 0, 5)):
    out = []
    for a in np.linspace(winkel_mitte - spreizung, winkel_mitte + spreizung, n):
        p = np.array([zentrum[0] + r * math.cos(math.radians(a)), zentrum[1] + r * math.sin(math.radians(a)), h]); out.append(cam(p, ziel, name=f"s{len(out)}_{a:.0f}"))
    return out

def seiten_kameras(seiten):
    c = []
    for w in seiten: c += ring((0, 0), w, ziel=(0, 0, 5))
    for i, k in enumerate(c): k["name"] = f"k{i}"
    return c

def stat(erg, maske_fn):
    PN, PC, PA, kl = erg["PN"], erg["PC"], erg["PA"], erg["klasse"]; m = maske_fn(PN, PC)
    a = PA[m]; return dict(m2=float(a.sum()), fehlt=float(PA[m & (kl == 2)].sum()), mittel=float(PA[m & (kl == 1)].sum()), gut=float(PA[m & (kl == 0)].sum()))

west = lambda PN, PC: (PN[:, 0] < -0.9) & (np.abs(PC[:, 0] + 10) < 0.3)
under = lambda PN, PC: (PN[:, 2] < -0.9) & (np.abs(PC[:, 2] - 6) < 0.3) & (np.abs(PC[:, 0]) < 2.5) & (PC[:, 1] > 5.9)
seite = lambda nx, ny: (lambda PN, PC: (PN[:, 0] * nx + PN[:, 1] * ny > 0.9))

def lauf(mesh, cams, name, wolke=None, occ=None, quelle=None, ziel=0.99):
    sperre = sbox(-10, -6, 10, 6)
    erg = FL.analysiere(np.asarray(mesh.vertices), np.asarray(mesh.faces), quelle, occ, cams, 0.0, None, wolke, optionen=dict(max_stand=25, ziel=ziel), freie_flaechen=sperre, log=lambda *a: None)
    FL.schreibe(erg, os.path.join(OUT, name), None, dict(n_verwendet=len(cams)), dict(objekt="synthetisch_" + name, flaeche=name, cams=cams, vorschau=True), None, None, mesh, None)
    return erg


def fall_a():
    print("Fall A: Quader+Erker, Kameras auf 3 Seiten (Osten 0 Grad, Norden 90, Sueden 270; Westen 180 fehlt)")
    m = haus(True)
    cams = seiten_kameras([0, 90, 270])
    erg = lauf(m, cams, "A_vorher")
    w = stat(erg, west); u = stat(erg, under); o = stat(erg, seite(1, 0)); n = stat(erg, lambda PN, PC: (PN[:, 1] > 0.9) & (np.abs(PC[:, 1] - 6) < 0.3))
    print("   West", w, "\n   Erker-Unterseite", u, "\n   Ost", o)
    pruefe("Westwand >= 90 % fehlt", w["m2"] > 50 and w["fehlt"] >= 0.9 * w["m2"], f"{w['fehlt']:.0f}/{w['m2']:.0f} m2")
    pruefe("Erker-Unterseite nicht gut", u["m2"] > 3 and u["gut"] < 0.1 * u["m2"], f"gut {u['gut']:.1f} mittel {u['mittel']:.1f} fehlt {u['fehlt']:.1f} von {u['m2']:.1f} m2")
    pruefe("Ostwand (fotografiert) ueberwiegend gut", o["gut"] >= 0.8 * o["m2"], f"gut {o['gut']:.0f}/{o['m2']:.0f}")
    st = erg["stand"]["standpunkte"]
    vor_west = [g for g in st if g["pos"][0] < -15 and abs(((g["az"] - 90 + 180) % 360) - 180) < 45]
    pruefe("Standpunkt vor der Westwand mit Blick nach Osten", len(vor_west) >= 1, f"{len(st)} Standpunkte; " + "; ".join("(%.0f,%.0f) az %.0f el %.0f" % (g["pos"][0], g["pos"][1], g["az"], g["el"]) for g in st[:6]))
    unter = [g for g in st if g["pos"][1] > 8 and abs(g["pos"][0]) < 12 and g["el"] >= 20]
    pruefe("Standpunkt am Erker mit Blick nach oben (>= 20 Grad)", len(unter) >= 1, f"{len(unter)}")
    # Kameras ergaenzen: Westseite + unter dem Erker
    cams2 = cams + ring((0, 0), 180, ziel=(-10, 0, 5)) + [cam((x, y, 1.6), (0, 7, 6), name=f"u{x}{y}") for x in (-3, 0, 3) for y in (11, 12.5, 14)]
    erg2 = lauf(m, cams2, "A_nachher")
    w2 = stat(erg2, west); u2 = stat(erg2, under)
    print("   nachher West", w2, "\n   nachher Erker-Unterseite", u2)
    pruefe("nachher: Westwand nicht mehr fehlt (< 2 %)", w2["fehlt"] <= 0.02 * w2["m2"], f"fehlt {w2['fehlt']:.1f}/{w2['m2']:.0f} gut {w2['gut']:.0f}")
    pruefe("nachher: Erker-Unterseite gut", u2["gut"] >= 0.8 * u2["m2"], f"gut {u2['gut']:.1f}/{u2['m2']:.1f}")
    pruefe("Dach als vom Boden nicht erreichbar gekennzeichnet", True if (erg["stand"].get("unerreichbar_m2", 0) > 200) else False, f"{erg['stand'].get('unerreichbar_m2', 0):.0f} m2")


def fall_b():
    print("Fall B: ohne STL, nur Quader-Huelle (LoD2-Ersatz) + Wolke auf 3 Seiten")
    m = haus(False); cams = seiten_kameras([0, 90, 270])
    sp = m.sample(400000); sel = (np.abs(sp[:, 0] - 10) < 0.05) | (np.abs(sp[:, 1] - 6) < 0.05) | (np.abs(sp[:, 1] + 6) < 0.05)     # Ost, Nord, Sued; Westwand ohne Punkte
    wolke = sp[sel].astype(np.float32)
    erg = lauf(m, cams, "B_lod2", wolke=wolke)
    w = stat(erg, west);
    d = erg["wolke_duenn"]; PA = erg["PA"]; ma = west(erg["PN"], erg["PC"]); mo = seite(1, 0)(erg["PN"], erg["PC"]) & (np.abs(erg["PC"][:, 0] - 10) < 0.3)
    dw = float((PA[ma] * d[ma]).sum() / PA[ma].sum()); do = float((PA[mo] * d[mo]).sum() / PA[mo].sum())
    pruefe("Westwand fehlt (LoD2-Huelle ohne STL)", w["fehlt"] >= 0.9 * w["m2"], f"{w['fehlt']:.0f}/{w['m2']:.0f}")
    pruefe("Wolke duenn Westwand >= 90 %", dw >= 0.9, f"{dw:.2f}")
    pruefe("Wolke duenn Ostwand <= 20 %", do <= 0.2, f"{do:.2f} ({len(wolke)} Punkte)")


def fall_c():
    print("Fall C: Fotonetz nur auf 3 Seiten + Quader-LoD2")
    full = haus(False); keep = ~((full.face_normals[:, 0] < -0.9) & (np.abs(full.triangles_center[:, 0] + 10) < 0.1))
    netz = trimesh.Trimesh(full.vertices, full.faces[keep], process=False)
    pruefe("Netz allein hat auf der Westseite keine Flaeche (die Falle)", int(west(netz.face_normals, netz.triangles_center).sum()) == 0 if False else float(netz.area_faces[(netz.face_normals[:, 0] < -0.9)].sum()) == 0.0)
    mesh, q = FL.netz_mit_lod2(netz, full)
    ak = float(np.sum(mesh.area_faces[q == 1])); pruefe("LoD2-Ergaenzung nur dort, wo das Netz fehlt (Westwand 120 m2 minus 0,5-m-Randstreifen an den Netzkanten)", 85 < ak < 125, f"{ak:.0f} m2 LoD2-Ergaenzung")
    cams = seiten_kameras([0, 90, 270]); erg = lauf(mesh, cams, "C_netz", quelle=q)
    w = stat(erg, west)
    pruefe("Westwand 'fehlt' trotz Netz-Loch", w["m2"] > 50 and w["fehlt"] >= 0.9 * w["m2"], f"{w['fehlt']:.0f}/{w['m2']:.0f}")


def fall_d():
    print("Fall D: Georeferenz-Anpassung + UTM-Rundlauf")
    L = Polygon([(0, 0), (30, 0), (30, 12), (14, 12), (14, 20), (0, 20)])         # asymmetrisch
    from shapely import affinity
    th, t = 37.0, (123.4, -56.7); ziel = affinity.translate(affinity.rotate(L, th, origin=(0, 0)), *t)
    th2, t2, iou, ex = FL.fit_grundriss(L, ziel)
    dth = abs(((th2 - th + 180) % 360) - 180); dt = float(np.hypot(t2[0] - t[0], t2[1] - t[1]))
    pruefe("Grundriss-Fit findet Drehung/Verschiebung", dth < 0.3 and dt < 0.05 and iou > 0.999, f"dTheta {dth:.3f} Grad, dt {dt:.3f} m, IoU {iou:.4f}")
    e, n = FL.utm32(47.99493, 7.85266); la, lo = FL.utm32_zurueck(e, n)
    pruefe("UTM <-> WGS84 Rundlauf", abs(la - 47.99493) < 1e-8 and abs(lo - 7.85266) < 1e-8, f"{e:.2f} {n:.2f}")


if __name__ == "__main__":
    import gpu_slot; gpu_slot.belegen("test_foto_luecken")
    for f in (fall_d, fall_c, fall_b, fall_a): f()
    print("\nBESTANDEN" if not FEHLER else "\nDURCHGEFALLEN: " + "; ".join(FEHLER)); sys.exit(1 if FEHLER else 0)
