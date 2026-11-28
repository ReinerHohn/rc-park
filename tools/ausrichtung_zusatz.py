#!/usr/bin/env python3
"""ausrichtung_zusatz.py - nachregistrierte Zusatzfotos (Handy; tools/zusatzfotos_registrieren.py -> <ordner>/sparse_handy/0) als Kameras in eine
KOPIE der SFM-Ausrichtung haengen, damit die KANTENSTUFE (tools/kantenstufe.py: Stabilkarten + Kanten-Tiefen-Sweep) sie nutzt (2026-11-28).

Anlass 28.11.2026 (schwabentor-1122): 327 Handyfotos vom 26.11. und 72 vom 28.11. waren registriert, gingen aber nur in die dichte Wolke (Lage-Veto) -
die Kantenstufe las nur 'kameras' der SFM-AUSRICHTUNG (903 Bilder des Hauptnetzes) und Bilder aus dem Sammelordner. Kernmethode = Form aus Fotokanten.
Verwandt: tools/zusatz_kameras_lot2.py (gleiche Aufgabe fuer den Kaufhaus-Rahmen kam_lot2, andere Rahmenkette), tools/kameras_nachtragen.py (K-<foto>.json fuer
Foto-Tor/Wandbild/F1), tools/zusatzfotos_registrieren.py (erzeugt sparse_handy/0). Vorlaeufer: keiner - Handykameras gingen nur in die dichte Wolke.

Rahmen: zusatzfotos_registrieren veraendert das Referenznetz nicht -> sparse_handy liegt im SfM-Rahmen der Ausrichtung. Dieselbe Formel wie
sfm_lod2_ausrichten.py beim Schreiben (X_sfm = s R X_m + t): Rc = R_cw R, tc = (R_cw t + t_cw) / s. RAHMEN-TOR je Ordner (keine Annahme): die
Referenzbilder, die in sparse_handy UND in der Ausrichtung stehen, muessen nach der Umrechnung auf ihren Ausrichtungs-Kameras liegen (Median
Zentrum <= --tor_m, Median Winkel <= --tor_grad, mindestens --min_gemeinsam); sonst wird der Ordner NICHT verwendet (Grund im Bericht).
Bilder: die Pose gilt fuer das VORBEREITETE Bild <ordner>/bilder/<name> (Skala/Beschnitt aus vorbereitet.json) - genau das wird verlinkt.
Ausgabe: --aus_json (Ausrichtung + neue Kameras, je Kamera quelle='zusatz:<ordner>'), --aus_bilder (Links: alle Bilder aus --fotos + neue Zusatzbilder),
<aus_json>.bericht.json. Die Original-Ausrichtung und der Sammelordner bleiben unveraendert (Fotosatz-Hash der SfM-Stufe unberuehrt).
Namen, die im Sammelordner schon vorkommen, aber nicht in der Ausrichtung stehen, werden uebersprungen (keine Verwechslung).
Exit: 0 = mindestens eine Kamera neu, 3 = keine neue Kamera (Ausgaben trotzdem geschrieben, Kette nimmt dann die Original-Ausrichtung).
  /media/oem/scan/venv-colmap/bin/python -I tools/ausrichtung_zusatz.py --ausrichtung AU.json --fotos FV --zusatz O1 [O2 ...] --aus_json X.json --aus_bilder DIR [--trocken]
Nichts Objektspezifisches. Test: tools/test_ausrichtung_zusatz.py (Schnelltest)."""
import os, sys, json, argparse
import numpy as np

STANDORT_NACHKOMMA = 2


def rot_aus_rvec(r):
    r = np.asarray(r, float); th = float(np.linalg.norm(r))
    if th < 1e-15: return np.eye(3)
    k = r / th; Kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(th) * Kx + (1 - np.cos(th)) * Kx @ Kx


def umrechnen(R_cw, t_cw, T):
    """SfM-Pose (x_cam = R_cw X_sfm + t_cw) -> Pose im Modellrahmen der Ausrichtung (gleiche Formel wie sfm_lod2_ausrichten.py)."""
    s = float(T["s"]); R = rot_aus_rvec(T["rvec"]); t = np.asarray(T["t"], float)
    Rc = R_cw @ R; tc = (R_cw @ t + t_cw) / s
    return Rc, tc


def winkel_grad(Ra, Rb):
    return float(np.degrees(np.arccos(np.clip((np.trace(Ra @ Rb.T) - 1) / 2, -1, 1))))


def rahmen_tor(posen, K, T, tor_m, tor_grad, min_gem):
    """posen: {nr: (R_cw, t_cw)}; K: Ausrichtungs-Kameras. -> (ok, info)."""
    dC, dW = [], []
    for nr, (Rw, tw) in posen.items():
        if nr not in K or "R" not in K[nr]: continue
        Rc, tc = umrechnen(Rw, tw, T); Ra = np.array(K[nr]["R"], float); ta = np.array(K[nr]["t"], float)
        dC.append(float(np.linalg.norm(-Rc.T @ tc + Ra.T @ ta))); dW.append(winkel_grad(Rc, Ra))
    info = dict(gemeinsam=len(dC), zentrum_median_m=round(float(np.median(dC)), 4) if dC else None, winkel_median_grad=round(float(np.median(dW)), 4) if dW else None)
    if len(dC) < min_gem: return False, dict(info, grund=f"nur {len(dC)} gemeinsame Referenzbilder (< {min_gem}) - Rahmen nicht pruefbar")
    if info["zentrum_median_m"] > tor_m or info["winkel_median_grad"] > tor_grad:
        return False, dict(info, grund=f"Referenzbilder weichen ab (Zentrum {info['zentrum_median_m']} m > {tor_m} oder Winkel {info['winkel_median_grad']} Grad > {tor_grad}) - anderes SfM/anderer Rahmen")
    return True, info


def kamera_eintrag(Rc, tc, cam_model, params, w, h, quelle):
    pr = [float(v) for v in params]; pin = cam_model in ("PINHOLE", "OPENCV", "FULL_OPENCV")
    C = -Rc.T @ tc
    return dict(standort=np.round(C, STANDORT_NACHKOMMA).tolist(), f_px_original=pr[0], fak=1.0, off=[0.0, 0.0], R=Rc.tolist(), t=tc.tolist(),
                cx=pr[2] if pin else pr[1], cy=pr[3] if pin else pr[2], k=pr[3:] if cam_model in ("SIMPLE_RADIAL", "RADIAL") else [], bild_b=int(w), bild_h=int(h),
                quelle=quelle, hinweis="f/cx/cy in Pixeln des vorbereiteten Zusatzbildes (ausrichtung_zusatz.py)")


def sparse_lesen(sp):
    """-> {name: (R_cw, t_cw, modell, params, W, H)} aus einem COLMAP-Netz (pycolmap)."""
    import pycolmap
    rec = pycolmap.Reconstruction(sp); out = {}
    for im in rec.images.values():
        cw = im.cam_from_world() if callable(getattr(im, "cam_from_world", None)) else im.cam_from_world
        cam = rec.cameras[im.camera_id]
        out[im.name] = (np.asarray(cw.rotation.matrix(), float), np.asarray(cw.translation, float), cam.model.name, list(cam.params), cam.width, cam.height)
    return out


def erweitern(A, fv_namen, ordner_netze, tor_m=0.05, tor_grad=0.5, min_gem=20):
    """A: Ausrichtung (dict); fv_namen: Dateinamen im Sammelordner; ordner_netze: [(ordner, {name: pose...})].
    -> (A_neu, neu {nr: bildpfad}, bericht). Reine Funktion (Test ohne pycolmap)."""
    K = dict(A["kameras"]); T = A["transformation"]; fv_stamm = {os.path.splitext(f)[0] for f in fv_namen}; neu = {}; bericht = dict(ordner=[])
    for o_, netz in ordner_netze:
        posen = {os.path.splitext(n)[0]: (v[0], v[1]) for n, v in netz.items()}
        ok, info = rahmen_tor(posen, K, T, tor_m, tor_grad, min_gem); e = dict(ordner=o_, rahmen_ok=ok, **info, neu=0, uebersprungen_name=[], ohne_bild=[])
        if ok:
            for n, (Rw, tw, mod, par, w, h) in sorted(netz.items()):
                nr = os.path.splitext(n)[0]
                if nr in K: continue                                         # Referenzbild oder schon aus frueherem Ordner
                if nr in fv_stamm: e["uebersprungen_name"].append(n); continue  # gleicher Name im Sammelordner, aber andere Pose/Bild -> nicht verwechseln
                bp = os.path.join(o_, "bilder", n)
                if not os.path.isfile(bp): e["ohne_bild"].append(n); continue
                Rc, tc = umrechnen(Rw, tw, T); K[nr] = kamera_eintrag(Rc, tc, mod, par, w, h, "zusatz:" + o_); neu[nr] = bp; e["neu"] += 1
        bericht["ordner"].append(e)
    A2 = dict(A); A2["kameras"] = K; A2["fotos_sfm"] = sorted(set(A.get("fotos_sfm") or []) | set(neu))
    A2["zusatz"] = dict(werkzeug="ausrichtung_zusatz.py", ordner=[e["ordner"] for e in bericht["ordner"] if e["rahmen_ok"]], neu=len(neu))
    bericht["neu_gesamt"] = len(neu); bericht["kameras_gesamt"] = len(K)
    return A2, neu, bericht


def links_anlegen(aus_bilder, fv, fv_namen, neu):
    os.makedirs(aus_bilder, exist_ok=True)
    for f in os.listdir(aus_bilder):                                         # nur eigene Links erneuern (Ordner gehoert diesem Werkzeug)
        p = os.path.join(aus_bilder, f)
        if os.path.islink(p): os.unlink(p)
    for f in fv_namen: os.symlink(os.path.realpath(os.path.join(fv, f)), os.path.join(aus_bilder, f))
    for nr, bp in neu.items(): os.symlink(os.path.realpath(bp), os.path.join(aus_bilder, os.path.basename(bp)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ausrichtung", required=True); ap.add_argument("--fotos", required=True); ap.add_argument("--zusatz", nargs="+", required=True)
    ap.add_argument("--aus_json", required=True); ap.add_argument("--aus_bilder", required=True); ap.add_argument("--trocken", action="store_true")
    ap.add_argument("--tor_m", type=float, default=0.05); ap.add_argument("--tor_grad", type=float, default=0.5); ap.add_argument("--min_gemeinsam", type=int, default=20)
    a = ap.parse_args(argv)
    A = json.load(open(a.ausrichtung)); fv_namen = sorted(f for f in os.listdir(a.fotos) if not f.startswith("."))
    netze = []
    for o_ in a.zusatz:
        sp = os.path.join(o_, "sparse_handy", "0")
        if not os.path.isfile(os.path.join(sp, "images.bin")): print(f"WARNUNG: {sp} fehlt - Ordner uebersprungen", flush=True); continue
        netze.append((o_, sparse_lesen(sp)))
    A2, neu, ber = erweitern(A, fv_namen, netze, a.tor_m, a.tor_grad, a.min_gemeinsam)
    for e in ber["ordner"]:
        print(f"{e['ordner']}: Rahmen {'OK' if e['rahmen_ok'] else 'ABGELEHNT'} (gemeinsam {e['gemeinsam']}, Zentrum {e['zentrum_median_m']} m, Winkel {e['winkel_median_grad']} Grad)"
              f" neu {e['neu']}, Name belegt {len(e['uebersprungen_name'])}, ohne Bild {len(e['ohne_bild'])}" + (f" - {e['grund']}" if e.get("grund") else ""), flush=True)
    print(f"Kameras {len(A['kameras'])} -> {len(A2['kameras'])} (+{len(neu)})", flush=True)
    if a.trocken: print("TROCKEN: nichts geschrieben", flush=True); return 0 if neu else 3
    os.makedirs(os.path.dirname(os.path.abspath(a.aus_json)), exist_ok=True)
    tmp = a.aus_json + ".tmp"; json.dump(A2, open(tmp, "w")); os.replace(tmp, a.aus_json)
    json.dump(ber, open(a.aus_json + ".bericht.json", "w"), indent=1, ensure_ascii=False)
    links_anlegen(a.aus_bilder, a.fotos, fv_namen, neu)
    return 0 if neu else 3


if __name__ == "__main__":
    sys.exit(main())
