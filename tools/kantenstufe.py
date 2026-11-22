#!/usr/bin/env python3
"""kantenstufe.py - KANTENSTUFE der Gesamtkette (KERNMETHODE, Nutzer 15.11.2026): Fotokanten + SfM-Kameras -> 3D-Kanten um die Modellflaeche -> Bewertung.
Allgemein fuer jedes Objekt (keine Kaufhaus-Pfade). Die dichte Wolke wird NICHT benutzt.

  /media/oem/scan/venv-seg/bin/python -I tools/kantenstufe.py modelle/<obj>/objekt.json --ausrichtung <SFM-AUSRICHTUNG.json> --bilder <ORDNER> --aus <DIR>
        [--max_fotos 80] [--refs 30] [--band 0.5] [--vorn 2.0] [--tol 0.15] [--nur_bewerten] [--suchraum messkoerper|modell] [--messkoerper STL] [--wolke W.npy] [--geraet cuda]
Schritte:
  1. Kameras aus der Ausrichtung (X_sfm = ..., je Kamera R, t im Modellrahmen = STL-Meter) -> DIR/kam.json (kam_lot2-Format: Rn, tn, C, f, cx, cy, W, H, modell, params).
     Auswahl: Kameras, die den Messkoerper sehen (Anteil projizierter Modellpunkte im Bild, Abstand < 80 m), gleichmaessig ueber 12 Blickrichtungen -> DIR/kam_wahl.json.
  2. tools/stabil_alle.py (GPU) -> DIR/stabil/<foto>.png
  3. tools/kanten_tiefe_sweep_flaeche.py --flaeche MESSKOERPER --flaeche_skala --band --vorn --huelle --ziel_auto (Blickziel je Referenz aus der Flaeche) -> DIR/sweep.npz
  4. Bewertung in 3D (gpu_knn): Modellkanten (Knick > 30 Grad + Rand, alle 5 cm) gegen Sweep-Kantenpunkte:
       Praezision = Anteil Modellkanten-Proben (im von Kanten belegten Bereich) mit Fotokante < tol  (rot = erfundene Kante)
       Recall     = Anteil Sweep-Punkte mit Modellkante < tol                                        (gelb = Fotokante ohne Modell = fehlendes Feature)
     Fehlende Kanten als Haufen (Raster 0,5 m, >= 30 Punkte) mit Seite/Hoehe -> Arbeitsliste fuer Generator-Features (kanten_features.py --sweep).
Ausgabe: DIR/kanten_bericht.json, modelle/<obj>/audit/kanten3d.png (Seitenansichten). Exit 0; rc 4 = zu wenig Kantenpunkte (Kameras/Stabilkarten pruefen).
22.11.2026 KREISFALL (0_DURCHBRUCH_AGENTEN_SCHLEIFE.md "Zirkulaere Messung"): bisher suchte der Sweep nur +-0,5 m um das STL des VORMODELLS und die Kameras wurden gegen
das Vormodell gewaehlt - Kanten > 0,5 m vor dem Vormodell (Vordach, Erker, Traufe) fand die Kette nie, Strahlen durch gebaute Oeffnungen suchten an der Rueckwand,
und ohne Vorlauf gab es keinen Suchraum. Jetzt (--suchraum messkoerper, Standard): Suchraum, Blickziel, Kameraauswahl und Box nur aus dem MODELLFREIEN Messkoerper
(tools/fassade_ortho.py --nur-messkoerper: LoD2 flach + Wandversatz aus Fotokanten, geschlossen), Band asymmetrisch --vorn 2,0 m vor bis --band 0,5 m hinter der Flaeche
(senkrecht, je Strahl umgerechnet), Strahlen am Messkoerper vorbei ueber die Huelle (--huelle); Tiefe = Triangulation ueber die Nachbarfotos (unveraendert);
dichte Wolke nur als Lage-Veto (--wolke, Punkte weiter als --veto_m von jeder Wolkenstelle fallen weg). Das gebaute Modell wird NUR noch bewertet (Schritt 4).
Waechter: tools/test_kantenstufe_kreis.py (zwei Vormodelle -> bitgleiche Kanten, Vordachkante 1,2 m vor der Wand gefunden). --suchraum modell = alter Weg (nur Vergleich).
Grenze: Teile weiter als --vorn vor der Messflaeche fehlen weiterhin (dafuer Foto-Tor teil_fotoform/foto_diff).
"""
import sys, os, json, glob, argparse, subprocess, time, numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); PY = "/media/oem/scan/venv-seg/bin/python"
sys.path.insert(0, os.path.join(ROOT, "tools"))


BILD_ENDUNGEN = (".jpg", ".jpeg", ".png")


def bild_finden(bd, name):
    """Bilddatei zur Kamera `name` (Kennung ohne Endung, wie in der Ausrichtung). 17.11.2026 (Durchsicht): der Ersatzweg `glob(name + "*")` nahm die erste Datei mit diesem ANFANG -
    fuer IMG_1 ohne eigene Datei (oder mit .JPEG, das nicht in der Liste stand) war das IMG_10.jpg: Kamera von Bild 1 mit dem Inhalt von Bild 10, die Kantenstufe rechnete still damit.
    Jetzt: (1) genau diese Datei, (2) Datei mit genau diesem Namen vor der Endung (Endung in beliebiger Schreibweise), (3) `name_<zusatz>` (Kaufhaus: 122 -> 122_<quelle>.jpg) NUR wenn eindeutig."""
    if os.path.isfile(os.path.join(bd, name)): return name
    try: alle = sorted(f for f in os.listdir(bd) if f.lower().endswith(BILD_ENDUNGEN))
    except OSError: return None
    g = [f for f in alle if os.path.splitext(f)[0] == name]
    if not g: g = [f for f in alle if f.startswith(name + "_")]; g = g if len(g) == 1 else []
    return g[0] if g else None


def kameras(A, bd):
    K = {}
    for nm, k in A["kameras"].items():
        f = bild_finden(bd, nm)
        if not f or "R" not in k: continue
        R = np.array(k["R"], float); t = np.array(k["t"], float); fp = float(k["f_px_original"]); k1 = float((k.get("k") or [0.0])[0])
        K[f] = dict(Rn=R.tolist(), tn=t.tolist(), C=(-R.T @ t).tolist(), f=fp, cx=float(k["cx"]), cy=float(k["cy"]), W=int(float(k.get("bild_b", 2 * float(k["cx"])))),
                    H=int(float(k.get("bild_h", 2 * float(k["cy"])))), modell="SIMPLE_RADIAL", params=[fp, float(k["cx"]), float(k["cy"]), k1])
    return K


def waehlen(K, V, n):
    """Kameras, die das Modell sehen; je 30-Grad-Sektor (Blick um die Modellmitte) die besten zuerst (Rundlauf)."""
    mid = V.mean(0); sek = {}
    for f, k in K.items():
        R = np.array(k["Rn"]); t = np.array(k["tn"]); X = V @ R.T + t; z = X[:, 2]; ok = z > 0.5
        u = k["f"] * X[ok, 0] / z[ok] + k["cx"]; v = k["f"] * X[ok, 1] / z[ok] + k["cy"]
        sicht = float(((u >= 0) & (u < k["W"]) & (v >= 0) & (v < k["H"])).sum()) / len(V); d = float(np.linalg.norm(np.array(k["C"]) - mid))
        if sicht < 0.2 or d > 80: continue
        az = int((np.degrees(np.arctan2(*(np.array(k["C"])[:2] - mid[:2])[::-1])) % 360) // 30); sek.setdefault(az, []).append((-sicht / max(d, 3) ** 0.5, f))
    for s in sek.values(): s.sort()
    out = []; i = 0
    while len(out) < n and any(i < len(s) for s in sek.values()):
        for s in sek.values():
            if i < len(s) and len(out) < n: out.append(s[i][1])
        i += 1
    return out, {str(a * 30): len(s) for a, s in sorted(sek.items())}


def messkoerper_laden(a, obj, objp, skala):
    """Suchraum der Kantenstufe (22.11.2026 Kreisfall): (Netz in Meter/Modellrahmen oder None, STL-Pfad, Quelle). Nie das gebaute Modell (ausser --suchraum modell)."""
    import trimesh
    if a.suchraum == "modell":
        p = os.path.join(ROOT, obj["stl"]); m = trimesh.load(p); m.apply_scale(skala); return m, p, "modell (ALTER WEG, zirkulaer: Suchraum = Vormodell)"
    mk = os.path.abspath(a.messkoerper) if a.messkoerper else os.path.join(os.path.abspath(a.aus), "messkoerper.stl")
    if not a.messkoerper:
        r = subprocess.run([PY, "-W", "ignore", "-I", os.path.join(ROOT, "tools/fassade_ortho.py"), objp, "--nur-messkoerper", mk], capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(mk):
            return None, mk, "kein Messkoerper: " + ((r.stdout + r.stderr).strip().splitlines() or ["?"])[-1][:200]
    m = trimesh.load(mk); m.apply_scale(skala)
    return (m, mk, "messkoerper (modellfrei: LoD2 flach + Wandversatz aus Fotokanten)") if len(m.faces) else (None, mk, "Messkoerper leer")


def abstand(A, B, geraet):
    """Abstand jedes Punkts aus A zum naechsten aus B (GPU gpu_knn; cpu = cKDTree fuer den Waechter-Test)."""
    if geraet == "cpu":
        from scipy.spatial import cKDTree
        return cKDTree(np.asarray(B, float)).query(np.asarray(A, float))[0]
    from gpu_knn import min_abstand
    return np.asarray(min_abstand(A, B))


def wolke_veto(P, wolke, veto_m, lo, hi, geraet):
    """Lage-Veto aus der dichten Wolke (nur grobe Ausreisser weg, nie Form): Kantenpunkte weiter als veto_m von jeder Wolkenstelle (Raster 0,1 m in der Box) fallen weg."""
    W = np.load(wolke, mmap_mode="r"); st = max(1, len(W) // 2_000_000); W = np.asarray(W[::st, :3], np.float32)
    W = W[np.all((W >= lo) & (W <= hi), 1)]
    if len(W) < 1000: return np.ones(len(P), bool), f"zu wenig Wolkenpunkte in der Box ({len(W)}) - kein Veto"
    W = np.unique(np.floor(W / 0.1).astype(np.int32), axis=0).astype(np.float32) * 0.1 + 0.05
    ok = abstand(P, W, geraet) <= veto_m
    return ok, f"{int((~ok).sum())} von {len(P)} Kantenpunkten weiter als {veto_m} m von der Wolke (verworfen)"


def modellkanten(m, winkel=30.0, schritt=0.05):
    import trimesh
    adj = m.face_adjacency; ang = m.face_adjacency_angles; E = m.face_adjacency_edges[ang > np.radians(winkel)]
    rand = trimesh.grouping.group_rows(m.edges_sorted, require_count=1); E = np.vstack([E, m.edges_sorted[rand]]) if len(rand) else E
    if not len(E): return np.zeros((0, 3))
    # 21.11.2026 (Tempo: ebenen_abweichung 150 s, davon 79 s hier - Python-Schleife mit 1,26 Mio. linspace): vektorisiert, gleiche Rechenschritte wie
    # A + (B - A) * np.linspace(0, 1, k) je Kante (t_i = i * (1/(k-1)), letzter Punkt genau 1) -> bitgleich (tools/test_kette_tempo.py)
    E = np.asarray(E); V = np.asarray(m.vertices, float); A = V[E[:, 0]]; D = V[E[:, 1]] - A
    L = np.sqrt(np.einsum("ij,ij->i", D, D)); k = np.maximum(2, (L / schritt).astype(int) + 1); kante = np.repeat(np.arange(len(E)), k)
    i = np.arange(int(k.sum())) - np.repeat(np.cumsum(k) - k, k); t = i * (1.0 / (k[kante] - 1)); t[np.cumsum(k) - 1] = 1.0
    return A[kante] + D[kante] * t[:, None]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--ausrichtung", required=True); ap.add_argument("--bilder", required=True)
    ap.add_argument("--aus", required=True); ap.add_argument("--max_fotos", type=int, default=80); ap.add_argument("--refs", type=int, default=30)
    ap.add_argument("--suchraum", choices=("messkoerper", "modell"), default="messkoerper", help="messkoerper = modellfrei (Standard, Kreisfall 22.11.2026); modell = alter, zirkulaerer Weg um das Vormodell")
    ap.add_argument("--messkoerper", default="", help="fertiger Messkoerper-STL (mm wie das Objekt-STL); Standard: tools/fassade_ortho.py --nur-messkoerper DIR/messkoerper.stl")
    ap.add_argument("--vorn", type=float, default=2.0, help="Suchraum vor der Messflaeche (m, senkrecht): Vordach/Erker/Traufe; nur --suchraum messkoerper")
    ap.add_argument("--wolke", default="", help="dichte Wolke (npy N x 3, Modellrahmen) nur als LAGE-VETO"); ap.add_argument("--veto_m", type=float, default=1.5)
    ap.add_argument("--geraet", default="cuda", help="cpu nur fuer den Waechter-Test"); ap.add_argument("--stabil_vorhanden", action="store_true", help="Stabilkarten liegen schon in DIR/stabil (Test)")
    ap.add_argument("--band", type=float, default=0.5); ap.add_argument("--tol", type=float, default=0.15); ap.add_argument("--nur_bewerten", action="store_true"); ap.add_argument("--name", default="", help="Zusatz fuer Bericht/Bild (z.B. _fertig: Bewertung des fertigen Modells nach Fassaden/Bauplan mit dem Sweep der Kantenstufe)")
    a = ap.parse_args(); import trimesh
    objp = os.path.abspath(a.objekt); obj = json.load(open(objp)); od = os.path.dirname(objp); os.makedirs(a.aus, exist_ok=True)
    A = json.load(open(a.ausrichtung if os.path.isabs(a.ausrichtung) else os.path.join(ROOT, a.ausrichtung)))
    skala = float(obj.get("stl_massstab", 87)) / 1000.0; stl = os.path.join(ROOT, obj["stl"])   # Modellrahmen = STL-Meter (kameras_aus_buendel)
    bericht = dict(objekt=os.path.relpath(objp, ROOT), stl=obj["stl"], ausrichtung=a.ausrichtung, start=time.strftime("%Y-%m-%d %H:%M"))
    KJ, KW, SD, SW = (os.path.join(a.aus, n) for n in ("kam.json", "kam_wahl.json", "stabil", "sweep.npz"))
    def ende(fehler):
        bericht["fehler"] = fehler; json.dump(bericht, open(os.path.join(a.aus, f"kanten_bericht{a.name}.json"), "w"), indent=1, ensure_ascii=False); print(fehler, flush=True); return 4
    if not a.nur_bewerten:
        S, sq, squelle = messkoerper_laden(a, obj, objp, skala); bericht.update(suchraum=a.suchraum, suchraum_quelle=squelle, suchraum_stl=os.path.relpath(sq, ROOT))
        print(f"Suchraum: {squelle}", flush=True)
        if S is None: return ende(f"KEIN modellfreier Suchraum ({squelle}) - LoD2/rahmen im Objekt pruefen; --suchraum modell waere der zirkulaere alte Weg")
        vorn = a.vorn if a.suchraum == "messkoerper" else 0.0; slo, shi = S.bounds; box = ",".join(f"{x:.2f}" for x in np.r_[slo - vorn - 1.0, shi + vorn + 1.0])
        K = kameras(A, a.bilder); json.dump(K, open(KJ, "w"))
        V = S.sample(4000, seed=0) if len(S.faces) else S.vertices; wahl, sek = waehlen(K, np.asarray(V), a.max_fotos)      # Kameraauswahl gegen den Messkoerper (nicht das Vormodell)
        json.dump({f: K[f] for f in wahl}, open(KW, "w")); bericht.update(kameras=len(K), gewaehlt=len(wahl), sektoren=sek, vorn_m=vorn)
        print(f"Kameras {len(K)}, gewaehlt {len(wahl)} (Sektoren {sek})", flush=True)
        if len(wahl) < 6: return ende("weniger als 6 Kameras sehen den Messkoerper")
        if not a.stabil_vorhanden: subprocess.run([PY, "-I", os.path.join(ROOT, "tools/stabil_alle.py"), KW, a.bilder, SD], check=True)
        subprocess.run([PY, "-I", os.path.join(ROOT, "tools/kanten_tiefe_sweep_flaeche.py"), KW, SD, SW, "--flaeche", sq, "--flaeche_skala", str(skala), "--box3", box,
                        "--band", str(a.band), "--ziel_auto", "--nbdist", "80", "--refs", str(a.refs), "--nb", "12", "--maxpx", "40000", "--geraet", a.geraet]
                       + (["--vorn", str(vorn), "--huelle"] if vorn > 0 else []), check=True)
        if a.wolke and os.path.exists(a.wolke):                                 # Lage-Veto (KERNMETHODE: Wolke nie Form, nur Lage)
            try:
                Z = dict(np.load(SW)); ok, txt = wolke_veto(Z["P"].astype(float), a.wolke, a.veto_m, slo - vorn - 1.0, shi + vorn + 1.0, a.geraet)
                if not ok.all(): np.savez(SW, **{k: (v[ok] if k in ("P", "s", "ref") else v) for k, v in Z.items()})
                bericht["wolke_veto"] = txt
            except Exception as e_: bericht["wolke_veto"] = f"ausgefallen ({type(e_).__name__}: {str(e_)[:150]}) - Kanten ohne Veto"
            print("Wolke-Veto:", bericht["wolke_veto"], flush=True)
    Z = np.load(SW); P = Z["P"].astype(float); bericht["sweep_punkte"] = int(len(P))
    if len(P) < 2000: return ende(f"nur {len(P)} Kantenpunkte")
    if not os.path.exists(stl): return ende(f"Kanten gefunden ({len(P)} Punkte), aber kein Modell {obj['stl']} zum Bewerten")
    m = trimesh.load(stl); m.apply_scale(skala); lo, hi = m.bounds                # das gebaute Modell wird nur BEWERTET, es bestimmt keine Kante
    E = modellkanten(m); dP = abstand(P, E, a.geraet); dE = abstand(E, P, a.geraet)
    belegt = dE < 1.0                                                          # nur Modellkanten, in deren Naehe ueberhaupt Fotokanten gefunden wurden (sonst ungesehen)
    prae = float((dE[belegt] < a.tol).mean()) if belegt.any() else 0.0; rec = float((dP < a.tol).mean()); f1 = 2 * prae * rec / max(prae + rec, 1e-9)
    from dach_bauen import seiten_aus_rahmen
    try: sn = seiten_aus_rahmen(obj)
    except Exception: sn = {"+x": "+x", "-x": "-x", "+y": "+y", "-y": "-y"}
    F = P[dP >= a.tol]; mid = (lo + hi) / 2; hauf = []
    if len(F):
        z = np.floor(F / 0.5).astype(int); u, inv, cnt = np.unique(z, axis=0, return_inverse=True, return_counts=True)
        for i in np.argsort(-cnt)[:40]:
            if cnt[i] < 30: break
            c = F[inv.ravel() == i].mean(0); d = c[:2] - mid[:2]; s = ("+x" if d[0] > 0 else "-x") if abs(d[0]) / max(hi[0] - lo[0], 1) > abs(d[1]) / max(hi[1] - lo[1], 1) else ("+y" if d[1] > 0 else "-y")
            hauf.append(dict(mitte=[round(float(x), 2) for x in c], punkte=int(cnt[i]), seite=sn.get(s, s), hoehe_m=round(float(c[2] - lo[2]), 2)))
    bericht.update(modellkanten_proben=int(len(E)), modellkanten_belegt=round(float(belegt.mean()), 3), praezision=round(prae, 3), recall=round(rec, 3), f1=round(f1, 3), tol_m=a.tol,
                   band_m=a.band, fehlende_kanten_haufen=hauf[:20], hinweis="Recall niedrig = Fotokanten ohne Modellkante (fehlende Features: Fenster, Gesimse, Lisenen ...); Praezision niedrig = Modellkanten ohne Fotokante (erfundene/falsch liegende Form)")
    json.dump(bericht, open(os.path.join(a.aus, f"kanten_bericht{a.name}.json"), "w"), indent=1, ensure_ascii=False)
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 3, figsize=(18, 7)); ok = dP < a.tol; rng = np.random.default_rng(0); sel = rng.choice(len(P), min(len(P), 120000), replace=False)
    for k, (i, j, t) in enumerate([(0, 2, f"Ansicht entlang y ({sn.get('-y', '-y')})"), (1, 2, f"Ansicht entlang x ({sn.get('-x', '-x')})"), (0, 1, "Draufsicht")]):
        x = ax[k]; s = sel[~ok[sel]]; x.scatter(P[s, i], P[s, j], s=0.3, c="orange", label="Fotokante ohne Modellkante"); s = sel[ok[sel]]; x.scatter(P[s, i], P[s, j], s=0.3, c="green", label="Fotokante = Modellkante")
        r = dE >= a.tol; x.scatter(E[r & belegt, i], E[r & belegt, j], s=0.5, c="red", label="Modellkante ohne Fotokante"); x.scatter(E[~belegt, i], E[~belegt, j], s=0.3, c="lightgray", label="Modellkante ungesehen")
        x.set_aspect("equal"); x.set_title(t)
    ax[0].legend(loc="upper left", markerscale=12, fontsize=8)
    fig.suptitle(f"{obj.get('name', '')} Kantenstufe: Praezision {prae:.2f}  Recall {rec:.2f}  F1 {f1:.2f}  (tol {a.tol} m, {len(P)} Sweep-Punkte)"); fig.tight_layout()
    os.makedirs(os.path.join(od, "audit"), exist_ok=True); fig.savefig(os.path.join(od, "audit", f"kanten3d{a.name}.png"), dpi=90)
    print(f"KANTEN: Praezision {prae:.3f} Recall {rec:.3f} F1 {f1:.3f}; fehlende Haufen {len(hauf)}; Bild {os.path.join(od, 'audit', f'kanten3d{a.name}.png')}", flush=True); return 0


if __name__ == "__main__":
    sys.exit(main())
