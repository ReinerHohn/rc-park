#!/usr/bin/env python3
"""flaeche_anpassen.py - Lage/Groesse einer Flaeche (Erker-n-Eck, Zylinder, Rotationsflaeche, Ebene) aus den FOTOS nachziehen (18.11.2026).
Prinzip (Photokonsistenz): stimmt die Geometrie, zeigt jedes Foto an derselben Rasterzelle dieselbe Stelle -> die Streuung (MAD) der Grauwerte ueber die Fotos ist klein und das
fusionierte Wandbild scharf. Eine falsche Achse/Apothem/Radius verwischt es (Gegenprobe synthetisch: Radius +10 % -> Abweichung 8,9 statt 1,8 Graustufen, Achse 10 cm -> 10,0).
Koordinatensuche mit abnehmender Schrittweite ueber die Parameter, Ziel = mittlere Uneinigkeit der Flaechen. Nur Fotos, Kamera und Kantenlage werden gebraucht, keine Wolke.
GRENZEN: braucht Textur (glatter Putz ohne Linien -> flaches Minimum), Verdecker mischen sich in die Streuung, Fotos mit falscher Kamera wirken wie Rauschen; das Ergebnis ist ein Vorschlag
(Vorher/Nachher-Zahl + Bild ansehen), keine Messung.
Aufruf: python3 tools/flaeche_anpassen.py objekt.json --flaechen flaechen.json --id erkerO --aus ORDNER [--zelle 0.02] [--fotos-max 40]
Ausgabe: flaechen_angepasst.json (nur die angepasste Flaeche ersetzt), bericht_<id>.json (Vorher/Nachher), ortho_vorher_/ortho_nachher_ je Teilflaeche."""
import os, sys, json, math, argparse, copy
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flaeche_ortho as FO


def parameter(F):
    """Liste (name, schritt_m_oder_grad, getter, setter) der frei anpassbaren Groessen je Flaechentyp."""
    P = []
    if F["typ"] in ("polygon", "zylinder", "rotation"):
        P += [("achse_x", 0.05, lambda F: F["achse"][0], lambda F, v: F["achse"].__setitem__(0, v)), ("achse_y", 0.05, lambda F: F["achse"][1], lambda F, v: F["achse"].__setitem__(1, v))]
    if F["typ"] == "polygon":
        P += [("apothem", 0.05, lambda F: F["apothem"], lambda F, v: F.__setitem__("apothem", v)), ("winkel0", 2.0, lambda F: F.get("winkel0", 0.0), lambda F, v: F.__setitem__("winkel0", v))]
    if F["typ"] == "zylinder": P += [("r", 0.05, lambda F: F["r"], lambda F, v: F.__setitem__("r", v))]
    if F["typ"] == "rotation":
        def setz(F, v):
            f0 = F.setdefault("_prof0", copy.deepcopy(F["profil"])); F["profil"] = [[z, r * v] for z, r in f0]; F["_skala"] = v
        P += [("r_skala", 0.05, lambda F: F.get("_skala", 1.0), setz)]
    if F["typ"] == "ebene":
        def seto(F, v):
            o0 = F.setdefault("_o0", list(F["o"])); n = np.array(F["n"], float); n /= np.linalg.norm(n); F["o"] = (np.array(o0) + n * v).tolist(); F["_abst"] = v
        P += [("abstand", 0.05, lambda F: F.get("_abst", 0.0), seto)]
    return P


def bewerten(F, cams, a, cache):
    teile = FO.flaechen_expandieren([F]); werte = []
    for T in teile:
        X, N, r = FO.raster(T, a.zelle); _, cnt, _, mad = FO.fusionieren(T, X, N, cams, a, None, cache)
        if np.isfinite(mad).sum() < 0.03 * len(mad): werte.append(60.0)                                # kaum Zellen mit >= 3 Fotos: schlecht
        else: werte.append(float(np.nanmedian(mad)))
    return float(np.mean(werte)), werte


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--flaechen", required=True); ap.add_argument("--id", required=True); ap.add_argument("--aus", required=True)
    ap.add_argument("--zelle", type=float, default=0.02); ap.add_argument("--fotos-max", type=int, default=40); ap.add_argument("--max-winkel", type=float, default=65.0)
    ap.add_argument("--max-fotos", type=int, default=8); ap.add_argument("--max-mpp", type=float, default=0.05); ap.add_argument("--tol", type=float, default=0.10)
    ap.add_argument("--bild-skala", type=float, default=0.5, help="Fotos fuer die Suche verkleinern (Speicher/Zeit)"); ap.add_argument("--min-schritt", type=float, default=0.003)
    ap.add_argument("--runden", type=int, default=40); a = ap.parse_args(argv); os.makedirs(a.aus, exist_ok=True)
    obj, cams = FO.kameras_laden(a.objekt); spec = json.load(open(a.flaechen)); idx = [i for i, s in enumerate(spec) if s["id"] == a.id]
    if not idx: sys.exit(f"Flaeche {a.id} nicht in {a.flaechen}")
    F0 = spec[idx[0]]; teile0 = FO.flaechen_expandieren([F0])
    # Fotos waehlen: die mit den meisten sichtbaren Zellen der Start-Geometrie (Guete wie im Werkzeug), danach Bilder einmal verkleinert in den Speicher
    gut = {}
    for T in teile0:
        X, N, _ = FO.raster(T, 0.05)
        for nr, (c, pf) in cams.items():
            px, z, C = FO.projektion(X, c); v = C[None, :] - X; dist = np.linalg.norm(v, axis=1); cw = (v * N).sum(1) / np.maximum(dist, 1e-9); mpp = dist / (c["f_px"] * np.maximum(cw, 1e-3))
            ok = (cw > math.cos(math.radians(a.max_winkel))) & (z > 1) & (px[:, 0] >= 0) & (px[:, 0] < 2 * c["cx"]) & (px[:, 1] >= 0) & (px[:, 1] < 2 * c["cy"]) & (mpp < a.max_mpp) & (dist > 0.5)
            gut[nr] = gut.get(nr, 0.0) + float((ok * cw / np.maximum(mpp, 1e-4)).sum())
    wahl = [nr for nr, g in sorted(gut.items(), key=lambda kv: -kv[1])[:a.fotos_max] if g > 0]; cams = {nr: cams[nr] for nr in wahl}; cache = {}
    for nr in wahl:
        im = cv2.imread(cams[nr][1])
        if im is not None: cache[nr] = cv2.resize(im, None, fx=a.bild_skala, fy=a.bild_skala, interpolation=cv2.INTER_AREA)
    print(f"{len(cache)} Fotos (verkleinert {a.bild_skala}) fuer {a.id}", flush=True)
    F = copy.deepcopy(F0); P = parameter(F); start, w0 = bewerten(F, cams, a, cache); beste = start; schritt = {n: s for n, s, _, _ in P}; print(f"  Start: Uneinigkeit {start:.2f} je Teilflaeche {np.round(w0,2).tolist()}", flush=True)
    for runde in range(a.runden):
        besser = False
        for name, _, get, setv in P:
            for vz in (+1, -1):
                F2 = copy.deepcopy(F); setv(F2, get(F2) + vz * schritt[name]); wert, _ = bewerten(F2, cams, a, cache)
                if wert < beste - 1e-4: F, beste, besser = F2, wert, True; print(f"  Runde {runde} {name} {get(F):+.3f} -> {beste:.2f}", flush=True); break
        if not besser:
            schritt = {n: s / 2 for n, s in schritt.items()}
            if max(schritt[n] for n in schritt if n != "winkel0") < a.min_schritt: break
    ende, w1 = bewerten(F, cams, a, cache); print(f"  Ende: Uneinigkeit {ende:.2f} (vorher {start:.2f}), je Teilflaeche {np.round(w1,2).tolist()}")
    # Bilder vorher/nachher in voller Aufloesung (alle Kameras des Objekts nicht noetig: die gewaehlten genuegen)
    a2 = argparse.Namespace(zelle=0.01, max_winkel=a.max_winkel, max_fotos=12, max_mpp=a.max_mpp, tol=a.tol)
    cams_voll = {nr: cams[nr] for nr in wahl}
    for tag, G in (("vorher", F0), ("nachher", F)):
        for T in FO.flaechen_expandieren([G]):
            X, N, r = FO.raster(T, 0.01); img, cnt, _, _ = FO.fusionieren(T, X, N, cams_voll, a2); cv2.imwrite(os.path.join(a.aus, f"ortho_{tag}_{T['id']}.png"), img.reshape(r["nz"], r["nu"], 3))
    G = {k: v for k, v in F.items() if not k.startswith("_")}; spec[idx[0]] = G
    json.dump(spec, open(os.path.join(a.aus, "flaechen_angepasst.json"), "w"), indent=1, ensure_ascii=False)
    json.dump(dict(id=a.id, vorher=start, nachher=ende, parameter_vorher={n: get(F0) for n, _, get, _ in parameter(F0)}, parameter_nachher={n: get(F) for n, _, get, _ in parameter(F)}, fotos=len(cache)),
              open(os.path.join(a.aus, f"bericht_{a.id}.json"), "w"), indent=1)
    print("  " + ", ".join(f"{n}: {get(F0):.3f} -> {get(F):.3f}" for n, _, get, _ in parameter(F0)))


if __name__ == "__main__": main()
