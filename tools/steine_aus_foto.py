#!/usr/bin/env python3
"""steine_aus_foto.py <relief.npz> <aus.npz> <fassaden.json> <nr> <ortho_fein.png> --feld u0 u1 z0 z1 [--px 0.02] [--fuge 0.03] [--massstab k x y z]

Quader mit ECHTEN Fugen aus dem feinen Fassadenbild (Nutzer 16.11.2026: "die Steine sind nach oben noch nicht korrekt").
Weiter oben am Turm ist das Scan-Relief nur noch Brei (Fotos von unten, flacher Winkel) - im 1-cm-Fassadenbild (tools/fassade_fein.py) steht aber jede Fuge
scharf. KERNMETHODE: Form aus Fotokanten. Ablauf:
  1. Feld (Wandkoordinaten des Reliefs) im 1-cm-Raster aus dem Fassadenbild lesen (Lage ueber fassaden.json: o, d, raster).
  2. FUGEN = schmale Linien, die von ihrer Umgebung abweichen: Helligkeit minus oertlicher Median (15 cm). Polaritaet (helle Moertelfuge / dunkle
     Schattenfuge) wird NICHT vorgegeben: beide Masken, es gewinnt die mit mehr langen duennen Linien. Keine Farbregel (gruenes/gelbes Haus geht genauso).
  2b. QUADER-TOR (--tor, 17.11.2026): nur wenn das Bild wirklich ein Fugenraster zeigt (durchlaufende Lagerfugen in regelmaessigem Abstand), sonst rc 5 und keine Datei.
  3. Steine = Flaechen zwischen den Fugen, nur wo das Relief Stein ist (Maske 'putz' von relief_putz.py = Putz; Kontur damit aus der Fotofarbe wie bisher).
  4. Hoehe: Steinflaeche = geglaettetes Scan-Relief (echtes Niveau, 30 cm Glaettung), Fuge --fuge tiefer, Kante ueber 3 cm gefast.
     Putz = Putzniveau. Stellen ohne Fotodaten (verdeckt) = Scan-Relief.
aus.npz hat das Format der Relief-Einsaetze (px 2 cm, Maske 'fein' = alles) und wird wie ein Feineinsatz vor das grobe Relief gesetzt
(Generator: relief_koerper(aus, rand_auslauf=False), grobes Relief dort tief_felder). aus.jpg ANSEHEN. Fugentiefe und Bosse sind ANNAHME, die Fugenlage ist echt.
Weitere Optionen: --ohne u0 u1 z0 z1 (mehrfach), --tor 0.12, --schwelle 2.4, --foto/--objekt/--stl/--streng/--gegenfoto (Feld direkt aus Fotos),
--paar 0.3 (21.11.2026 Paar-Probe: Haupt- und Gegenfoto, die fast nirgends uebereinstimmen, haben eine falsche Kamera - naechstes Foto statt die Wand als "Verdecker" zu loeschen).
Ausgaben: <aus.npz> + <aus>.jpg (Fassadenbild | Steinbild). Umgebung: cv2 -> /media/oem/scan/venv-seg/bin/python -I tools/steine_aus_foto.py ... (oder `tools/py seg ...`; ohne 'seg' waehlt tools/py ~/.venvs/rcpark, dort fehlt cv2).
Exit: 0 = geschrieben, 2 = kaum Stein mit Fotodaten, 3 = kein vertrauenswuerdiges Foto / --streng ohne Ergebnis, 5 = Quader-Tor: kein Fugenraster.
"""
import sys, os, json, argparse, numpy as np, cv2
from scipy import ndimage as ndi


def linien(m, min_len):
    lab, n = ndi.label(m, np.ones((3, 3)))
    if not n: return m & False, 0.0
    sl = ndi.find_objects(lab); gut = np.zeros(n + 1, bool); summe = 0.0
    fl = ndi.sum(m, lab, np.arange(1, n + 1))
    for i, s in enumerate(sl, 1):
        L = max(s[0].stop - s[0].start, s[1].stop - s[1].start)
        if L >= min_len and fl[i - 1] <= 6.0 * L * 4: gut[i] = True; summe += L          # lang und duenn (mittlere Breite <= ~24 Zellen ueber verzweigte Netze)
    return gut[lab], summe


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("relief"); ap.add_argument("aus"); ap.add_argument("fassaden"); ap.add_argument("nr"); ap.add_argument("ortho")
    ap.add_argument("--feld", nargs=4, type=float, required=True); ap.add_argument("--px", type=float, default=0.02); ap.add_argument("--fuge", type=float, default=0.03); ap.add_argument("--massstab", nargs=4, type=float)
    ap.add_argument("--ohne", nargs=4, type=float, action="append", default=[], help="Feld u0 u1 z0 z1 ohne Steine (Vordach, Wandbild: Generator baut dort selbst)"); ap.add_argument("--bosse", type=float, default=0.04, help="Buckel der Steinflaeche (m), 0 = eben"); ap.add_argument("--putz_s", type=float, default=0.22); ap.add_argument("--foto", help="statt des Orthos: Bild direkt aus diesem kalibrierten Foto auf der Reliefebene lesen (fassaden/nr/ortho dann als - - 0 - angeben)"); ap.add_argument("--objekt"); ap.add_argument("--stl", help="Modell-STL(s) fuer die Verdeckungspruefung"); ap.add_argument("--rand", type=float, default=0.3); ap.add_argument("--streng", action="store_true", help="nur mit Gegenfoto und <= 2 cm/px (fuer die automatische Kette)"); ap.add_argument("--gegenfoto", help="Foto fuer die Verdecker-Gegenprobe (sonst das naechstbeste von anderem Standort bei --foto auto)"); ap.add_argument("--uneinig", type=float, default=0.25, help="oertliche Korrelation mit dem Gegenfoto unter diesem Wert = Verdecker"); ap.add_argument("--textur", type=float, default=8.0, help="nur Stellen mit Struktur pruefen (Grauwert-Streuung); glatter Putz hat keine Korrelation"); ap.add_argument("--nah", type=float, default=0.25, help="Stein nur so nah (m) an der groben Steinmaske; 0 = aus (Wand ohne Wandbilder: sonst gehen Steinbaender verloren, die die grobe Maske nicht kennt)"); ap.add_argument("--duenn", type=float, default=0.12, help="Steinflaechen duenner als dies (m) verwerfen; 0 = aus"); ap.add_argument("--putz_v", type=float, default=0.45)
    ap.add_argument("--tor", type=float, default=0.12, help="Quader-Tor: Mindestanteil der Feldhoehe mit regelmaessigen, durchlaufenden Lagerfugen (0 = aus). Gemessen 17.11.2026: Gemessen 17.11.2026: echtes Quaderwerk (Schwabentor Sued/West/Nord, beide Polaritaeten) 18-40 %% mit 7-25 Schichten; kein Quaderwerk (kaufhaus_gk Hauptfassade roter Putz mit Fenstern/Gesimsen, Seitenstreifen) 0-3 %% mit 0-1 Schichten. Schwelle dazwischen; ausserdem >= 4 Schichten. Schwelle dazwischen; rc 5 bei Ablehnung")
    ap.add_argument("--paar", type=float, default=0.3, help="Paar-Probe: Haupt- und Gegenfoto muessen auf mindestens diesem Anteil der gemeinsam gesehenen Struktur uebereinstimmen, sonst ist eine Kamera falsch (kein Verdecker) und das naechste Foto wird versucht")
    ap.add_argument("--haupt_max", type=int, default=3, help="so viele Hauptfotos (Rangfolge) hoechstens versuchen"); ap.add_argument("--gegen_max", type=int, default=4, help="so viele Gegenfotos je Hauptfoto hoechstens versuchen")
    ap.add_argument("--schwelle", type=float, default=2.4, help="Fuge ab so vielen Standardabweichungen der Abweichung vom oertlichen Median"); a = ap.parse_args()
    Z = dict(np.load(a.relief)); rel = Z["rel"].astype(np.float32); H, W = rel.shape; rp = float(Z["px"]); u0 = float(Z["u0"]); z0 = float(Z["z0"]); A = Z["a"]; t = Z["t"]; niv = float(Z.get("putz_niveau_m", 0.0))
    if not a.foto: F = json.load(open(a.fassaden))["fassaden"][int(a.nr)]; R = F["raster"]; o = np.array(F["o"]); d = np.array(F["d"]); im = cv2.imread(a.ortho)
    f0, f1, g0, g1 = a.feld; c = 0.01; nu = int(round((f1 - f0) / c)); nz = int(round((g1 - g0) / c)); jj, ii = np.meshgrid(np.arange(nu), np.arange(nz)); U = f0 + (jj + 0.5) * c; ZZ = g1 - (ii + 0.5) * c
    if a.foto:
        # 16.11.2026: DIREKT aus dem Foto auf der WANDEBENE DES RELIEFS lesen (nicht ueber ein Ortho auf der LoD2-Fassadenebene): die LoD2-Ebene liegt bis 0,75 m neben der Wand,
        # bei schraegem Blick verschiebt das den Bildinhalt seitlich um Dezimeter (West Schwabentor: Nordwestecke erschien 1 m zu frueh, dahinter "Steine" aus Himmel).
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import glob, fassade_ein_foto as FE
        nv_ = Z["n"]; tu_, tz_ = [float(v) for v in Z["trend_je_m"]]; dpl = float(Z["ebene_abstand_m"]) + tu_ * (U - u0) - tz_ * ((z0 + H * rp) - ZZ)
        X = A[0] + U * t[0] + dpl * nv_[0]; Y = A[1] + U * t[1] + dpl * nv_[1]; Zw = ZZ
        if a.massstab: k = a.massstab[0]; Mp = a.massstab[1:]; X = Mp[0] + k * (X - Mp[0]); Y = Mp[1] + k * (Y - Mp[1]); Zw = Mp[2] + k * (ZZ - Mp[2])
        od_ = os.path.dirname(os.path.abspath(a.objekt)); root_ = os.path.dirname(os.path.dirname(od_)); obj_ = json.load(open(a.objekt)); mm_ = None; rk_ = None; mp_ = os.path.join(od_, "messprotokoll")
        if a.stl:
            import trimesh, render_kern as rk_
            ms_ = [trimesh.load(q_) for q_ in a.stl.split(",")]; mm_ = trimesh.util.concatenate(ms_) if len(ms_) > 1 else ms_[0]; mm_.apply_scale(float(obj_.get("stl_massstab", 87)) / 1000.0)
        P_ = np.stack([X, Y, Zw], -1).reshape(-1, 3); rang = []
        if a.foto == "auto":                                              # bestes vertrauenswuerdiges Foto fuer DIESES Feld: sichtbare Flaeche / Meter je Pixel (Verdeckung gegen das Modell)
            G_ = P_.reshape(U.shape + (3,))[::25, ::25].reshape(-1, 3); Pm_ = G_.mean(0); kand = []
            for kf in glob.glob(os.path.join(mp_, "K-*.json")):
                n_ = os.path.basename(kf)[2:-5]; K_ = FE.kamera(kf)
                if K_ is None or n_.startswith("video") or (n_.startswith(("dl_", "neu__")) and not K_.get("vertrauen")) or not glob.glob(os.path.join(root_, obj_["fotos_dir"], n_ + ".*")): continue
                R_ = cv2.Rodrigues(np.array(K_["rvec"]))[0]; C_ = -R_.T @ np.array(K_["t"]); v_ = C_ - Pm_; di_ = np.linalg.norm(v_); cw_ = float(v_[:2] @ nv_[:2] / di_)
                if cw_ >= 0.3 and di_ <= 250: kand.append((di_ / (K_["f_px"] * cw_), n_, K_))
            for mpp_, n_, K_ in sorted(kand, key=lambda q_: q_[0])[:12]:
                ok0 = FE.sichtbar(mm_, K_, G_, rk_, tol=0.6)[0]; rang.append((float(ok0.mean()) ** 2 / max(mpp_, 0.005), n_, float(ok0.mean()), mpp_))      # Abdeckung zaehlt quadratisch, Aufloesung nur bis 0,5 cm/px: sonst gewinnt eine Nahaufnahme, die 15 % der Wand zeigt (Haertetest ober_tvdr)
            rang.sort(key=lambda q_: -q_[0])
            if not rang or rang[0][2] < 0.3: print("kein vertrauenswuerdiges Foto sieht mindestens 30 % dieses Feldes"); return 3
            a.foto = rang[0][1]; print("Fotowahl:", [(q_[1][-22:], f"{q_[2] * 100:.0f} %", f"{q_[3] * 100:.1f} cm/px") for q_ in rang[:4]])
        def lesen(n_):                                                    # Foto n_ auf der Wandebene des Reliefs: (sichtbar, Bild, Tiefe, Kamera)
            K_ = FE.kamera(os.path.join(mp_, "K-" + n_ + ".json")); ok_, mx_, my_, zc_ = FE.sichtbar(mm_, K_, P_, rk_, tol=0.6)
            if a.stl and a.rand > 0: ok_ = cv2.erode(ok_.reshape(U.shape).astype(np.uint8), np.ones((2 * int(a.rand / c) + 1,) * 2, np.uint8)).astype(bool).ravel()
            im_ = cv2.imread(glob.glob(os.path.join(root_, obj_["fotos_dir"], n_ + ".*"))[0]); b_ = cv2.remap(im_, mx_.astype(np.float32).reshape(U.shape), my_.astype(np.float32).reshape(U.shape), cv2.INTER_LINEAR, borderValue=(0, 0, 0)); b_[~ok_.reshape(U.shape)] = 0
            return ok_, b_, zc_, K_
        def nrm_(b_, s_=3.0): g_ = cv2.GaussianBlur(cv2.cvtColor(b_, cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), s_); m_ = cv2.blur(g_, (61, 61)); sd_ = np.sqrt(np.maximum(cv2.blur(g_ * g_, (61, 61)) - m_ * m_, 0)); return (g_ - m_) / (sd_ + 2.0), sd_
        def standort(K_): return -cv2.Rodrigues(np.array(K_["rvec"]))[0].T @ np.array(K_["t"])
        # VERDECKER, die nicht im Modell stehen (Baum, Geruest, Fahrzeug): Gegenprobe mit einem Foto von einem ANDEREN Standort - auf der Wandebene muessen beide
        # dasselbe zeigen (oertlich normierte Helligkeit); wo sie sich grossflaechig widersprechen, gilt die Stelle als "keine Daten" (16.11.2026: Baum wurde auf der Suedseite zu Steinen).
        # 21.11.2026 PAAR-PROBE (Schwabentor West w00: Gegenfoto eigen__192 hatte eine falsche Kamera - Gesims 4 m zu tief auf der Wand -, auf 99 % der Struktur
        # widerspruechlich; ausgeblendet wurden genau die Eckquader, das Quader-Tor sah 0 % Schichten, die Wand blieb glatt): ein Verdecker widerspricht OERTLICH,
        # ein Foto mit falscher Kamera UEBERALL. Stimmt ein Paar auf weniger als --paar der gemeinsam gesehenen Struktur ueberein, ist das kein Verdecker, sondern
        # ein unpassendes Paar -> naechstes Gegenfoto. Unter den --haupt_max besten Hauptfotos gewinnt das, das am besten von einem Foto eines anderen Standorts BESTAETIGT wird
        # (Schwabentor West: Rang 1 eigen__..114052 ist verwackelt - einig 47 %, Quader-Tor 3 % -, die Nachbaraufnahmen ..114037/39/50 vom selben Standort sind scharf - einig 69-72 %, Quader-Tor 16-20 %).
        haupt = [q_[1] for q_ in rang[:a.haupt_max] if q_[2] >= 0.3] if rang else [a.foto]; gew = None; erst = None; abgelehnt = []; je_haupt = []
        for hf in haupt:
            ok_, bild, zc_, Kc = lesen(hf); erst = erst or (hf, ok_, bild, zc_, Kc); na_, sa_ = nrm_(bild); C0_ = standort(Kc)
            kand2 = [a.gegenfoto] if a.gegenfoto else [q_[1] for q_ in rang if q_[1] != hf and q_[2] > 0.3 and np.linalg.norm(standort(FE.kamera(os.path.join(mp_, "K-" + q_[1] + ".json"))) - C0_) > 0.08 * np.linalg.norm(C0_ - P_.mean(0))]
            for n2 in kand2[:a.gegen_max]:
                ok2, b2, _, _ = lesen(n2); nb_, sb_ = nrm_(b2); beide = ok_.reshape(U.shape) & ok2.reshape(U.shape); korr = cv2.blur(na_ * nb_, (81, 81))      # oertliche Korrelation: gleiche Wand = hoch, Laub gegen Wand oder Laub gegen Laub = ~0
                tex = beide & (sa_ > a.textur); te_ = beide & ((sa_ > a.textur) | (sb_ > a.textur))      # Einigkeit auf der Struktur BEIDER Fotos: ein verwackeltes Hauptfoto hat kaum eigene Struktur und waere sonst immer 'einig'
                einig = float((korr[te_] >= a.uneinig).mean()) if te_.sum() >= 2000 else 1.0      # zu wenig Struktur zum Vergleichen (glatter Putz) = wie bisher annehmen
                if einig >= a.paar or a.gegenfoto:
                    kf_ = cv2.blur(nrm_(bild, 1.0)[0] * nrm_(b2, 1.0)[0], (81, 81)); km_ = float(np.clip(kf_[te_], 0, 1).mean()) if te_.sum() >= 2000 else 1.0
                    # Rang: mittlere FEINE Korrelation (1 cm statt 3 cm vorgeglaettet, stetig) - der Anteil 'einig' saettigt, ein verwackeltes Foto ist oft noch zu 100 % 'einig'
                    wert = km_ * float(ok_.mean()); je_haupt.append(f"{hf[-12:]}+{n2[-12:]}: einig {einig * 100:.0f} %, Korrelation {km_:.2f} x sichtbar {ok_.mean() * 100:.0f} %")      # bestaetigte Flaeche: Abdeckung zaehlt mit
                    if gew is None or wert > gew[0]: gew = (wert, hf, ok_, bild, zc_, Kc, n2, beide, korr, tex, einig)
                    break
                abgelehnt.append(f"{hf[-12:]}+{n2[-12:]}: einig {einig * 100:.0f} %")
        if abgelehnt: print(f"Fotopaare verworfen (stimmen auf der Wandebene auf < {a.paar * 100:.0f} % der Struktur ueberein = Kamera eines Fotos falsch, kein Verdecker):", abgelehnt)
        if len(je_haupt) > 1: print("Paar-Probe je Hauptfoto (Anteil der Struktur, auf dem das Gegenfoto dasselbe zeigt):", je_haupt)
        zweit = None
        if gew:
            _, a.foto, ok_, bild, zc_, Kc, zweit, beide, korr, tex, einig = gew
            uneinig = tex & (korr < a.uneinig); uneinig = cv2.dilate(cv2.morphologyEx(uneinig.astype(np.uint8), cv2.MORPH_OPEN, np.ones((25, 25), np.uint8)), np.ones((31, 31), np.uint8)).astype(bool)
            bild[uneinig] = 0; print(f"Gegenfoto {zweit[-30:]}: {beide.mean() * 100:.0f} % des Feldes von beiden gesehen, Paar einig auf {einig * 100:.0f} % der Struktur, {uneinig.mean() * 100:.0f} % widerspruechlich (Verdecker?) -> ausgeblendet")
        else:
            a.foto, ok_, bild, zc_, Kc = erst; print("kein passendes Gegenfoto von anderem Standort - Verdecker ausserhalb des Modells NICHT geprueft")
        mpp_ist = float(np.median(zc_[ok_]) / Kc["f_px"]) if ok_.any() else 9.0
        if a.streng and (zweit is None or mpp_ist > 0.02):               # Kette: lieber nichts als Steine aus einem groben oder ungeprueften Einzelfoto (Haertetest: Holzgeruest in 6 cm/px wurde zu "Quadern")
            print(f"STRENG: kein Ergebnis ({'kein Gegenfoto' if zweit is None else f'Foto zu grob: {mpp_ist * 100:.1f} cm/px > 2'})"); return 3
        print(f"Foto {a.foto[-40:]}: {np.median(zc_[ok_]) / Kc['f_px'] * 100:.1f} cm/px an der Wand, {ok_.mean() * 100:.0f} % des Feldes sichtbar")
    else:
        X = A[0] + U * t[0]; Y = A[1] + U * t[1]; Zw = ZZ
        if a.massstab: k = a.massstab[0]; Mp = a.massstab[1:]; X = Mp[0] + k * (X - Mp[0]); Y = Mp[1] + k * (Y - Mp[1]); Zw = Mp[2] + k * (ZZ - Mp[2])
        uo = (X - o[0]) * d[0] + (Y - o[1]) * d[1]; bild = cv2.remap(im, ((uo - R["u0"]) / R["zelle"] - 0.5).astype(np.float32), ((R["z1"] - Zw) / R["zelle"] - 0.5).astype(np.float32), cv2.INTER_LINEAR, borderValue=(0, 0, 0))
    daten = bild.max(2) > 8; grau = cv2.cvtColor(bild, cv2.COLOR_BGR2GRAY).astype(np.float32)
    def gross(x, interp=cv2.INTER_LINEAR): return cv2.remap(x, ((U - u0) / rp - 0.5).astype(np.float32), (H - (ZZ - z0) / rp - 0.5).astype(np.float32), interp, borderMode=cv2.BORDER_REPLICATE)
    putz = gross((Z["putz"] if "putz" in Z else np.zeros(rel.shape, bool)).astype(np.float32)) > 0.5; grob = gross(rel)      # 17.11.2026: ohne Putzmaske (farbiger Putzbau, relief_putz fand nichts) gilt alles als moeglicher Stein - das Quader-Tor entscheidet
    if "wand" in Z: daten &= gross(Z["wand"].astype(np.float32)) > 0.5      # 17.11.2026: Wandflaeche laut LoD2 (fassaden_kette.wand_flaeche): Dach ueber der Traufe, Himmel und angebaute Nachbarn sind keine Wand (Dachziegel haben auch 'Lagerfugen')
    hsv = cv2.cvtColor(cv2.GaussianBlur(bild, (0, 0), 2.0), cv2.COLOR_BGR2HSV).astype(np.float32); pf = (hsv[..., 1] / 255 < a.putz_s) & (hsv[..., 2] / 255 > a.putz_v)   # Kontur Putz/Stein im 1-cm-Bild neu (gleiche Regel wie relief_putz.py, dort nur 5 cm): Verzahnung scharf statt ausgefranst
    if (putz & daten).sum() > 500: pf &= hsv[..., 2] > 0.82 * float(np.median(hsv[..., 2][putz & daten]))      # Putz ist so hell wie der sichere Putz daneben - graue (wenig gesaettigte) Steine sind dunkler
    pf = ndi.binary_closing(ndi.binary_opening(pf, np.ones((7, 7))), np.ones((7, 7))); nah = ndi.binary_dilation(~putz, np.ones((2 * int(a.nah / c) + 1,) * 2)) if a.nah > 0 else np.ones(putz.shape, bool)          # Stein nur in der Naehe (25 cm) der groben Steinmaske: Wandbilder/Fenster im Putz bleiben Putz
    putz = np.where(daten, pf | ~nah, putz)
    if a.duenn > 0: st_ = ndi.binary_opening(~putz & daten, np.ones((int(a.duenn / c) | 1,) * 2)); putz = np.where(daten, ~st_, putz)      # duenne 'Stein'-Linien (Ortgangkante, Draht, Rand einer Verdeckung) sind keine Quader
    for wert, min_zellen in ((True, 3000), (False, 1000)):               # Inseln weg: helle Steine mitten im Quaderfeld sind kein Putz (< 0,3 m2), Farbflecken im Putz kein Stein (< 0,1 m2)
        lab_, n_ = ndi.label(putz == wert)
        if n_: gr_ = ndi.sum(np.ones(putz.shape), lab_, np.arange(1, n_ + 1)); putz[np.isin(lab_, 1 + np.flatnonzero(gr_ < min_zellen))] = not wert
    for q0, q1, r0, r1 in a.ohne: putz |= (U >= q0) & (U <= q1) & (ZZ >= r0) & (ZZ <= r1)
    stein = ~putz & daten
    if stein.sum() < 2000: print("kaum Stein mit Fotodaten im Feld"); return 2
    from scipy.signal import find_peaks
    g = cv2.GaussianBlur(grau, (0, 0), 1.0); ab = g - cv2.medianBlur(np.clip(g, 0, 255).astype(np.uint8), 21).astype(np.float32); best = None
    komp, nk = ndi.label(ndi.binary_opening(stein, np.ones((9, 9))))
    for name, vz in (("hell", 1.0), ("dunkel", -1.0)):                    # Polaritaet nicht vorgegeben: beide rechnen, die mit den deutlicheren Lagerfugen gewinnt
        r = vz * ab; fuge = np.zeros(stein.shape, bool); guete = 0.0; summe = 0.0; tor_h = 0.0; tor_deck = 0.0; tor_n = 0
        for ki in range(1, nk + 1):                                       # je zusammenhaengendem Steinfeld (Eckstreifen): Schichten = Zeilenprofil, Stossfugen = Spaltenprofil je Schicht
            m = komp == ki
            if m.sum() < 3000: continue
            ys, xs = np.nonzero(m); y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1; mm = m[y0:y1, x0:x1]; rr = np.where(mm, r[y0:y1, x0:x1], 0.0)
            nrow = mm.sum(1); p = ndi.gaussian_filter1d(rr.sum(1) / np.maximum(nrow, 1), 1.0); p[nrow < 15] = 0
            lager, pr = find_peaks(p, distance=16, prominence=a.schwelle * 0.5 * float(p.std())); guete += float(pr["prominences"].sum()) if len(lager) else 0.0
            grenzen = [0] + list(lager) + [y1 - y0]
            # QUADER-TOR (17.11.2026, kaufhaus_gk: roter Putz und ein blaues Nachbarhaus mit Fensterlaeden wurden zu "Quadern"): find_peaks hat eine RELATIVE Schwelle und findet in jedem Bild Spitzen.
            # Echtes Quaderwerk hat DURCHLAUFENDE Lagerfugen in regelmaessigem Abstand. Je Lagerfuge: Anteil der Feldbreite, auf dem die Zeile (15 cm laengs gemittelt) wirklich ein Grat ist
            # (ueber der Rauschschwelle UND hoeher als 5 cm darueber/darunter) = 'tragend' ab 50 %. Deckung = Anteil der Feldhoehe zwischen benachbarten tragenden Fugen mit Schichthoehe 25-70 cm
            # (erste Fassung 16-70 cm: Gesimsprofile und Fenstersprossen der Kaufhaus-Hauptfassade, Abstaende 17-29 cm, kamen auf 15 %; echte Schichten am Schwabentor liegen bei 30-65 cm).
            rs_ = cv2.blur(rr, (15, 1)); sg_ = 1.48 * float(np.median(np.abs(rr[mm] - np.median(rr[mm])))); th_ = max(1.5, sg_); hk_ = y1 - y0; trag = []
            for l_ in lager:
                zl_ = rs_[max(l_ - 1, 0):l_ + 2].max(0); gr_ = (zl_ > th_) & (zl_ > rs_[max(l_ - 5, 0)] + 0.5 * th_) & (zl_ > rs_[min(l_ + 5, hk_ - 1)] + 0.5 * th_)
                if mm[l_].sum() >= 15 and gr_[mm[l_]].mean() >= 0.5: trag.append(l_)
            if os.environ.get("TOR_DEBUG"): print("   TOR", ki, "Feld", x1 - x0, "x", y1 - y0, "cm, Breite Median", int(np.median(nrow[nrow > 0])), "Abstaende", np.diff(trag).tolist())
            tor_h += float((nrow >= 15).sum()); sch_ = [d_ for d_ in np.diff(trag) if 25 <= d_ <= 70]; tor_n += len(sch_); tor_deck += float(sum(sch_))
            for l_ in lager: fuge[y0 + l_ - 1:y0 + l_ + 2, x0:x1] |= mm[l_ - 1:l_ + 2] if l_ >= 1 else False; summe += mm[l_].sum()
            for b0, b1 in zip(grenzen[:-1], grenzen[1:]):
                if b1 - b0 < 8: continue
                band = mm[b0 + 2:b1 - 2]; ncol = band.sum(0); q = ndi.gaussian_filter1d(rr[b0 + 2:b1 - 2].sum(0) / np.maximum(ncol, 1), 1.0); q[ncol < 0.6 * max(b1 - b0 - 4, 1)] = 0
                stoss, _ = find_peaks(q, distance=20, prominence=a.schwelle * 0.6 * float(q.std()) + 1e-6)
                for s_ in stoss: fuge[y0 + b0:y0 + b1, x0 + max(s_ - 1, 0):x0 + s_ + 2] |= mm[b0:b1, max(s_ - 1, 0):s_ + 2]; summe += b1 - b0
        fuge |= stein & ~ndi.binary_erosion(stein, np.ones((3, 3)), border_value=1) & False
        deck = tor_deck / max(tor_h, 1.0); print(f"Fugen {name}: {summe / 100:.0f} m, Deutlichkeit der Lagerfugen {guete:.1f}; Quader-Tor: {tor_n} Schichten (25-70 cm) zwischen durchlaufenden Lagerfugen, auf {deck * 100:.0f} % der Feldhoehe")
        if best is None or guete > best[3]: best = (name, fuge, summe, guete, deck, tor_n)
    name, fuge, summe = best[:3]
    if a.tor > 0 and (best[4] < a.tor or best[5] < 4):                   # kein Fugenraster im Bild = kein Quaderwerk (Putz, Holz, Nachbarhaus, Laub): lieber nichts als erfundene Steine
        print(f"QUADER-TOR: kein Fugenraster (Schichten zwischen durchlaufenden Lagerfugen auf {best[4] * 100:.0f} % der Feldhoehe < {a.tor * 100:.0f} % oder nur {best[5]} Schichten < 4) - keine Steine. Von Hand uebersteuern: --tor 0"); return 5
    lab, n = ndi.label(stein & ~fuge); fl = ndi.sum(stein, lab, np.arange(1, n + 1)); klein = np.isin(lab, 1 + np.flatnonzero(fl < 60)); fuge |= klein & stein          # Kruemel < 60 cm2 zur Fuge
    fl = fl[fl >= 60]; dt = ndi.distance_transform_edt(~fuge) * c
    niveau = cv2.GaussianBlur(np.where(stein, grob, 0).astype(np.float32), (0, 0), 30) / np.maximum(cv2.GaussianBlur(stein.astype(np.float32), (0, 0), 30), 1e-3)
    niveau = np.maximum(niveau, niv + 0.02); h = niveau - a.fuge * (1.0 - np.clip(dt / 0.03, 0, 1))
    if a.bosse > 0:                                                       # Buckelquader: Kissen je Stein + rauhe Bruchflaeche. ERFUNDEN (Form der einzelnen Bosse ist nicht gemessen), nur Fugenlage und Kontur sind echt
        rng = np.random.default_rng(1); lab2, n2 = ndi.label(stein & ~fuge); je = np.r_[0.0, rng.uniform(0.6, 1.2, n2)][lab2]
        rauh = ndi.gaussian_filter(rng.standard_normal(stein.shape), 3.0); rauh = rauh / (rauh.std() + 1e-9) * 0.008 + ndi.gaussian_filter(rng.standard_normal(stein.shape), 9.0) * 0.12
        h = h + (a.bosse * je * np.sqrt(np.clip(dt / 0.10, 0, 1)) + rauh * np.clip(dt / 0.04, 0, 1)).astype(np.float32)
    aus = np.where(stein, h, np.where(putz, niv if abs(niv) > 1e-6 else 1e-4, grob)).astype(np.float32)
    kq = int(round(a.px / c)); aus2 = cv2.resize(aus, (nu // kq, nz // kq), interpolation=cv2.INTER_AREA)
    Zo = {k_: Z[k_] for k_ in ("a", "t", "n", "ebene_abstand_m") if k_ in Z}; tu, tz = [float(v) for v in Z["trend_je_m"]]
    Zo["ebene_abstand_m"] = float(Z["ebene_abstand_m"]) + tu * (f0 - u0) + tz * (g1 - (z0 + H * rp))      # Ebene des Trends am neuen Ursprung (links oben)
    Zo.update(rel=aus2, u0=f0, z0=g0, px=a.px, trend_je_m=Z["trend_je_m"], putz_niveau_m=niv, fein=np.ones(aus2.shape, bool), fugen_polaritaet=name, fugen_m=summe / 100, steine=len(fl), stein_median_m2=float(np.median(fl)) * c * c if len(fl) else 0.0)
    np.savez_compressed(a.aus, **Zo)
    lx = np.gradient(aus, c, axis=1); lz = np.gradient(aus, c, axis=0); sh = (np.clip(0.7 - 0.5 * lx + 0.7 * lz, 0, 1) * 255).astype(np.uint8)
    cv2.imwrite(os.path.splitext(a.aus)[0] + ".jpg", np.hstack([bild, cv2.cvtColor(sh, cv2.COLOR_GRAY2BGR)]))
    print(f"{os.path.basename(a.aus)}: Fugen {name}, {summe / 100:.0f} m, {len(fl)} Steine, Median {Zo['stein_median_m2']:.3f} m2, Stein mit Fotodaten {stein.sum() * c * c:.1f} m2, ohne Daten {(~daten & ~putz).sum() * c * c:.1f} m2")


if __name__ == "__main__":
    sys.exit(main())
