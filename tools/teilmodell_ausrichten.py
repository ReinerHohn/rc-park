#!/usr/bin/env python3
"""teilmodell_ausrichten.py <hauptmodell-sparse> <teilmodelle-ordner> [--ausrichtung SFM-AUSRICHTUNG.json] [--min_gemeinsam 4]
       teilmodell_ausrichten.py --tor <teilmodelle>/ausrichtung.json [--modell 0]   (Nachtkette: rc 0 = ausgerichtet, 3 = UNSICHER/UNAUSGERICHTET, Grund auf stdout)

Teilmodelle aus tools/handy_teilmodell.py ins HAUPTMODELL einpassen: gemeinsame Bilder (in beiden mit Pose) -> Aehnlichkeitsabbildung (Umeyama) der Kamerazentren,
RANSAC gegen falsche Paare. Meldet je Teilmodell: gemeinsame Bilder, Inlier, Massstab, mittlerer Rest in m (Hauptmodell-Einheit, mit --ausrichtung auch Modellmeter).
Ein Teilmodell ohne genug gemeinsame Bilder (< --min_gemeinsam) bleibt UNAUSGERICHTET (keine Lage geraten).

QUALITAETSTOR (27.11.2026, einpassung_guete): status "ausgerichtet" nur wenn ALLE Bedingungen halten, sonst "UNSICHER: <Gruende mit Zahlen>":
  (a) mittlerer Rest der Anker / RMS-Radius der Anker-Kamerazentren <= REST_REL_MAX,
  (b) genug Anker (>= MIN_ANKER, Inlier-Anteil >= MIN_ANTEIL), nicht auf einer Linie (LINIE_MIN), Teilmodell reicht nicht weit ueber die Anker (HEBEL_MAX),
  (c) Median Drehfehler je Ankerbild (Hauptmodell-Drehung gegen eingepasste Teilmodell-Drehung) <= DREH_MAX_GRAD.
  ANLASS: 27.11. Handy-Teilmodell 0 (634 Bilder, 324 gemeinsam) hiess "ausgerichtet" bei Rest 1,43 m (max 8,8 m); die Nachtkette rechnete die dichte Wolke darauf;
  die Spur-Einpassung (lage-bruecke: tools/teilmodell_spuren_einpassen.py) zeigte spaeter: Steg 1 m zu hoch (DOM1), Massstab +1,7 %.
  Herkunft der Schwellen: Doku/projekt/foto-sfm/teilmodell_qualitaetstor.md. Schreibt <n>_ausgerichtet/ NUR bei "ausgerichtet", sonst <n>_unsicher/ (zum Ansehen);
  ein alter <n>_ausgerichtet/ aus frueheren Laeufen wird nicht geloescht - massgeblich ist status in ausrichtung.json (Tor --tor).
Verwandt: tools/handy_teilmodell.py, tools/kameras_nachtragen.py (Umeyama gemeinsame Bilder -> Modellrahmen), tools/teilmodell_spuren_einpassen.py (Zweig lage-bruecke,
direkte 3D-Spuren), modelle/METHODE_SEITEN_SFM.md. Test: tools/test_teilmodell_qualitaetstor.py."""
import os, sys, json, argparse
import numpy as np

# Schwellen: Herleitung aus drei echten Einpassungen (26.11. Teil 0 gut, Teil 2 und 27.11. Teil 0 schlecht), siehe Doku/projekt/foto-sfm/teilmodell_qualitaetstor.md
REST_REL_MAX = 0.025    # gut 0,016 | schlecht 0,042 / 0,050 -> geometrisches Mittel gut/bester-schlechter 0,026, abgerundet
DREH_MAX_GRAD = 0.6     # gut 0,28 | schlecht 1,38 / 1,66 Grad -> geometrisches Mittel 0,62, abgerundet
HEBEL_MAX = 3.0         # ANNAHME: kein belegter Extrapolationsfall (gemessen 1,39-2,10; 26.11. Teil 3 mit 5 Ankern 6,9) - Wert dazwischen
MIN_ANKER = 8           # ANNAHME: Sim3 hat 7 Freiheitsgrade; darunter keine Ueberbestimmung je Freiheitsgrad
MIN_ANTEIL = 0.5        # ANNAHME wie tools/sim3_robust.py MIN_ANTEIL
LINIE_MIN = 0.1         # ANNAHME: zweite/erste Hauptachse der Anker; auf einer Linie ist die Drehung um die Linie frei (gemessen 0,47-0,77)


def umeyama(A, B):
    """s, R, t mit B ~ s R A + t."""
    ma, mb = A.mean(0), B.mean(0); a, b = A - ma, B - mb
    U, S, Vt = np.linalg.svd(b.T @ a / len(A)); D = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0: D[2, 2] = -1
    R = U @ D @ Vt; s = np.trace(np.diag(S) @ D) / ((a ** 2).sum() / len(A)); t = mb - s * R @ ma
    return s, R, t


def ransac(A, B, iters=500, tol=None, rng=None):
    """rng je Aufruf neu (frueher gemeinsamer Standard-Generator -> Ergebnis hing von der Aufrufreihenfolge ab: 294 vs 295 Inlier)."""
    rng = np.random.default_rng(0) if rng is None else rng
    n = len(A); best = None
    if tol is None: tol = 0.05 * np.linalg.norm(B.max(0) - B.min(0)) + 1e-9
    for _ in range(iters):
        i = rng.choice(n, 3, replace=False); s, R, t = umeyama(A[i], B[i])
        if not np.isfinite(s) or s <= 0: continue
        e = np.linalg.norm((s * (R @ A.T)).T + t - B, axis=1); inl = e < tol
        if best is None or inl.sum() > best[0].sum(): best = (inl, s, R, t)
    if best is None: return None
    inl = best[0]; s, R, t = umeyama(A[inl], B[inl]); e = np.linalg.norm((s * (R @ A[inl].T)).T + t - B[inl], axis=1)
    return inl, s, R, t, e


def einpassung_guete(A, B, inl, s, R, t, m_je_einheit=1.0, rot_teil=None, rot_haupt=None, teil_punkte=None):
    """Qualitaetstor einer Einpassung X_haupt = s R X_teil + t (wiederverwendbar).
    A/B: Kamerazentren der gemeinsamen Bilder (Teil-/Hauptrahmen), inl: Inlier-Maske, m_je_einheit: Meter je Haupteinheit,
    rot_teil/rot_haupt: (n,3,3) cam_from_world-Drehungen derselben Bilder (optional; ohne = Bedingung (c) nicht pruefbar -> UNSICHER),
    teil_punkte: (k,3) Teilmodell-Punkte im TEILrahmen (optional; ohne = Hebel aus allen A). -> dict(status, gruende, kennzahlen)."""
    A = np.asarray(A, float); B = np.asarray(B, float); inl = np.asarray(inl, bool); m = float(m_je_einheit)
    T = lambda X: (s * (np.asarray(R) @ np.asarray(X, float).T)).T + t
    Bi = B[inl]; n = int(inl.sum()); k = {"anker": n, "gemeinsam": len(A), "inlier_anteil": round(n / max(len(A), 1), 3)}
    gr = []
    if n < 3: return {"status": "UNSICHER: weniger als 3 Anker", "gruende": ["anker < 3"], "kennzahlen": k}
    cen = Bi.mean(0); radius = float(np.sqrt(((Bi - cen) ** 2).sum(1).mean())) * m
    e = np.linalg.norm(T(A[inl]) - Bi, axis=1) * m
    sv = np.linalg.svd(Bi - cen, full_matrices=False)[1]; linie = float(sv[1] / max(sv[0], 1e-12))
    P = T(teil_punkte) if teil_punkte is not None and len(teil_punkte) else T(A)
    hebel = float(np.percentile(np.linalg.norm(P - cen, axis=1), 90) * m / max(radius, 1e-12))
    k.update(anker_radius_m=round(radius, 3), rest_mittel_m=round(float(e.mean()), 3), rest_median_m=round(float(np.median(e)), 3),
             rest_rel=round(float(e.mean()) / max(radius, 1e-12), 4), linie=round(linie, 3), hebel_p90=round(hebel, 2))
    if n < MIN_ANKER: gr.append(f"zu wenige Anker {n} < {MIN_ANKER}")
    if n / max(len(A), 1) < MIN_ANTEIL: gr.append(f"Inlier-Anteil {n / len(A):.2f} < {MIN_ANTEIL}")
    if k["rest_rel"] > REST_REL_MAX: gr.append(f"Rest {k['rest_mittel_m']:.2f} m = {k['rest_rel']:.3f} der Anker-Ausdehnung ({radius:.1f} m) > {REST_REL_MAX}")
    if linie < LINIE_MIN: gr.append(f"Anker fast auf einer Linie ({linie:.3f} < {LINIE_MIN})")
    if hebel > HEBEL_MAX: gr.append(f"Extrapolation: Teilmodell reicht {hebel:.1f}x Anker-Radius (p90) > {HEBEL_MAX}")
    if rot_teil is not None and rot_haupt is not None:
        Rt = np.asarray(rot_teil, float)[inl]; Rh = np.asarray(rot_haupt, float)[inl]
        D = np.einsum("nij,jk,nlk->nil", Rh, np.asarray(R), Rt)        # Rh @ R @ Rt^T = Identitaet bei perfekter Einpassung
        w = np.degrees(np.arccos(np.clip((np.trace(D, axis1=1, axis2=2) - 1) / 2, -1, 1)))
        k["dreh_median_grad"] = round(float(np.median(w)), 3); k["dreh_p90_grad"] = round(float(np.percentile(w, 90)), 2)
        if k["dreh_median_grad"] > DREH_MAX_GRAD: gr.append(f"Drehfehler je Bild Median {k['dreh_median_grad']:.2f} Grad > {DREH_MAX_GRAD}")
    else: gr.append("Drehfehler nicht pruefbar (keine Drehungen)")
    return {"status": "ausgerichtet" if not gr else "UNSICHER: " + "; ".join(gr), "gruende": gr, "kennzahlen": k}


def tor(pfad, modell="0"):
    """Nachtkette: (rc, text). rc 0 nur bei status 'ausgerichtet'; fehlende Datei/Modell/anderer Status = 3."""
    try: z = json.load(open(pfad))[str(modell)]
    except (OSError, ValueError, KeyError) as ex: return 3, f"UNSICHER: Einpassung {pfad} Modell {modell} nicht lesbar ({type(ex).__name__})"
    st = z.get("status", "?"); return (0 if st == "ausgerichtet" else 3), f"Einpassung Modell {modell}: {st} (Rest {z.get('rest_mittel_m')} m, Massstab {z.get('massstab')})"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("haupt", nargs="?"); ap.add_argument("teil", nargs="?"); ap.add_argument("--ausrichtung"); ap.add_argument("--min_gemeinsam", type=int, default=4)
    ap.add_argument("--tor"); ap.add_argument("--modell", default="0")
    a = ap.parse_args()
    if a.tor: rc, txt = tor(a.tor, a.modell); print(txt); return rc
    if not (a.haupt and a.teil): ap.error("haupt und teil noetig (oder --tor)")
    import pycolmap
    def posen(Rec):
        o = {}
        for i in Rec.images.values():
            if i.has_pose:
                c = i.cam_from_world() if callable(i.cam_from_world) else i.cam_from_world
                o[i.name] = (np.array(i.projection_center()), np.array(c.rotation.matrix()))
        return o
    H = pycolmap.Reconstruction(a.haupt); hp = posen(H)
    sm = 1.0
    if a.ausrichtung: sm = 1.0 / json.load(open(a.ausrichtung))["transformation"]["s"]
    out = {}
    for d in sorted(x for x in os.listdir(a.teil) if x.isdigit()):
        M = pycolmap.Reconstruction(os.path.join(a.teil, d)); mp = posen(M)
        gem = sorted(set(hp) & set(mp)); z = dict(bilder=len(mp), gemeinsam=len(gem), punkte=M.num_points3D())
        if len(gem) < a.min_gemeinsam: z["status"] = f"UNAUSGERICHTET (gemeinsam {len(gem)} < {a.min_gemeinsam})"
        else:
            A = np.array([mp[n][0] for n in gem]); B = np.array([hp[n][0] for n in gem]); r = ransac(A, B)
            if r is None: z["status"] = "UNAUSGERICHTET (RANSAC ohne Loesung)"
            else:
                inl, s, R, t, e = r
                P = np.array([p.xyz for p in M.points3D.values()]) if M.num_points3D() else None
                if P is not None and len(P) > 20000: P = P[np.random.default_rng(0).choice(len(P), 20000, replace=False)]
                g = einpassung_guete(A, B, inl, s, R, t, sm, np.array([mp[n][1] for n in gem]), np.array([hp[n][1] for n in gem]), P)
                z.update(inlier=int(inl.sum()), massstab=float(s), rest_mittel_m=float(e.mean() * sm), rest_max_m=float(e.max() * sm), status=g["status"], guete=g["kennzahlen"])
                M.transform(pycolmap.Sim3d(s, pycolmap.Rotation3d(R), t))
                od = os.path.join(a.teil, d + ("_ausgerichtet" if z["status"] == "ausgerichtet" else "_unsicher")); os.makedirs(od, exist_ok=True); M.write(od)
        out[d] = z; print(d, json.dumps(z, ensure_ascii=False), flush=True)
    json.dump(out, open(os.path.join(a.teil, "ausrichtung.json"), "w"), indent=1, ensure_ascii=False); return 0


if __name__ == "__main__":
    sys.exit(main())
