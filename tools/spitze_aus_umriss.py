#!/usr/bin/env python3
"""spitze_aus_umriss.py - TURMSPITZE / LATERNE / DACHREITER aus den FOTO-SILHOUETTEN gegen den Himmel (21.11.2026).

Anlass (Kettenlauf Schwabentor 21.11.): das Dachprofil kommt aus der dichten Wolke (tools/dach_profil_wolke.py); nach oben wird die Wolke duenn, die Spitze fehlt
(Wolke endet ~2 m unter dem Knauf) und der Hals der Laterne liegt dort, wo nur noch wenige hundert Punkte je Scheibe sind. KERNMETHODE: Form aus Fotos, Wolke nur Lage.
Die Laterne ist nicht unbedingt rund (rund_aus_umriss.py setzt einen Kreisquerschnitt und Gradienten-Kanten voraus, Fugen und Dachziegel stoeren); vor dem Himmel ist
der Umriss dagegen eindeutig. Darum hier die HIMMELSKANTE (foto_pick.himmel, Cache audit/himmel_cache wie dach_aus_fotos/umriss_tor):

 1. Achse = gemessene Dachachse aus audit/dach_profil.json (o + achse_uv im Fassadenrahmen d/n) - nur LAGE aus der Wolke.
 2. Je kalibriertem Foto (messprotokoll/K-*.json, flaeche_ortho.kameras_laden/projektion) die Achse z = Mitte Dachprofil .. Wolkenende + --ueber projizieren.
    SPITZE: oberste Hoehe, deren Achsenpunkt noch auf Bauwerk faellt (Band +-BAND_M quer), durchgehend von unten; die Spitze liegt auf der Achse (Drehsymmetrie der
    Zelt-/Pyramidenspitze - ANNAHME), also ist der Sehstrahl-Schnitt mit der Achse die Hoehe. Gilt nur, wenn die Silhouette dort ihren Gipfel hat (hoechster
    Bauwerkspixel im Fenster +-GIPFEL_M liegt an der Achse): wer nah unter der Traufe steht, sieht die Traufe ueber der Spitze -> Foto entfaellt.
    Obere Bildkante oder Verdecker ueber der Spitze (kein Himmel ueber ihr) -> Foto entfaellt.
 3. BREITE je Hoehe: Zeile durch den Achsenpunkt, quer zur projizierten Achse nach links und rechts bis zum Himmel; nur wenn BEIDE Seiten innerhalb MAX_HALB_M Himmel
    erreichen (sonst Dachflaeche/Nachbar dahinter). Pixel -> m mit einem Meter-Lineal quer zur Blickrichtung an der Achse (wie foto_breitenprofil.py).
    Sichtbare Halbbreite haengt beim eckigen Querschnitt von der Blickrichtung ab: Median ueber die Fotos + Streuung im Bericht; Querschnitt ist ANNAHME.
 4. Abstimmung: Spitze = Median der Fotos (mind. MIN_FOTOS aus mind. MIN_SEKTOREN Richtungen), Profil = Median je Hoehe (mind. MIN_FOTOS Fotos).
    Hals/Krempe: schmalste Stelle der Laterne, Krempe = erste Verbreiterung > 20 % darueber (dieselbe Regel wie hand_vergleich am Wolkenprofil).
Ausgabe: Block 'spitze_foto' in audit/dach_profil.json (spitze_z, profil [[z, halb_m, n_fotos, streuung]], hals_z, krempe_z, fotos, sektoren, gueltig, grund) -
bauteile.dach_aus_profil baut damit ueber dem Wolkenende die Laterne/Spitze aus den Fotos weiter; Bild audit/spitze_umriss.jpg (Fotos mit Achse, Spitze, Breiten; rechts Profil).
Aufruf: spitze_aus_umriss.py <objekt.json> [--profil audit/dach_profil.json] [--ueber 6] [--schritt 0.25] [--max-fotos 200] [--nur-messen]
rc 0 = gueltig eingetragen, rc 3 = kein Dachprofil, rc 4 = zu wenig Fotos (Block mit gueltig=false eingetragen, Generator nutzt ihn nicht).
"""
import sys, os, json, argparse, math, numpy as np

H_ = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H_)

# ---- Schwellen (Grund je Zeile; nicht an einem Bauwerk eingestellt) ---------------------------------------------------------------------------
BAND_M = 0.12          # halbe Bandbreite quer zur Achse: Knauf/Nadel sind duenn (Stange ~5-10 cm), 1600-px-Maske loest auf 40 m Abstand ~3 cm/px
GIPFEL_M = 2.5         # Fenster quer, in dem der Silhouettengipfel an der Achse liegen muss (groesser als jede Laterne, kleiner als das Dach)
GIPFEL_TOL_M = 0.6     # Gipfel darf so weit neben der Achse liegen (Achse aus der Wolke auf Dezimeter, schraeger Blick versetzt den Knauf etwas)
MAX_HALB_M = 3.5       # Breitenmessung nur bis 3,5 m Halbbreite (darueber ist es Dachflaeche, nicht Laterne)
LUECKE_M = 0.3         # Luecken bis 30 cm in der Achse gelten als durchgehend (Maskenrauschen an der Nadel)
MIN_FOTOS = 8          # Spitze/Profilhoehe braucht 8 Fotos (Formfamilie >= 3 Fotos, hier mehr: einzelne Masken sind an duennen Spitzen unvollstaendig)
MIN_SEKTOREN = 3       # aus 3 Richtungssektoren (45 Grad) - ein einzelner Standort koennte eine falsche Kamera sein
SEKTOR_GRAD = 45
KREMPE = 1.2           # Krempe = erste Verbreiterung > 20 % ueber dem Hals (wie hand_vergleich)
PLATEAU = 0.93         # Krempe = erste Hoehe mit 93 % der Haubenbreite (Untersicht-Ellipse erreicht das erst nahe der Kante; Profilstreuung ~3-5 %)
STUFE_M = 0.15         # ... und mind. 15 cm absolut (Profilstreuung je Hoehe 3-10 cm; an einer duennen Nadel sind 20 % nur wenige cm)


def projektor(c, s):
    import flaeche_ortho as FO
    def p(X):
        q, z, C = FO.projektion(np.atleast_2d(X), c); return q * s, z, C
    return p


def foto_messen(maske, proj, A, zs, C):
    """Ein Foto: Spitze (z oder None + Grund) und Halbbreiten je Hoehe. maske True = Himmel. A = Achse (x, y). C = Kamerastandort."""
    H, W = maske.shape; X = np.c_[np.tile(A, (len(zs), 1)), zs]; p, zc, _ = proj(X)
    if (zc <= 0.5).any(): return None, "Achse hinter der Kamera", {}
    b = np.array([A[0] - C[0], A[1] - C[1], 0.0]); b /= max(np.linalg.norm(b), 1e-9); q = np.array([-b[1], b[0], 0.0])     # quer zur Blickrichtung, horizontal
    p1, _, _ = proj(X + q); ppm = np.linalg.norm(p1 - p, axis=1)                                                         # Pixel je Meter quer an der Achse
    e = (p1 - p) / np.maximum(ppm[:, None], 1e-9)
    if (p[:, 0] < 2).any() or (p[:, 0] > W - 3).any(): return None, "Achse ausserhalb des Bilds", {}
    def bau(x, y): xi, yi = int(round(x)), int(round(y)); return 0 <= xi < W and 0 <= yi < H and not maske[yi, xi]
    def band(i, m):
        n = max(1, int(math.ceil(m * ppm[i])))
        return any(bau(p[i, 0] + k * e[i, 0], p[i, 1] + k * e[i, 1]) for k in range(-n, n + 1))
    if p[-1, 1] < 2: return None, "obere Bildkante unter der Suchhoehe", {}
    an = [band(i, BAND_M) for i in range(len(zs))]
    if not an[0]: return None, "Achse unten schon Himmel (Dach nicht gesehen/Achse falsch)", {}
    dz = zs[1] - zs[0]; lu = max(1, int(round(LUECKE_M / dz))); top = 0; leer = 0
    for i in range(1, len(zs)):
        if an[i]: top = i; leer = 0
        else:
            leer += 1
            if leer > lu: break
    if top >= len(zs) - lu - 1: return None, "kein Himmel ueber der Spitze (Verdecker/Bildkante)", {}
    # Gipfel: im Fenster +-GIPFEL_M quer muss die hoechste Bauwerkszeile an der Achse liegen
    it = top; n = int(GIPFEL_M * ppm[it]); best = None
    for k in range(-n, n + 1, max(1, n // 60)):
        x = p[it, 0] + k * e[it, 0]; y0 = p[it, 1] + k * e[it, 1]
        xi = int(round(x))
        if not 0 <= xi < W: continue
        col = ~maske[:max(1, min(H, int(y0) + 1)), xi]
        if col.any():
            yt = int(np.argmax(col))
            if best is None or yt < best[0] - 1: best = (yt, k / ppm[it])
    if best is not None and abs(best[1]) > GIPFEL_TOL_M: return None, f"Silhouettengipfel {best[1]:+.1f} m neben der Achse (Traufe/Dach verdeckt die Spitze)", {}
    # Spitze genauer: zwischen top und top+1 die Zeile des letzten Bauwerkspixels auf der Achse (Unterabtastung dz)
    z_sp = float(zs[top] + dz / 2)
    halb = {}
    for i in range(top + 1):
        nmax = int(MAX_HALB_M * ppm[i]); seiten = []
        for sg in (-1, 1):
            k = 0
            while k <= nmax and bau(p[i, 0] + sg * k * e[i, 0], p[i, 1] + sg * k * e[i, 1]): k += 1
            seiten.append(k if k <= nmax else None)
        if None not in seiten and sum(seiten) > 0: halb[round(float(zs[i]), 2)] = ((seiten[0] + seiten[1]) / 2 / ppm[i], (seiten[1] - seiten[0]) / 2 / ppm[i])
    return z_sp, None, halb


def auswerten(messungen, zs, sektor):
    """messungen: Liste (name, az_grad, z_spitze, halb{z: (h, versatz)} [, (kamera_z, abstand_waagrecht)]). -> dict Ergebnis (ohne Dateien, fuer den Test)."""
    sp = [(m[0], m[1], m[2]) for m in messungen if m[2] is not None]
    sek = sorted({int((az % 360) // sektor) for _, az, _ in sp}); erg = dict(fotos=len(sp), sektoren=sek)
    if len(sp) < MIN_FOTOS or len(sek) < MIN_SEKTOREN:
        erg.update(gueltig=False, grund=f"Spitze nur in {len(sp)} Fotos aus {len(sek)} Richtungen (verlangt {MIN_FOTOS} / {MIN_SEKTOREN})"); return erg
    zsp = np.array([s[2] for s in sp]); med = float(np.median(zsp)); erg.update(spitze_z=round(med, 2), spitze_streuung=round(float(np.median(np.abs(zsp - med))), 2))
    prof = []; formen = []
    for z in zs:
        z = round(float(z), 2); hv = [(m[1], m[3][z][0]) for m in messungen if m[2] is not None and z in m[3]]
        if len(hv) >= MIN_FOTOS and z < med:
            v = np.array([x[1] for x in hv]); h = float(np.median(v)); prof.append([z, round(h, 3), len(v), round(float(np.median(np.abs(v - h))), 3)]); formen.append(querschnitt([x[0] for x in hv], v))
    if len(prof) >= 3:
        r = [p[1] for p in prof]; g = [float(np.median(r[max(0, i - 1):i + 2])) for i in range(len(r))]       # Median ueber 3 Hoehen (Maskenrauschen)
        for p, gi in zip(prof, g): p[1] = round(gi, 3)
        # Hals/Krempe: laufendes Minimum von unten; Krempe = erste Hoehe, die > KREMPE x Minimum UND > STUFE_M breiter ist (eine Nadel 0,22 -> 0,30 m ist Rauschen, kein Kragen)
        im_ = 0
        for i in range(1, len(prof)):
            if prof[i][1] < prof[im_][1]: im_ = i
            elif prof[i][1] > KREMPE * prof[im_][1] and prof[i][1] - prof[im_][1] > STUFE_M:
                rk = max(p[1] for p in prof[i:] if p[0] <= prof[i][0] + 1.5)
                # Untersicht: die Unterkante der Haube erscheint von unten als Ellipse, ihr hinterer Rand liegt im Bild tiefer als die Seitenpunkte - die Breite ueberschreitet die
                # Schwelle schon unter der Kante (synthetisch 0,5 m zu tief). Die Seitenpunkte (Kante auf Achsentiefe) geben die volle Breite: Krempe = erste Hoehe mit >= PLATEAU x Haubenbreite.
                # (Verworfen: Korrektur r*tan(Hoehenwinkel) fuer eine waagrechte Scheibe - am Schwabentor springt die Breite in 0,3 m, die Krempe ist ausgestellt, Korrektur +0,67 m zu viel.)
                kp = next((p for p in prof[i:] if p[1] >= PLATEAU * rk), prof[i])
                erg.update(hals_z=prof[im_][0], hals_halb=prof[im_][1], krempe_z=kp[0], krempe_roh_z=prof[i][0],
                           krempe_halb=round(rk, 3)); break
    # Querschnitt je Hoehe: eckig (Quadrat, Lage theta) oder rund - aus der Abhaengigkeit der sichtbaren Halbbreite von der Blickrichtung; geglaettet ueber 5 Hoehen (Mehrheit)
    for i, p in enumerate(prof):
        nb = [f for f in formen[max(0, i - 2):i + 3] if f]; eck = sum(f[0] == "eckig" for f in nb) > len(nb) / 2
        th = float(np.median([f[1] for f in nb if f[0] == "eckig"])) if eck else 0.0
        p += ["eckig" if eck else "rund", round(th, 1), round(p[1] / (4 / math.pi) if eck else p[1], 3)]      # [z, halb_sichtbar, n, streuung, form, theta_grad, halbseite_oder_radius]
    erg["profil"] = prof
    erg.update(gueltig=True, grund=None); return erg


def querschnitt(az, h):
    """Sichtbare Halbbreiten h aus Blickrichtungen az (Grad): Quadrat mit Halbseite a und Lage theta zeigt a(|cos(az-theta)|+|sin(az-theta)|) (zwischen a und 1,41 a), ein Kreis immer r.
    -> ('eckig', theta) wenn das Quadratmodell die Streuung um mindestens 40 % besser erklaert UND die Blickrichtungen mind. 30 Grad (mod 90) ueberdecken, sonst ('rund', 0).
    GRENZE (22.11.2026, Schwabentor: offene Laterne als 'rund' gebaut): 'rund' heisst nur 'aus der Silhouette nicht unterscheidbar' - ein Achteck schwankt um 8 % (unter der
    1600-px-Maske), und aus schmalem Blickwinkelbereich (dort 16 von 17 Fotos in 25 Grad) ist keine Periode messbar. Eckenzahl/Pfosten/Haube: tools/laterne_aus_fotos.py
    (Kanten im Inneren der Silhouette, volle Aufloesung) - bauteile.dach_aus_profil nimmt dessen Block 'laterne_foto' vor diesen Ringen."""
    az = np.radians(np.asarray(az, float)); h = np.asarray(h, float)
    if len(h) < 4: return None
    m4 = np.degrees(az) % 90; sp = 90 - max(np.diff(np.r_[np.sort(m4), np.sort(m4)[0] + 90]))           # Ueberdeckung der Blickrichtungen modulo 90 Grad
    rund = float(np.median(np.abs(h - np.median(h)))); best = (np.inf, 0.0)
    for t in np.radians(np.arange(0, 90, 2.0)):
        f = np.abs(np.cos(az - t)) + np.abs(np.sin(az - t)); a = float(np.median(h / f)); e = float(np.median(np.abs(h - a * f)))
        if e < best[0]: best = (e, float(np.degrees(t)))
    return ("eckig", best[1]) if sp >= 30 and best[0] < 0.6 * rund else ("rund", 0.0)


def main(argv=None):
    import cv2, flaeche_ortho as FO, dach_aus_fotos as DA
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--profil"); ap.add_argument("--ueber", type=float, default=6.0); ap.add_argument("--schritt", type=float, default=0.1)
    ap.add_argument("--max-fotos", type=int, default=400); ap.add_argument("--nur-messen", action="store_true"); ap.add_argument("--cache", help="Himmelsmasken-Cache (Standard audit/himmel_cache)")
    ap.add_argument("--neu-masken", action="store_true", help="fehlende Himmelsmasken rechnen (sonst nur Cache)")
    a = ap.parse_args(argv)
    od = os.path.dirname(os.path.abspath(a.objekt)); Au = os.path.join(od, "audit"); pp = a.profil or os.path.join(Au, "dach_profil.json")
    try: D = json.load(open(pp))
    except Exception: print("kein Dachprofil", pp); return 3
    P = D.get("scheiben") or []
    if len(P) < 4: print("Dachprofil ohne Scheiben"); return 3
    o = np.array(D["o"], float); d = np.array(D["d"], float); n = np.array(D["n"], float); cu, cv_ = (D.get("achse_uv") or [0.0, 0.0])
    A = o + cu * d + cv_ * n; z_end = P[-1][0] + float(D.get("schritt", 0.5)); z_lo = (P[0][0] + P[-1][0]) / 2
    zs = np.round(np.arange(z_lo, z_end + a.ueber, a.schritt), 2)
    obj, cams = FO.kameras_laden(a.objekt); cache = a.cache or os.path.join(Au, "himmel_cache")
    print(f"Achse x {A[0]:.2f} y {A[1]:.2f} (Dachprofil), Suche z {z_lo:.1f}..{zs[-1]:.1f}; {len(cams)} Kameras")
    mess = []; gruende = {}; bilder = []
    for nr, (c, pf) in sorted(cams.items())[:a.max_fotos]:
        W0, H0 = int(round(c["cx"] * 2)), int(round(c["cy"] * 2)); wh = c.get("bild")
        if wh: W0, H0 = int(wh[0]), int(wh[1])
        kam = dict(name=nr, W0=W0, H0=H0, foto=pf); M_, s = DA.himmel_laden(kam, cache, nur_cache=not a.neu_masken)
        if M_ is None: gruende["keine Himmelsmaske"] = gruende.get("keine Himmelsmaske", 0) + 1; continue
        s = M_.shape[1] / (c["cx"] * 2) if not wh else s
        proj = projektor(c, s); _, _, C = proj(np.array([[A[0], A[1], z_lo]]))
        z_sp, g, halb = foto_messen(M_, proj, A, zs, C)
        if z_sp is None: gruende[g.split(" (")[0].split(" neben")[0]] = gruende.get(g.split(" (")[0].split(" neben")[0], 0) + 1; continue
        az = math.degrees(math.atan2(C[1] - A[1], C[0] - A[0])); mess.append((nr, az, z_sp, halb, (float(C[2]), float(np.hypot(C[0] - A[0], C[1] - A[1]))))); bilder.append((nr, pf, c, s, z_sp, halb))
    E = auswerten(mess, zs, SEKTOR_GRAD)
    print(f"Fotos mit Spitze: {E['fotos']} aus Sektoren {E['sektoren']}; verworfen: {gruende}")
    E.update(quelle="tools/spitze_aus_umriss.py: Himmelskante der kalibrierten Fotos an der Dachachse (Lage aus dach_profil.json)", achse=[round(float(A[0]), 3), round(float(A[1]), 3)],
             wolke_ende_z=round(z_end, 2), verworfen=gruende, einzel=[[m[0], round(m[1], 1), round(m[2], 2)] for m in mess],
             annahmen=["ANNAHME: Spitze liegt auf der Dachachse (Zelt-/Pyramidenspitze)", "Querschnitt je Hoehe aus der Blickrichtungs-Abhaengigkeit der Halbbreite (Quadrat a(|cos|+|sin|) gegen Kreis); eckig: Halbseite = Median / (4/pi) (ANNAHME: Mittel ueber die Blickrichtungen)",
                       "Knauf/Kreuz/Nadel ueber der Spitze nur so weit, wie die 1600-px-Himmelsmaske sie aufloest"])
    if E.get("gueltig"):
        print(f"SPITZE z {E['spitze_z']} m (Streuung {E['spitze_streuung']} m, Wolke endete bei {z_end:.2f}); Hals z {E.get('hals_z')} halb {E.get('hals_halb')}; Krempe z {E.get('krempe_z')}")
        print("  Profil z:halb(n)form " + " ".join(f"{p[0]:g}:{p[1]:.2f}({p[2]}){p[4][0]}{p[5]:g}" for p in E["profil"][::3]))
    else: print("UNGUELTIG:", E["grund"])
    try: bild(bilder, A, E, os.path.join(Au, "spitze_umriss.jpg"))
    except Exception as e: print("Bild fehlgeschlagen:", e)
    if not a.nur_messen:
        D["spitze_foto"] = E; json.dump(D, open(pp, "w"), indent=1); print("->", pp, "(Block spitze_foto)")
    return 0 if E.get("gueltig") else 4


def bild(bilder, A, E, aus):
    """Pruefbild: bis 6 Fotos ueber den Blickwinkel verteilt (Ausschnitt um die Spitze; gelb Achse, rot gemessene Spitze dieses Fotos, magenta Median, gruen Halbbreiten), rechts Profil."""
    import cv2, flaeche_ortho as FO
    if not bilder: return
    az = [math.atan2(FO.projektion(np.array([[A[0], A[1], 0.0]]), b[2])[2][1] - A[1], FO.projektion(np.array([[A[0], A[1], 0.0]]), b[2])[2][0] - A[0]) for b in bilder]
    o = np.argsort(az); pick = [bilder[o[int(i)]] for i in np.linspace(0, len(o) - 1, min(6, len(o)))]; kacheln = []
    for nr, pf, c, s, z_sp, halb in pick:
        im = cv2.imread(pf)
        if im is None: continue
        sb = im.shape[1] / (c["cx"] * 2); P_ = lambda X: FO.projektion(np.atleast_2d(X), c)[0] * sb
        zl = min(halb) if halb else z_sp - 5; a0 = P_([A[0], A[1], zl - 2])[0]; a1 = P_([A[0], A[1], z_sp + 2])[0]; hpx = abs(a0[1] - a1[1])
        cv2.line(im, tuple(int(v) for v in a0), tuple(int(v) for v in a1), (0, 255, 255), max(1, im.shape[1] // 1500))
        for zz, col in ((z_sp, (0, 0, 255)), (E.get("spitze_z"), (255, 0, 255))):
            if zz is None: continue
            q = P_([A[0], A[1], zz])[0]; cv2.line(im, (int(q[0] - hpx * 0.15), int(q[1])), (int(q[0] + hpx * 0.15), int(q[1])), col, max(1, im.shape[1] // 1200))
        C = FO.projektion(np.array([[A[0], A[1], 0.0]]), c)[2]; b = np.array([A[0] - C[0], A[1] - C[1], 0.0]); b /= np.linalg.norm(b); qd = np.array([-b[1], b[0], 0.0])
        for zz, (h, v) in list(halb.items())[::4]:
            l_ = P_(np.array([A[0], A[1], zz]) + qd * (v - h))[0]; r_ = P_(np.array([A[0], A[1], zz]) + qd * (v + h))[0]
            cv2.circle(im, (int(l_[0]), int(l_[1])), max(2, im.shape[1] // 800), (0, 220, 0), -1); cv2.circle(im, (int(r_[0]), int(r_[1])), max(2, im.shape[1] // 800), (0, 220, 0), -1)
        cxm = (a0[0] + a1[0]) / 2; y0 = int(max(0, a1[1] - 0.15 * hpx)); y1 = int(min(im.shape[0], a0[1] + 0.05 * hpx)); x0 = int(max(0, cxm - 0.5 * hpx)); x1 = int(min(im.shape[1], cxm + 0.5 * hpx))
        k = im[y0:y1, x0:x1]
        if k.size == 0 or k.shape[0] < 10: continue
        k = cv2.resize(k, (max(1, int(k.shape[1] * 400 / k.shape[0])), 400)); cv2.putText(k, f"{nr[-14:]} z {z_sp:.2f}", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1); kacheln.append(k)
    pr = np.full((400, 260, 3), 255, np.uint8); Pf = E.get("profil") or []
    if Pf:
        za = Pf[0][0]; zb = E.get("spitze_z", Pf[-1][0]) + 0.5; hm = max(p[1] for p in Pf) * 1.2
        Y = lambda z: int(380 - (z - za) / max(zb - za, 1e-6) * 360); X = lambda h: int(20 + h / hm * 220)
        for p in Pf: cv2.circle(pr, (X(p[1]), Y(p[0])), 2, (0, 160, 0), -1)
        for k_, col in (("spitze_z", (255, 0, 255)), ("krempe_z", (0, 0, 255)), ("hals_z", (255, 0, 0))):
            if E.get(k_) is not None: cv2.line(pr, (0, Y(E[k_])), (259, Y(E[k_])), col, 1); cv2.putText(pr, f"{k_} {E[k_]}", (120, Y(E[k_]) - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.38, col, 1)
        if E.get("wolke_ende_z") is not None: cv2.line(pr, (0, Y(E["wolke_ende_z"])), (259, Y(E["wolke_ende_z"])), (150, 150, 150), 1)
    cv2.putText(pr, "Halbbreite Foto (m) -> ; grau: Wolkenende", (2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (0, 0, 0), 1)
    out = np.hstack(kacheln + [pr]); cv2.imwrite(aus, out, [cv2.IMWRITE_JPEG_QUALITY, 85]); print("Bild:", aus)


if __name__ == "__main__": sys.exit(main())
