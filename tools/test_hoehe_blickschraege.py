#!/usr/bin/env python3
"""test_hoehe_blickschraege.py - HOEHEN waagerechter Fensterkanten aus der senkrechten Blickschraege (laibung_aus_fotos.hoehe_messen, 27.11.2026).

Verwandt/Vorlaeufer: tools/test_nische_annahme.py (Nischentiefe aus Schraegfotos), tools/test_sohlbank.py (sohlbank_aus_fotos, gleiche Gerade senkrecht),
tools/test_nischen_fenster.py (Umriss aus dem Wandbild), tools/foto_mass.py --tri (Gegenprobe am Echtfoto).
Befund (Handvergleich Kette 1122zm 'rundbogenfenster' FALSCH, Schwabentor f00; Foto IMG_20261106_113205/113130, M-eigen__IMG_20261106_113205-001..-006):
  - Sohle (Nischengrund auf der Sohlbank) im Foto trianguliert 23,57-23,58 m, Kette 23,36-23,39: das Wandbild liegt auf der Messflaeche w = -0,36, die Putzwand
    im Fensterbereich aber bei -0,52..-0,56 (Wolke, Triangulation) -> Fotos von unten zeigen jede Kante (Ebenenfehler) x kappa tiefer.
  - Fensterscheitel im Foto 25,33-25,38 m, Kette 24,96/24,90: nischen_fenster nahm die Oberkante des dunklen LADENS (0,7 m tief, staerkste Kante im
    fusionierten Wandbild); die Vorderkante der Sturzlaibung ist im Wandbild verschmiert, im Einzelfoto scharf.
Erwartung (synthetisch, eigene Masse; Felder wie foto_feld sie liefert: Zeilen z absteigend, Abtastebene s = -0,36; 14 Kameras 18-70 m, Hoehe 1,5 m):
  A Sohle 23,55 m, Kante 0,55 m hinter der Fassadenebene: hoehe_messen -> 23,55 +- 0,02, Tiefe 0,55 +- 0,05; uebernommen in nische.z0 und Fenster-z0
    (Wandbild-Wert stand 23,45 = ROT ohne Messung).
  B Scheitel, Vorderkante (Nischenflaeche 0,62) kontrastreich, Laden 1,04 m dahinter: -> 25,40 +- 0,02; Fenster z1/bogen.scheitel, Kaempfer wandert mit (rund: z1 - b/2).
  B2 Laden-Kante staerker als die Vorderkante: Steigung 1,04 passt nicht zur Wandflaeche -> 'fehler', KEINE Aenderung (nie ein falscher Wert).
  C Nischenscheitel 25,95 (Kante 0,50 tief) -> 25,95 +- 0,02, Nischen-Kaempfer wandert mit.
  D sohlbank_aus_fotos.zone_von sucht im Wandbild-Rahmen (nische.z0_ortho), nicht auf der wahren Hoehe.
  E nur 2 Fotos -> 'fehler', nichts geaendert.
< 10 s, nur CPU. Rote Probe: --alt = Stand vor dem Fix (keine Hoehenmessung, zone_von mit nische.z0) muss A, B, C, D ROT zeigen.
"""
import sys, os, copy, argparse, numpy as np
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import laibung_aus_fotos as LA
import sohlbank_aus_fotos as SB

ALT = "--alt" in sys.argv
C = 0.01; S_REF = -0.36; F = 0
A_ARGS = argparse.Namespace(min_fotos=3, k_spanne=0.1, staerke_rel=0.4)


def pruef(ok, text):
    global F
    print(("  ok     " if ok else "  FEHLER ") + text)
    if not ok: F += 1


def kameras(n=14):
    rng = np.random.default_rng(3); K = {}
    for i, (cw, cu) in enumerate(zip(np.linspace(18, 70, n), rng.uniform(-6, 6, n))): K[f"k{i:02d}"] = (float(cu), float(cw), 1.5)
    return K


def z_obs(K, z, T):
    """Hoehe, in der eine Kante (Hoehe z, T hinter w = 0) auf der Abtastebene w = S_REF erscheint (Strahl Kamera -> Kante)."""
    _, Cw, Cz = K; return Cz + (z - Cz) * (Cw - S_REF) / (Cw + T)


def feld(za, ze, stufen, seed, breite=0.3):
    """Feld (Zeilen z absteigend von ze) mit Grauwerten je Hoehenstufe: stufen = [(z_ab, wert), ...] aufsteigend (Wert gilt ab z_ab nach oben)."""
    rng = np.random.default_rng(seed); zz = ze - C * (np.arange(int(round((ze - za) / C))) + 0.5)
    g = np.full(len(zz), float(stufen[0][1]))
    for z_ab, w in stufen: g[zz >= z_ab] = w
    from scipy import ndimage as ndi
    G = np.repeat(g[:, None], int(breite / C), axis=1) + rng.normal(0, 3.0, (len(zz), int(breite / C)))
    return np.clip(ndi.gaussian_filter(G, 0.8), 1, 255).astype(np.uint8)


def felder(KK, za, ze, stufen_fn):
    return {k: (feld(za, ze, stufen_fn(K), i), 0.0, S_REF, za) for i, (k, K) in enumerate(KK.items())}


def fenster():
    """Rundbogenfenster 0,68 m in Rundbogennische 2,10 m, Werte wie das Wandbild sie liefert (zu tief)."""
    return dict(u0=-0.34, u1=0.34, z0=23.45, z1=24.96, bogen=dict(form="rund", kaempfer=24.62, scheitel=24.96), laibung=dict(tiefe_ab_wand=1.04),
                nische=dict(u0=-1.05, u1=1.05, z0=23.40, z1=25.88, bogen=dict(form="rund", kaempfer=24.83, scheitel=25.88)))


def main():
    KK = kameras(); q = fenster(); s_w = 0.36
    # A Sohle: helle Nische ueber dunkler Bank, Kante 23,55 / 0,55 m
    fA = felder(KK, 23.10, 23.70, lambda K: [(0, 70), (z_obs(K, 23.55, 0.55), 205)])
    # B Scheitel: Laden (70) bis zur Hinterkante, Sturzlaibung (130), dunkler Schattenstrich (60), Nischenflaeche (215) ab der Vorderkante
    fB = felder(KK, 24.40, 25.70, lambda K: [(0, 70), (z_obs(K, 25.40, 1.04), 130), (z_obs(K, 25.40, 0.62) - 0.02, 60), (z_obs(K, 25.40, 0.62), 215)])
    fB2 = felder(KK, 24.40, 25.70, lambda K: [(0, 40), (z_obs(K, 25.40, 1.04), 220), (z_obs(K, 25.40, 0.62) - 0.02, 175), (z_obs(K, 25.40, 0.62), 205)])
    fC = felder(KK, 25.58, 26.18, lambda K: [(0, 90), (z_obs(K, 25.95, 0.50), 210)])
    FQ = dict(sohle=fA, scheitel=fB, nische_scheitel=fC)

    print("A/B/C: Hoehen aus der senkrechten Blickschraege (Wandbild: Sohle 23,40/23,45, Scheitel 24,96, Nischenscheitel 25,88)")
    q1 = copy.deepcopy(q)
    if not ALT: LA.hoehen_fenster(q1, FQ, KK, C, A_ARGS, s_w)
    hf = q1.get("hoehen_fotos") or {}
    pruef(abs(q1["nische"]["z0"] - 23.55) <= 0.02 and abs(q1["z0"] - 23.55) <= 0.02, f"A Sohle: Nische z0 {q1['nische']['z0']}, Fenster z0 {q1['z0']} (Soll 23,55 +- 0,02)")
    pruef(abs(((hf.get("sohle") or {}).get("tiefe") or 0) - 0.55) <= 0.05, f"A Tiefe der Sohlkante {(hf.get('sohle') or {}).get('tiefe')} (Soll 0,55 +- 0,05)")
    pruef(abs(q1["z1"] - 25.40) <= 0.02 and abs(q1["bogen"]["scheitel"] - 25.40) <= 0.02, f"B Scheitel {q1['z1']} / bogen {q1['bogen']['scheitel']} (Soll 25,40 +- 0,02)")
    pruef(abs(q1["bogen"]["kaempfer"] - (q1["z1"] - 0.34)) <= 0.005, f"B rund bleibt rund: Kaempfer {q1['bogen']['kaempfer']} = Scheitel - 0,34")
    N = q1["nische"]
    pruef(abs(N["z1"] - 25.95) <= 0.02 and abs(N["bogen"]["kaempfer"] - (N["z1"] - 1.05)) <= 0.005, f"C Nischenscheitel {N['z1']}, Kaempfer {N['bogen']['kaempfer']} (Soll 25,95 / 24,90)")

    print("B2: Laden-Kante staerker als die Vorderkante -> kein Mass statt falschem Mass")
    q2 = copy.deepcopy(q); H2, L2 = LA.hoehen_fenster(q2, dict(scheitel=fB2), KK, C, A_ARGS, s_w)
    pruef("scheitel" not in H2 and q2["z1"] == 24.96, f"B2 Scheitel unveraendert {q2['z1']} ({[h.get('fehler', '')[:70] for h in L2]})")

    print("D: Sohlbank-Suche im Wandbild-Rahmen")
    zone_alt = lambda q_: (float((q_.get("nische") or q_)["u0"]), float((q_.get("nische") or q_)["u1"]), float((q_.get("nische") or q_)["z0"]), float(q_["u0"]), float(q_["u1"]))
    qd = copy.deepcopy(q); qd["nische"].update(z0=23.55, z0_ortho=23.40)      # Zustand nach hoehen_anwenden (fest, unabhaengig von A)
    zv = (zone_alt if ALT else SB.zone_von)(qd)
    pruef(abs(zv[2] - 23.40) <= 1e-6, f"D zone_von z_unten {zv[2]} (Soll Wandbild-Wert 23,40, nicht die wahre Hoehe 23,55)")

    print("E: zu wenige Fotos")
    q3 = copy.deepcopy(q); K2 = dict(list(KK.items())[:2]); H3, L3 = LA.hoehen_fenster(q3, dict(sohle={k: fA[k] for k in K2}), K2, C, A_ARGS, s_w)
    pruef(not H3 and q3["nische"]["z0"] == 23.40, f"E 2 Fotos: nichts geaendert ({[h.get('fehler', '')[:50] for h in L3]})")
    print(f"{'ALT (rote Probe)' if ALT else 'NEU'}: {F} Fehler")
    return 1 if F else 0


if __name__ == "__main__": sys.exit(main())
