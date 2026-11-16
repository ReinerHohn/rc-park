#!/usr/bin/env python3
"""fassaden_kette.py <objekt.json> --netz <mesh.npz> [--wand NAME ax ay bx by aussen_x aussen_y z1 ...] [--min_laenge 3] [--px 0.05] - Fassaden-Kette AUTOMATISCH je Wand.

Was am 15.11.2026 am Schwabentor von Hand lief, in einem Lauf (Nutzer: "Baue alles automatisch in die Pipeline, was irgendwie geht"):
  1. Waende: --wand (gemessene Wandgerade) oder alle Aussenkanten des LoD2-Grundrisses aus dach.json (>= --min_laenge), Hoehe bis hoechster Dachpunkt des Teils.
  2. Fotos je Wand automatisch waehlen (fotos_fuer_wand): Abdeckung der Wandflaeche x Aufloesung x Frontalitaet aus den K-Dateien, beste 3.
  3. relief_einsatz.py (Hoehenbild aus dem Netz, ab z 0, mit Oeffnungsmaske) -> relief/<wand>.npz
  4. relief_putz.py (Putz eben ueber die Fotofarbe) -> <wand>_putz.npz        (faellt weg, wenn kein Putz gefunden)
  5. steine_generieren.py (Loecher ausserhalb von Putz und Oeffnungen) -> <wand>_voll.npz
  5c. mit --fotosteine: steine_aus_foto.py --foto auto oberhalb --foto_ab -> <wand>_foto.npz (anbauen() setzt es vor das grobe Relief)
  5b. mit --fein SPARSE BILDER: tiefe_lokal.py fuer die Steinzone der Wand (1 cm, GPU) + relief_mischen.py -> <wand>_misch.npz (2 cm), wird von anbauen() vor das grobe Relief gesetzt.
  6. Bericht audit/fassaden_kette.json (Wand, Fotos, Loch-/Putz-/Generiert-Anteile) + je Wand das Bild relief/<wand>_voll.jpg zum ANSEHEN.
Im Generator: `from fassaden_kette import anbauen; koerper = anbauen(koerper, OBJ)` vereinigt alle *_voll.npz (nur innerhalb der nach aussen verschobenen Koerperhuelle).
Grenzen: Auskragungen/Erker (Band 0,6 m) und regelmaessige Bauteile (Fenster, Boegen, Uhr) bleiben Sache von bauteile.py; generierte Steine sind ANNAHME.
"""
import sys, os, json, glob, argparse, subprocess, numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); PY = "/media/oem/scan/venv-seg/bin/python"


def fotos_fuer_wand(od, a, b, n, z0, z1, k=3, max_winkel=65.0):
    """Beste Fotos fuer eine Wandflaeche: Anteil der 5 x 7 Rasterpunkte im Bild x Pixel je Meter x cos(Blickwinkel). Keine Verdeckungspruefung."""
    import cv2
    a = np.array(a, float); b = np.array(b, float); G = np.array([[*(a + s * (b - a)), z] for s in np.linspace(0.08, 0.92, 5) for z in np.linspace(z0 + 0.08 * (z1 - z0), z1 - 0.08 * (z1 - z0), 7)]); c = G.mean(0); erg = []
    for f in glob.glob(os.path.join(od, "messprotokoll", "K-*.json")):
        K = json.load(open(f)).get("kamera")
        if not K or "rvec" not in K: continue
        R = cv2.Rodrigues(np.array(K["rvec"]))[0]; t = np.array(K["t"]); S = -R.T @ t; d = S - c; L = float(np.linalg.norm(d)); w = np.degrees(np.arccos(np.clip(d[:2] @ n / max(np.linalg.norm(d[:2]), 1e-9), -1, 1)))
        if w > max_winkel or L > 400: continue
        p = G @ R.T + t; ok = (p[:, 2] > 0); x = K["f_px"] * p[:, 0] / np.where(ok, p[:, 2], 1) + K["cx"]; y = K["f_px"] * p[:, 1] / np.where(ok, p[:, 2], 1) + K["cy"]
        ab = float((ok & (x > 0) & (x < 2 * K["cx"]) & (y > 0) & (y < 2 * K["cy"])).mean())
        if ab >= 0.4: erg.append((ab * min(K["f_px"] / L, 250.0) * np.cos(np.radians(w)), ab, os.path.basename(f)[2:-5]))
    erg.sort(reverse=True); return [e[2] for e in erg[:k]], erg[:k]


def waende_aus_lod2(od, min_laenge):
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    D = json.load(open(os.path.join(od, "dach.json"))); teile = [Polygon(t["grundriss_uv"]).buffer(0) for t in D["teile"]]; U = unary_union(teile).buffer(0.05).buffer(-0.05)
    U = max(U.geoms, key=lambda g: g.area) if U.geom_type == "MultiPolygon" else U; zmax = max(float(t.get("beste", {}).get("first") or t.get("dom1_p95") or 10.0) for t in D["teile"])
    P = np.array(U.exterior.coords)[:-1]; m = np.array(U.centroid.coords[0]); W = []
    for i in range(len(P)):
        a, b = P[i], P[(i + 1) % len(P)]; L = float(np.linalg.norm(b - a))
        if L < min_laenge: continue
        t = (b - a) / L; n = np.array([t[1], -t[0]]); n = n if (0.5 * (a + b) - m) @ n > 0 else -n
        W.append(dict(name="w%02d" % len(W), a=a.tolist(), b=b.tolist(), aussen=(0.5 * (a + b) + 10 * n).tolist(), z1=zmax))
    return W


def anbauen(koerper, objekt_json, tiefe=0.4):
    """Fuer Generatoren: alle relief/*_voll.npz der Fassaden-Kette als Platten anfuegen, begrenzt auf die nach aussen verschobene Koerperhuelle."""
    sys.path.insert(0, HIER); from relief_einsatz import koerper as relief_koerper
    od = os.path.dirname(os.path.abspath(objekt_json)); B = os.path.join(od, "audit", "fassaden_kette.json")
    if not os.path.exists(B): return koerper, []
    belege = []; basis = koerper      # 16.11.2026: Huelle je Wand aus dem GRUNDKOERPER, nicht aus dem wachsenden Koerper (sonst wird jede weitere Wand gegen alle frueheren Reliefs geschnitten: schwab_auto, 8 Waende, 13,6 GB -> vom System beendet)
    for w in json.load(open(B))["waende"]:
        f = os.path.join(od, "relief", w["name"] + "_voll.npz")
        if not os.path.exists(f) or w.get("aus"): continue
        Z = np.load(f); n = Z["n"]; hu = basis + basis.translate((0.8 * n[0], 0.8 * n[1], 0.0)); koerper.num_tri();      # num_tri: Zwischenergebnis ausrechnen, damit der Rechenbaum nicht ueber alle Waende waechst
        fm = os.path.join(od, "relief", w["name"] + "_misch.npz"); tf = [tuple(w["fein_feld"])] if w.get("fein_feld") and os.path.exists(fm) else []
        ff = os.path.join(od, "relief", w["name"] + "_foto.npz"); hat_foto = bool(w.get("foto_feld")) and os.path.exists(ff)
        if not w.get("nur_foto"): koerper = koerper + (relief_koerper(f, tiefe=tiefe, trend=True, tief_felder=tf + ([tuple(w["foto_feld"])] if hat_foto else [])) ^ hu)
        if hat_foto: koerper = koerper + (relief_koerper(ff, tiefe=tiefe, trend=True, rand_auslauf=False) ^ hu); belege.append(dict(seite="wand", element=f"Quader mit Fugen aus dem Foto, Fassade {w['name']} ab z {w['foto_feld'][2]:.0f} m", quelle="tools/steine_aus_foto.py --foto auto (bestes Foto, Verdeckung, Gegenfoto)", steine=w.get("foto_steine"), hinweis="Fugenlage aus dem Foto, Fugentiefe/Bosse ANNAHME; relief/<wand>_foto.jpg ansehen"))
        if tf: koerper = koerper + (relief_koerper(fm, tiefe=tiefe, trend=True) ^ hu)                 # lokale Feinrechnung (tools/tiefe_lokal.py + relief_mischen.py) vor dem groben Relief
        belege.append(dict(seite="wand", element=f"Relief Fassade {w['name']} (Fassaden-Kette)", quelle="Netz der dichten Wolke (Hoehenbild 5 cm); Putz ueber Fotofarbe (" + ", ".join(w.get("fotos", [])[:3]) + "); Loecher generiert",
                           generiert_anteil=w.get("generiert"), hinweis="Scan-Relief, kein Mass; generierte Steine = ANNAHME"))
    return koerper, belege


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--netz", required=True); ap.add_argument("--wand", nargs=8, action="append", default=[]); ap.add_argument("--min_laenge", type=float, default=3.0)
    ap.add_argument("--px", type=float, default=0.05); ap.add_argument("--massstab", nargs=4, help="wie relief_putz.py (Relief im Rohrahmen)")
    ap.add_argument("--fotosteine", action="store_true", help="Stufe 5c: Quader mit Fugen aus dem besten Foto oberhalb --foto_ab (tools/steine_aus_foto.py --foto auto)"); ap.add_argument("--foto_ab", type=float, default=10.0); ap.add_argument("--nachbar_stl", default="", help="STL der Nachbarobjekte fuer die Verdeckung"); ap.add_argument("--fein", nargs=2, metavar=("SPARSE", "BILDER"), help="je Wand zusaetzlich die lokale Feinrechnung der Tiefe fuer die Steinzone (tools/tiefe_lokal.py, GPU, ~11 min je Wand) und relief_mischen.py"); ap.add_argument("--fein_max_size", default="3200"); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); rd = os.path.join(od, "relief"); os.makedirs(rd, exist_ok=True)
    W = [dict(name=w[0], a=[float(w[1]), float(w[2])], b=[float(w[3]), float(w[4])], aussen=[float(w[5]), float(w[6])], z1=float(w[7])) for w in a.wand] or waende_aus_lod2(od, a.min_laenge)
    def lauf(cmd):
        r = subprocess.run([PY, "-W", "ignore", "-I"] + cmd, capture_output=True, text=True); z = (r.stdout.strip().splitlines() or [r.stderr.strip()[-200:]])[-1]; print("   ", z[:200], flush=True); return r.returncode
    for w in W:
        A = np.array(w["a"]); Bp = np.array(w["b"]); L = float(np.linalg.norm(Bp - A)); t = (Bp - A) / L; n = np.array([t[1], -t[0]]); n = n if (np.array(w["aussen"]) - A) @ n > 0 else -n
        fotos, bew = fotos_fuer_wand(od, A, Bp, n, 0.0, w["z1"]); w["fotos"] = fotos; w["laenge"] = round(L, 2); print(f"WAND {w['name']}: {L:.1f} m, z bis {w['z1']:.1f}, Fotos {[(f[-12:], round(s_)) for s_, _, f in bew]}", flush=True)
        r0 = os.path.join(rd, w["name"] + ".npz"); r1 = os.path.join(rd, w["name"] + "_putz.npz"); r2 = os.path.join(rd, w["name"] + "_voll.npz")
        rc = lauf([os.path.join(HIER, "relief_einsatz.py"), a.netz, r0, "--ecke_a", *map(str, w["a"]), "--ecke_b", *map(str, w["b"]), "--aussen", *map(str, w["aussen"]), "--feld", "0.1", str(round(L - 0.1, 2)), "0", str(w["z1"]), "--px", str(a.px), "--klemme", "-0.10", "0.15"])
        leer = bool(rc) or not os.path.exists(r0) or float(np.load(r0)["lochanteil"]) > 0.6
        if leer:                                                          # 16.11.2026 (Haertetest ober_tvdr): Netz deckt die Wand nicht -> frueher AUS. Jetzt: leeres Relief als Traeger, Putz und Steine NUR aus Fotos (Stufe 5c ab Boden)
            w["netz"] = "deckt die Wand nicht"; print("    Netz deckt die Wand nicht - nur Fotostufe", flush=True)
            if not a.fotosteine or not fotos or lauf([os.path.join(HIER, "relief_einsatz.py"), "-", r0, "--ecke_a", *map(str, w["a"]), "--ecke_b", *map(str, w["b"]), "--aussen", *map(str, w["aussen"]), "--feld", "0.1", str(round(L - 0.1, 2)), "0", str(w["z1"]), "--px", str(a.px)]) != 0: w["aus"] = "kein Netz, keine Fotostufe"; continue
        Z = np.load(r0); w["loch"] = round(float(Z["lochanteil"]), 3); w["oeffnung"] = round(float(Z["oeffnung"].mean()), 3)
        quelle = r0
        if fotos and lauf([os.path.join(HIER, "relief_putz.py"), r0, r1, a.objekt, *fotos, "--feld", "0", str(L), "0", str(w["z1"])] + (["--massstab", *a.massstab] if a.massstab else [])) == 0:
            quelle = r1; w["putz"] = round(float(np.load(r1)["putz"].mean()), 3)
        if leer:
            if quelle != r1: w["aus"] = "kein Netz und kein Putz erkannt (Fotofarbe) - nichts zu tun"; print("    AUS:", w["aus"]); continue
            import shutil; shutil.copy(r1, r2); w["generiert"] = 0.0
        elif lauf([os.path.join(HIER, "steine_generieren.py"), quelle, r2, "--max_loch_m2", "1.5"]) == 0: w["generiert"] = round(float(np.load(r2)["generiert_anteil"]), 3)
        else: w["aus"] = "steine_generieren fehlgeschlagen"; continue
        fab = 0.0 if leer else a.foto_ab
        if a.fotosteine and "putz" in np.load(quelle).files and w["z1"] > fab + 2.0:      # 16.11.2026 Stufe 5c: oberhalb --foto_ab (Strassenfotos zu flach fuer brauchbares Scan-Relief) Quader/Gewaende/Baender
            rfo = os.path.join(rd, w["name"] + "_foto.npz"); stl_ = os.path.join(os.path.dirname(os.path.dirname(od)), json.load(open(a.objekt))["stl"])                                 # mit Fugen aus dem BESTEN Foto, direkt auf der Wandebene, Verdeckung gegen das Modell + Gegenfoto (Baeume)
            if os.path.exists(stl_) and lauf([os.path.join(HIER, "steine_aus_foto.py"), quelle, rfo, "-", "0", "-", "--foto", "auto", "--objekt", a.objekt, "--stl", stl_ + ("," + a.nachbar_stl if a.nachbar_stl else ""),
                                              "--feld", "0.1", str(round(L - 0.1, 2)), str(fab), str(w["z1"]), "--px", "0.03", "--nah", "0", "--streng"] + (["--massstab", *a.massstab] if a.massstab else [])) == 0 and os.path.exists(rfo):
                w["foto_feld"] = [0.0, round(L, 2), fab, round(float(w["z1"]), 2)]; w["foto_steine"] = int(np.load(rfo)["steine"])
        if leer:
            if not w.get("foto_feld"): w["aus"] = "kein Netz und kein brauchbares Foto fuer Steine"; print("    AUS:", w["aus"]); continue
            w["nur_foto"] = True                                          # anbauen(): nur die Fotoplatte, keine leere Grundplatte (gab 193 Splitterkoerper am Haertetest)
        if a.fein and not leer:                                           # Steinzone = Zeilen mit >= 30 % echtem Nicht-Putz-Relief; zusammenhaengender Block von unten, hoechstens 12 m
            Zv = np.load(r2); rel_ = Zv["rel"]; H_ = rel_.shape[0]; pz = Zv["putz"] if "putz" in Zv.files else np.zeros_like(rel_, bool); pz = np.vstack([pz, np.zeros((H_ - pz.shape[0], pz.shape[1]), bool)]) if pz.shape[0] < H_ else pz
            stein = ((rel_ != 0) & ~pz).mean(1) >= 0.3; k_ = H_
            while k_ > 0 and (stein[k_ - 1] or (H_ - k_) * a.px < 1.5): k_ -= 1
            z1f = round(min((H_ - k_) * a.px, 12.0), 2)
            if z1f >= 2.0:
                feld = ["0.1", str(round(L - 0.1, 2)), "0", str(z1f)]; rf_ = subprocess.run(["/media/oem/scan/venv-colmap/bin/python", "-I", os.path.join(HIER, "tiefe_lokal.py"), a.objekt, a.fein[0], a.fein[1], "--name", w["name"] + "_fein", "--a", *map(str, w["a"]), "--b", *map(str, w["b"]),
                                                                                                           "--aussen", *map(str, w["aussen"]), "--feld", *feld, "--max_size", a.fein_max_size] + (["--massstab", *a.massstab] if a.massstab else []), capture_output=True, text=True)
                print("   ", (rf_.stdout.strip().splitlines() or [rf_.stderr.strip()[-200:]])[-1][:200], flush=True); rfe = os.path.join(rd, w["name"] + "_fein.npz")
                if rf_.returncode == 0 and os.path.exists(rfe) and lauf([os.path.join(HIER, "relief_mischen.py"), rfe, r2, os.path.join(rd, w["name"] + "_misch.npz")]) == 0:
                    w["fein_feld"] = [0.0, round(L, 2), 0.0, round(z1f - 0.1, 2)]; w["fein_anteil"] = round(float(np.load(os.path.join(rd, w["name"] + "_misch.npz"))["fein"].mean()), 3)
    os.makedirs(os.path.join(od, "audit"), exist_ok=True); json.dump(dict(netz=a.netz, waende=W), open(os.path.join(od, "audit", "fassaden_kette.json"), "w"), indent=1, ensure_ascii=False)
    print("->", os.path.join(od, "audit", "fassaden_kette.json"), "| ANSEHEN: relief/<wand>_voll.jpg")


if __name__ == "__main__":
    sys.exit(main())
