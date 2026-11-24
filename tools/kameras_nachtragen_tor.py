#!/usr/bin/env python3
"""kameras_nachtragen_tor.py <objekt.json> [--fassaden <fassaden.json>] [--min-sicht 0.1] - GUELTIGKEITS-TOR fuer nachgetragene Kameras (Stufe seiten).

Anlass 23.11.2026 (Kette 1122q, schwabentor-1122): tools/kameras_nachtragen.py trug 327 nachregistrierte Fotos als K-Dateien ein, Bericht 'gegenprobe': 0.
'gegenprobe' prueft aber nur Fotos, die SCHON eine K-Datei hatten (Standortunterschied > 1 m) - die 327 NEUEN hatte niemand geprueft. Am Bestand: 38 Standorte
unplausibel (bis 119 m unter dem Gelaende, Regel tools/kamera_plausibel.py), nur 85 am Modell nachgezogen ('vertrauen', tools/kamera_verfeinern.py); der Rest
waere als reine SfM-Pose in fassade_ortho gegangen (Namensregel dl_/neu__ griff nicht mehr, Sammelordner-Praefixe eigen__/commons_...).
Regel je NEUER Kamera (audit/kameras_nachtragen.json 'neu'):
  1. Standort/Brennweite/Verzeichnung plausibel (kamera_plausibel.datei_pruefen) - sonst GESPERRT 'unplausibel';
  2. am Modell belegt ('vertrauen' aus kamera_verfeinern.py: >= 2 Waende mit >= 15 Inliern, Rest/Abstand plausibel) - sonst GESPERRT 'unbelegt';
  3. (24.11.2026, Kette 1122zb) Standort NICHT im Gebaeude (im_gebaeude) - sonst GESPERRT 'unplausibel'; dasselbe fuer vorhandene ABGELEITETE Kameras (Altbestand,
     auch allein mit --altbestand vor kameras_nachtragen).
  Gesperrt = der Zustand VOR dem Nachtragen: K-Datei ohne eigene Picks -> umbenannt in K-<foto>.json.unplausibel bzw. .unbelegt (kein Werkzeug liest sie, nichts geloescht;
  ein spaeteres kamera_verfeinern kann das Foto ohne Startpose neu bestimmen); K-Datei mit Picks/Linien -> nur 'kamera' entfernt (als 'kamera_gesperrt' behalten).
Zusaetzlich je Wand aus --fassaden (fassaden.json von fassade_ortho; ohne Angabe keine Wandliste): wie viele BELEGTE neue Kameras
die Wand sehen (Anteil >= --min-sicht einer Stichprobe der Wandflaeche im Bild, Blickwinkel <= 70 Grad, <= 6 cm/px wie fassade_ortho, Regel kamera_plausibel.messkamera).
Das ist die Vorab-Schaetzung, ob ein Wiederholen von Wandbild/Bau lohnt (tools/seiten_wiederholung.py misst danach am neuen Wandbild).
Ausgabe audit/kameras_nachtragen_tor.json {belegt: [..], gesperrt: [{foto, grund}], waende: [{nr, id, neu_sicht, fotos}]}. Exit 0 = mindestens eine belegte Kamera,
3 = keine (alles gesperrt oder nichts nachgetragen), 2 = kein Bericht audit/kameras_nachtragen.json.
Umgebung: numpy/cv2 -> /media/oem/scan/venv-seg/bin/python -I (oder tools/py). Letzter Schritt des Nachhol-Skripts von tools/seiten_luecken.py.
"""
import sys, os, json, math, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kamera_plausibel as KP

PICK_SCHLUESSEL = ("punkte", "linien")


def urteil(k):
    """-> (belegt, grund) fuer eine K-'kamera' (nach kamera_verfeinern). Grund leer = belegt."""
    if not isinstance(k, dict) or "rvec" not in k: return False, "keine Kamera in der K-Datei"
    if not k.get("vertrauen"): return False, "unbelegt: nicht am Modell nachgezogen (kamera_verfeinern rc 3 oder nicht gelaufen) - reine SfM-Pose"
    if k.get("tiefe_unsicher"): return False, "unbelegt: tiefe_unsicher"
    return True, ""


def sperren(kp, grund, art):
    """K-Datei <kp> auf den Zustand vor dem Nachtragen setzen. art 'unplausibel'/'unbelegt'. Rueckgabe: was geschah."""
    d = json.load(open(kp))
    if any(d.get(s_) for s_ in PICK_SCHLUESSEL):                     # eigene Picks/Linien bleiben lesbar - nur die Kamera faellt weg
        d["kamera_gesperrt"] = dict(d.pop("kamera"), sperre=grund)
        if isinstance(d.get("kamera_vorher"), dict) and "rvec" in d["kamera_vorher"] and KP.messkamera("", d["kamera_vorher"], False): d["kamera"] = d.pop("kamera_vorher")
        __import__("json_sicher").schreiben(kp, d); return "kamera entfernt (Picks bleiben)"
    ziel = kp + "." + art
    if os.path.exists(ziel): os.remove(ziel)                         # Sperrvermerk eines frueheren Laufs fuer dasselbe Foto (eigene Ausgabe dieses Tors)
    os.rename(kp, ziel); return "umbenannt -> " + os.path.basename(ziel)


def sicht_anteil(k, F, max_winkel=70.0, max_mpp=0.06, n_u=12, n_z=24):
    """Anteil einer Stichprobe der Wand F (fassaden.json: n, d, o, u, z) im Bild der Kamera k - wie die Kamera-Vorauswahl von fassade_ortho (ohne Verdeckung)."""
    import cv2
    n, d, o = np.asarray(F["n"], float), np.asarray(F["d"], float), np.asarray(F["o"], float)
    U, Z = np.meshgrid(np.linspace(F["u"][0], F["u"][1], n_u), np.linspace(F["z"][0], F["z"][1], n_z))
    X = np.c_[o[0] + U.ravel() * d[0], o[1] + U.ravel() * d[1], Z.ravel()]
    R = cv2.Rodrigues(np.asarray(k["rvec"], float))[0]; t = np.asarray(k["t"], float); C = -R.T @ t
    v = C - X; dd = np.linalg.norm(v, axis=1)
    if not np.isfinite(dd).all() or dd.max() > 2000 or dd.min() < 0.5: return 0.0
    cw = (v @ np.r_[n, 0.0]) / dd; pc = X @ R.T + t; z = np.maximum(pc[:, 2], 1e-6)
    u = k["f_px"] * pc[:, 0] / z + k["cx"]; w = k["f_px"] * pc[:, 1] / z + k["cy"]
    ok = (cw > math.cos(math.radians(max_winkel))) & (pc[:, 2] > 1) & (u > 0) & (u < 2 * k["cx"]) & (w > 0) & (w < 2 * k["cy"]) & (dd / (k["f_px"] * np.maximum(cw, 1e-3)) < max_mpp)
    return float(ok.mean())


def im_gebaeude(k, FF, rand=0.3):
    """24.11.2026 (Kette 1122zb): 21 nachgetragene Kameras lagen nach einer gekippten Abbildung (kameras_nachtragen, Massstab 0,0017) im Turm [1,4 14,0 2,1], bestanden
    kamera_verfeinern ('vertrauen') und sahen keine Wand. Regel: Standort HINTER JEDER Wandebene (n zeigt nach aussen, wie sicht_anteil) um > <rand> m UND unter der
    hoechsten Wandoberkante = im Gebaeude. Hinreichend, nicht notwendig (auch bei einspringenden Grundrissen liegt der Schnitt aller Innen-Halbraeume im Gebaeude);
    Drohnen-/Hochblick ueber dem Dach bleibt erlaubt. FF = fassaden.json 'fassaden'. -> bool."""
    import cv2
    if not FF or not isinstance(k, dict) or "rvec" not in k: return False
    C = -cv2.Rodrigues(np.asarray(k["rvec"], float))[0].T @ np.asarray(k["t"], float)
    if not np.isfinite(C).all(): return False
    hinter = all(float(np.dot(np.asarray(F["n"], float)[:2], C[:2] - np.asarray(F["o"], float)[:2])) < -rand for F in FF)
    return bool(hinter and C[2] < max(float(F["z"][1]) for F in FF))


def altbestand_sperren(mp, FF, ausser, schreiben=True):
    """Bereits vorhandene ABGELEITETE Kameras (kamera_rahmen.abgeleitet: nachregistriert/kamera_verfeinern) im Gebaeude sperren - kameras_nachtragen ueberschreibt
    vorhandene K-Dateien nie, ein frueherer Fehllauf (1122zb) bliebe sonst fuer immer 'belegt'. Danach bestimmt das naechste Nachholen das Foto neu. -> Liste."""
    import glob, kamera_rahmen as KR
    aus = []
    for kp in sorted(glob.glob(os.path.join(mp, "K-*.json"))):
        n_ = os.path.basename(kp)[2:-5]
        if n_ in ausser: continue
        try: k = json.load(open(kp)).get("kamera")
        except Exception: continue
        if KR.abgeleitet(k) and im_gebaeude(k, FF):
            g_ = "unplausibel: Standort im Gebaeude (Altbestand, abgeleitete Kamera)"; aus.append(dict(foto=n_, grund=g_, aktion=sperren(kp, g_, "unplausibel") if schreiben else "-"))
    return aus


def pruefen(objekt, fassaden=None, min_sicht=0.1, schreiben=True):
    od = os.path.dirname(os.path.abspath(objekt)); root = os.path.dirname(os.path.dirname(od)); obj = json.load(open(objekt))
    au = os.path.join(root, obj.get("audit", os.path.join(od, "audit"))); mp = os.path.join(od, "messprotokoll"); kn = os.path.join(au, "kameras_nachtragen.json")
    if not os.path.exists(kn): return None
    neu = [e["foto"] for e in json.load(open(kn)).get("neu", [])]
    FF = json.load(open(fassaden))["fassaden"] if fassaden and os.path.exists(fassaden) else []
    belegt, gesperrt, kams = [], [], {}
    for n_ in dict.fromkeys(neu):
        kp = os.path.join(mp, "K-" + n_ + ".json")
        if not os.path.exists(kp):
            alt_ = [s_ for s_ in ("unplausibel", "unbelegt") if os.path.exists(kp + "." + s_)]
            gesperrt.append(dict(foto=n_, grund=("schon gesperrt (" + alt_[0] + ")") if alt_ else "K-Datei fehlt")); continue
        try: d_ = json.load(open(kp))
        except Exception: d_ = {}
        if not (isinstance(d_.get("kamera"), dict) and "rvec" in d_["kamera"]):      # schon gesperrt (Picks-Datei ohne Kamera) oder nie eine Kamera: nichts zu tun
            gesperrt.append(dict(foto=n_, grund="schon gesperrt (kamera_gesperrt)" if d_.get("kamera_gesperrt") else "keine Kamera in der K-Datei")); continue
        try: ok_p, g_p = KP.datei_pruefen(kp)
        except Exception as e: ok_p, g_p = False, f"nicht lesbar ({str(e)[:60]})"
        k = (json.load(open(kp)).get("kamera") if ok_p else None)
        if not ok_p:
            gesperrt.append(dict(foto=n_, grund="unplausibel: " + g_p, aktion=sperren(kp, "unplausibel: " + g_p, "unplausibel") if schreiben else "-")); continue
        ok_b, g_b = urteil(k)
        if not ok_b:
            gesperrt.append(dict(foto=n_, grund=g_b, aktion=sperren(kp, g_b, "unbelegt") if schreiben else "-")); continue
        if im_gebaeude(k, FF):
            g_ = "unplausibel: Standort im Gebaeude (hinter allen Wandebenen, unter der Oberkante)"; gesperrt.append(dict(foto=n_, grund=g_, aktion=sperren(kp, g_, "unplausibel") if schreiben else "-")); continue
        belegt.append(n_); kams[n_] = k
    alt_gesperrt = altbestand_sperren(mp, FF, set(neu), schreiben) if FF else []
    waende = []
    if FF:
        for i, F in enumerate(FF):
            sieht = [n_ for n_, k in kams.items() if KP.messkamera(n_, k, False) and sicht_anteil(k, F) >= min_sicht]
            waende.append(dict(nr=i, id=F.get("id", "f%02d" % i), neu_sicht=len(sieht), fotos=sieht[:40], fotos_vorher=len(F.get("fotos") or {})))
    erg = dict(zeit=__import__("time").strftime("%Y-%m-%d %H:%M"), neu=len(neu), belegt=belegt, gesperrt=gesperrt, altbestand_gesperrt=alt_gesperrt, waende=waende, fassaden=fassaden,
               regel="plausibel (kamera_plausibel) UND am Modell nachgezogen (kamera_verfeinern 'vertrauen'); gesperrt = Zustand vor dem Nachtragen")
    if schreiben: __import__("json_sicher").schreiben(os.path.join(au, "kameras_nachtragen_tor.json"), erg)
    return erg


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--fassaden", default=""); ap.add_argument("--min-sicht", type=float, default=0.1)
    ap.add_argument("--trocken", action="store_true", help="nur Bericht auf stdout, nichts umbenennen/schreiben")
    ap.add_argument("--altbestand", action="store_true", help="NUR vorhandene abgeleitete Kameras im Gebaeude sperren (vor kameras_nachtragen, 24.11.2026), Exit 0"); a = ap.parse_args()
    if a.altbestand:
        od = os.path.dirname(os.path.abspath(a.objekt)); FF = json.load(open(a.fassaden))["fassaden"] if a.fassaden and os.path.exists(a.fassaden) else []
        aus = altbestand_sperren(os.path.join(od, "messprotokoll"), FF, set(), schreiben=not a.trocken) if FF else []
        print(f"ALTBESTAND: {len(aus)} abgeleitete Kamera(s) im Gebaeude gesperrt" + (f" (z. B. {aus[0]['foto']}) - werden jetzt neu nachgetragen" if aus else "") + ("" if FF else " (keine fassaden.json - nicht geprueft)"))
        return 0
    erg = pruefen(a.objekt, a.fassaden or None, a.min_sicht, schreiben=not a.trocken)
    if erg is None: print("kein audit/kameras_nachtragen.json - nichts zu pruefen"); return 2
    from collections import Counter
    print(f"TOR nachgetragene Kameras: {erg['neu']} neu, {len(erg['belegt'])} BELEGT, {len(erg['gesperrt'])} gesperrt ("
          + ", ".join(f"{n} {g}" for g, n in Counter(x["grund"].split(":")[0] for x in erg["gesperrt"]).most_common()) + ")")
    if erg.get("altbestand_gesperrt"): print(f"  Altbestand: {len(erg['altbestand_gesperrt'])} abgeleitete Kamera(s) im Gebaeude gesperrt (z. B. {erg['altbestand_gesperrt'][0]['foto']}) - naechstes Nachholen bestimmt sie neu")
    for w in erg["waende"]: print(f"  Wand {w['id']}: {w['neu_sicht']} belegte neue Kamera(s) sehen sie (vorher {w['fotos_vorher']} Fotos im Wandbild)")
    return 0 if erg["belegt"] else 3


if __name__ == "__main__":
    sys.exit(main())
