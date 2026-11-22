#!/usr/bin/env python3
"""wand_dicke_tor.py <objekt.json> --seiten <pipe/sfm/seiten_modelle.json> --ausrichtung <messprotokoll/SFM-AUSRICHTUNG-<obj>.json> [--aus audit/wand_dicke.json]

WANDDICKE / TEILVERSATZ JE LoD2-KANTE (22.11.2026, Nulllauf schwabentor-1122f: aus zwei Seitenteilen per Foto-GPS vereint; Ostwand 1-2,5 m ausserhalb LoD2, Westwand
~3 m dick, Treppentuermchen 4-5 m neben LoD2; das Grundriss-Tor sagt nur "durchgefallen", nicht WELCHER Teil WO liegt). Vorlage: Messung des Koordinators
(scratchpad wanddicke.py/teile_lage.py), hier als Kettenwerkzeug:
  1. Jeder vereinte Seitenteil (seiten_modelle.json: 'vereint', Teilmodell + dichte Wolke je Teil) wird EINZELN in den Modellrahmen gelegt: Sim3 Teil-Kamerazentren ->
     Kamerastandorte der Ausrichtung (SFM-AUSRICHTUNG 'kameras'.standort). So misst das Tor die geschriebene Lage, unabhaengig davon, wie die Teile vereint wurden.
  2. Je Kante (>= MIN_KANTE_M) der LoD2-Grundflaeche des ZIELGEBAEUDES (objekt.json lod2.id; Nachbarhaeuser zaehlen nicht): Wandpunkte im Hoehenband Z_BAND (Wandfuss-
     bereich - LoD2 gilt fuer den Wandfuss, nicht fuer Vordach/Erker/Ueberstaende), hoechstens ABSTAND_M von der Kante, innerhalb der Kantenlaenge (0,5 m Rand).
     Vorzeichenbehafteter Normalabstand (+ = aussen). Je Teil: Lage = Median, Dicke = P90 - P10; je Kante: Lageunterschied der Teile (max - min der Mediane) und
     Dicke aller Teile zusammen.
  3. Urteil je Kante: 'doppelwand' (Dicke gesamt > DICKE_MAX_M und Lageunterschied > VERSATZ_MAX_M), 'dick' (Dicke > DICKE_MAX_M, ein Teil oder Teile einig - Ursache im
     Teil selbst: zweite Wand/Durchfahrt oder Geister), 'versetzt' (Lageunterschied > VERSATZ_MAX_M), 'ok', 'kein_urteil' (< MIN_PUNKTE je Teil = zu wenig Wandbeleg).
Ausgabe JSON (kanten[], teile{}, urteil, rc). rc 0 = keine Kante doppelwand/versetzt, 3 = mindestens eine, 2 = nicht messbar (keine Seitenteile, kein LoD2, keine Kameras).
MESSWERKZEUG, KEIN ABBRUCH in der Kette (gesamtkette ruft es mit ok=(0, 2, 3) und schreibt nur die Zahlen).
GRENZEN (ANNAHMEN): DICKE_MAX_M 1,2 m und VERSATZ_MAX_M 0,5 m aus der Vorlage gesetzt, NOCH NICHT aus einem guten Kontrollobjekt abgeleitet (schwabentor-1120 besteht das
  Grundriss-Tor - dort messen und hier eintragen). Z_BAND im Modellrahmen (Boden ~0 = DGM); nur Teile mit eigenen Kameras in der Ausrichtung.
Test: tools/test_wand_dicke_tor.py. Python: /media/oem/scan/venv-colmap/bin/python -I (pycolmap)."""
import os, sys, json, argparse
import numpy as np

T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
Z_BAND = (1.5, 9.0)      # ANNAHME (Vorlage): Wandfuss-Band in Metern ueber dem Modellboden
ABSTAND_M = 3.0          # ANNAHME (Vorlage): Wandpunkte hoechstens 3 m von der LoD2-Kante
MIN_KANTE_M = 4.0        # kuerzere Kanten (Rundungen, Versaetze) nicht werten
MIN_PUNKTE = 200         # ANNAHME: weniger Wandpunkte eines Teils an einer Kante = kein Urteil fuer diesen Teil
DICKE_MAX_M = 1.2        # ANNAHME (Vorlage, nicht aus Kontrollobjekt abgeleitet)
VERSATZ_MAX_M = 0.5      # ANNAHME (Vorlage, nicht aus Kontrollobjekt abgeleitet)
N_MAX = 600000           # Punkte je Teil (feste Zufallsauswahl)


def sim3_fit(X, Y):
    mx, my = X.mean(0), Y.mean(0); U, S, Vt = np.linalg.svd((Y - my).T @ (X - mx)); D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(U @ Vt)); R = U @ D @ Vt
    s = float((S * np.diag(D)).sum() / max(((X - mx) ** 2).sum(), 1e-18)); M = np.eye(4); M[:3, :3] = s * R; M[:3, 3] = my - s * R @ mx; return M


def kanten_messen(grundflaeche, teile, z_band=Z_BAND, abstand=ABSTAND_M, min_kante=MIN_KANTE_M, min_punkte=MIN_PUNKTE):
    """grundflaeche = Ecken (n x 2) der Zielgebaeude-Grundflaeche, teile = {Name: Punkte n x 3 im Modellrahmen}. -> Liste je Kante (dict)."""
    g = np.asarray(grundflaeche, float); c = g.mean(0); L_ = []
    for p0, p1 in zip(g, np.roll(g, -1, 0)):
        L = float(np.linalg.norm(p1 - p0))
        if L < min_kante: continue
        e = (p1 - p0) / L; n = np.array([e[1], -e[0]]); n = n if (p0 - c) @ n > 0 else -n
        k = dict(von=np.round(p0, 2).tolist(), bis=np.round(p1, 2).tolist(), laenge_m=round(L, 2), teile={}); alle = []
        for name, P in teile.items():
            P = np.asarray(P, float); w = (P[:, 2] > z_band[0]) & (P[:, 2] < z_band[1]); q = P[w, :2] - p0; s = q @ e; d = q @ n; m = (s > 0.5) & (s < L - 0.5) & (np.abs(d) < abstand)
            if m.sum() < min_punkte: k["teile"][str(name)] = dict(n=int(m.sum()), urteil="kein_urteil"); continue
            k["teile"][str(name)] = dict(n=int(m.sum()), lage_m=round(float(np.median(d[m])), 3), dicke_m=round(float(np.percentile(d[m], 90) - np.percentile(d[m], 10)), 3)); alle.append(d[m])
        gueltig = [v for v in k["teile"].values() if "lage_m" in v]
        if not gueltig: k["urteil"] = "kein_urteil"; L_.append(k); continue
        D = np.concatenate(alle); k["dicke_gesamt_m"] = round(float(np.percentile(D, 90) - np.percentile(D, 10)), 3); k["lage_gesamt_m"] = round(float(np.median(D)), 3)
        k["lageunterschied_m"] = round(max(v["lage_m"] for v in gueltig) - min(v["lage_m"] for v in gueltig), 3) if len(gueltig) > 1 else None
        dick = k["dicke_gesamt_m"] > DICKE_MAX_M; vers = (k["lageunterschied_m"] or 0) > VERSATZ_MAX_M
        k["urteil"] = "doppelwand" if dick and vers else ("versetzt" if vers else ("dick" if dick else "ok")); L_.append(k)
    return L_


def zusammenfassen(kanten):
    """-> (rc, urteil) aus den Kanten-Urteilen."""
    schlecht = [k for k in kanten if k["urteil"] in ("doppelwand", "versetzt")]; gemessen = [k for k in kanten if k["urteil"] != "kein_urteil"]
    if not gemessen: return 2, "keine Kante mit genug Wandbeleg - kein Urteil"
    if schlecht: return 3, "; ".join(f"Kante {k['von']}->{k['bis']}: {k['urteil']} (Dicke {k['dicke_gesamt_m']} m, Teile {k['lageunterschied_m']} m auseinander)" for k in schlecht)
    dick = [k for k in gemessen if k["urteil"] == "dick"]
    return 0, f"{len(gemessen)} Kanten gemessen, keine Doppelwand" + (f"; {len(dick)} Kante(n) dick in sich (Teil selbst: zweite Wand oder Geister)" if dick else "")


def teile_laden(sm, au, n_max=N_MAX):
    """seiten_modelle.json + SFM-AUSRICHTUNG -> ({Teil: Punkte im Modellrahmen}, {Teil: Info}) - je Teil Sim3 aus den eigenen Kameras."""
    import pycolmap
    from sfm_seiten_modelle import ply_kopf, PLY_SATZ
    st = {k: np.asarray(v["standort"], float) for k, v in (au.get("kameras") or {}).items() if v.get("standort") is not None}; P, I = {}, {}
    for e in sm.get("teile", []):
        if e.get("teil") not in (sm.get("vereint") or []) or not e.get("modell"): continue
        fu = (e.get("dicht") or {}).get("fused"); r = pycolmap.Reconstruction(e["modell"]); X, Y = [], []
        for im in r.images.values():
            nm = os.path.splitext(im.name)[0]
            if im.has_pose and (nm in st or im.name in st): X.append(im.projection_center()); Y.append(st.get(nm, st.get(im.name)))
        if len(X) < 5 or not fu or ply_kopf(fu)[0] <= 0: I[str(e["teil"])] = dict(grund=f"{len(X)} Kameras in der Ausrichtung, dichte Wolke {'da' if fu else 'fehlt'}"); continue
        X, Y = np.array(X), np.array(Y); M = sim3_fit(X, Y); rest = np.linalg.norm(X @ M[:3, :3].T + M[:3, 3] - Y, axis=1)
        n, h, _ = ply_kopf(fu); f = open(fu, "rb"); f.seek(h); d = np.frombuffer(f.read(n * 27), PLY_SATZ)["p"]
        idx = np.random.default_rng(0).choice(n, min(n, n_max), replace=False); P[str(e["teil"])] = d[idx].astype(float) @ M[:3, :3].T + M[:3, 3]
        I[str(e["teil"])] = dict(kameras=len(X), rest_median_m=round(float(np.median(rest)), 3), punkte=int(len(idx)))
    return P, I


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0]); ap.add_argument("objekt"); ap.add_argument("--seiten", required=True); ap.add_argument("--ausrichtung", required=True); ap.add_argument("--aus")
    a = ap.parse_args(argv); aus = a.aus or os.path.join(os.path.dirname(os.path.abspath(a.objekt)), "audit", "wand_dicke.json"); erg = dict(werkzeug="wand_dicke_tor.py", grenzen=dict(dicke_max_m=DICKE_MAX_M, versatz_max_m=VERSATZ_MAX_M, z_band=Z_BAND, abstand_m=ABSTAND_M, herkunft="ANNAHME (Vorlage 1122f), nicht aus Kontrollobjekt abgeleitet"))
    def ende(rc, urteil):
        erg.update(rc=rc, urteil=urteil); os.makedirs(os.path.dirname(aus), exist_ok=True); json.dump(erg, open(aus, "w"), indent=1, ensure_ascii=False)
        for k in erg.get("kanten", []): print(f"Kante {k['von']}->{k['bis']} ({k['laenge_m']} m): {k['urteil']}" + (f", Dicke {k.get('dicke_gesamt_m')} m, Teile {k.get('lageunterschied_m')} m auseinander" if "dicke_gesamt_m" in k else "") + " | " + "; ".join(f"Teil {t}: " + (f"Lage {v['lage_m']:+.2f} m, Dicke {v['dicke_m']:.2f} m" if "lage_m" in v else f"{v['n']} Pkt") for t, v in k["teile"].items()))
        print(("WANDDICKE: " if rc == 0 else "ACHTUNG WANDDICKE: ") + urteil); return rc
    try: sm = json.load(open(a.seiten)); au = json.load(open(a.ausrichtung)); obj = json.load(open(a.objekt))
    except Exception as ex: return ende(2, f"Eingabe fehlt ({type(ex).__name__}: {ex})")
    if (sm.get("ergebnis") or {}).get("art") != "vereint" or len(sm.get("vereint") or []) < 2: return ende(2, "keine vereinten Seitenteile - nichts zu messen")
    zid = (obj.get("lod2") or {}).get("id")
    if not zid: return ende(2, "objekt.json ohne lod2.id - Zielgebaeude unbekannt")
    import wolke_grundriss_pruefen as WG
    gf = [g for b in WG.grundrisse(obj, 60.0) if b["id"] == zid for g in b["ground"]]
    if not gf: return ende(2, f"LoD2-Grundflaeche von {zid} nicht gefunden")
    P, I = teile_laden(sm, au); erg["teile"] = I
    if len(P) < 1: return ende(2, "kein Teil in den Modellrahmen gelegt: " + json.dumps(I, ensure_ascii=False))
    erg["kanten"] = [k for g in gf for k in kanten_messen(g, P)]; rc, u = zusammenfassen(erg["kanten"]); return ende(rc, u)


if __name__ == "__main__": sys.exit(main())
