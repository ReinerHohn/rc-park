#!/usr/bin/env python3
"""foto_tor_bezug.py - FOTO-TOR MIT BEZUGSSTAND: entscheidet je Foto und je Fassade "besser / schlechter / gleich als der zuletzt abgenommene Stand".

Warum (Messreihe 17.11.2026, Kopf von tools/foto_diff.py): absolute Kennzahlen (Anteil Modellkanten ohne Foto, Treffer-F1) ueberlappen fuer gutes Modell,
schlechtes Modell und falsches Fotopaar - keine feste Schwelle trennt. Nur der PAARVERGLEICH auf demselben Foto traegt. Dieses Werkzeug macht daraus ein Tor:

  1. Bezugsstand je Foto (--bezug_setzen): Rohmasken des abgenommenen Modells aus foto_diff.py (Raster, GPU, Schnellweg _RUECK nur_masken):
     Modellkanten (Knick/Sprung + Umriss), Fotokanten, Silhouette, Verdecker (Tiefenkarte), Fassadenlabel (Normalenrichtung N/O/S/W/Dach, ANNAHME y = Nord),
     dazu dmed (Medianabstand) -> audit/fototor_bezug.json + Masken unter /media/oem/scan/rc-park_daten/fototor_bezug/<objekt>/<foto>.npz.
  2. Neuer Lauf: dasselbe Foto mit FESTEM dmed aus dem Bezug (gleiche Glaettung -> gleiche Fotokanten; vorher aenderte ein anderes Modell die Fotokanten).
  3. Mass = gekappte SYMMETRISCHE Chamfer-Distanz in px / Kappe (tol 0,35 m): Mittel ueber Modellkanten des Abstands zur naechsten Fotokante
     + Mittel ueber Fotokanten des Abstands zur naechsten Modellkante, beide auf --tol gekappt (0 = deckungsgleich, 2 = nichts passt).
     Bewertet nur im GEMEINSAMEN Bereich: Vereinigung beider Silhouetten + --rand m, ohne Verdecker beider Staende (gleicher Bereich fuer beide = fairer Vergleich).
  4. SITZ-TOR je Foto: sitzt KEINER der beiden Staende in diesem Foto (eine globale Bildverschiebung um <= 1 m senkt die Kosten um >= --sitz_max = 4 %,
     foto_diff.versatz_schaetzen), ist die Kamera schlechter als die zu beurteilende Aenderung -> "nicht beurteilbar (sitzt nicht)". Messung 17.11.: Fotos, in denen
     der Bezug nicht sitzt, hatten 2-10 von 18 Vorzeichen falsch, sitzende 0-6. Symmetrisch (einer von beiden genuegt), damit ein schlechter Bezug nicht jede
     Verbesserung als "nicht beurteilbar" sperrt.
  5. Je Foto: gepaartes Bootstrapping ueber Kacheln (--kachel m) -> 95-%-Intervall der Differenz neu - Bezug; "schlechter" nur, wenn das Intervall > 0 UND
     Differenz > --min_diff (umgekehrt "besser"), sonst "gleich". Zu wenige Kanten = "nicht beurteilbar".
  6. GESAMT (und je Fassade): Mittel der Differenzen ueber die beurteilbaren Fotos, Bootstrapping UEBER FOTOS (5/95 %); "schlechter" nur, wenn die untere Grenze > 0
     UND das Mittel > --pool_floor (Rauschgrenze, s. u.), umgekehrt "besser"; weniger als --min_fotos beurteilbare Fotos = "nicht beurteilbar".
     Grund: je Foto traegt das Vorzeichen nur zu ~90 % (Kamerafehler), die Signifikanz je Foto nur zu ~65 %; erst das Mittel ueber Fotos trennt (Nachweis).
  RAUSCHGRENZE (Nachweis 17.11.2026, tools/test_foto_tor_bezug.py, schwab_v3, 15 Fotos, davon 8-11 je Fall beurteilbar): Wiederholung gleiches Modell = 0
     (bitgleich); 2 cm / 5 cm seitlich: Mittel -0,0004 / +0,0004 -> pool_floor 0,005 (0,2 m seitlich = 0,010-0,034). Je Foto: Bootstrap-Halbbreite Median 0,044.
  ERGEBNIS des Nachweises: deutliche Faelle (>= 0,5 m, Massstab 2 %, falsche Kamera, schwab_auto) je Richtung 22 von 24 richtig, 0 falsche Richtung
     (verfehlt: Hoehe +0,5 m -> "gleich"; Hoehe ist schwach, auch nur waagerechte Kanten helfen nicht); alle Faelle ab 0,2 m 30/36, 2-5 cm 6/6 "gleich".
     Mit nur 6 Fotos 84 % (falsche Richtung <= 2,4 %) -> moeglichst 10-15 Fotos pruefen. Je Foto: Vorzeichen 83 %, signifikant 58 %.
     JE FASSADE nur HINWEIS (fassade_floor 0,02): 58 % richtig, 5 von 167 falsche Richtung, 0 Fehlalarme bei 2-5 cm - fuer rot zaehlt nur das Gesamturteil.
Exit 0 = nicht schlechter (gleich/besser/uneinheitlich), 3 = BELEGTE VERSCHLECHTERUNG (nicht 1: das ist ein Absturz), 2 = NICHT BEURTEILBAR (kein Bezug - auch wenn er gerade angelegt wurde -, zu wenige beurteilbare Fotos).
Bild je Foto: audit/fototor_<foto>.jpg (Kacheln rot = schlechter, gruen = besser; magenta = Bezugs-, cyan = neue Modellkanten).
Nachweis: tools/test_foto_tor_bezug.py (Wiederholung, Versatz 0,2/0,5/1 m, Massstab 2 %, falsches Fotopaar, schwab_v3 gegen schwab_auto).
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/foto_tor_bezug.py modelle/<objekt>/objekt.json --fotos a,b,c [--bilder_dir D] [--stl X]
      [--bezug_setzen | --setzen_wenn_ok] [--aus bericht.json]
"""
import sys, os, json, glob, time, hashlib, argparse, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATEN = "/media/oem/scan/rc-park_daten/fototor_bezug"
FASSADE = {1: "N", 2: "O", 3: "S", 4: "W", 5: "Dach"}
STANDARD = dict(tol=0.35, rand=1.0, kachel=1.5, min_diff=0.01, n_boot=400, min_px=300, min_kacheln=6, sitz_max=0.04, pool_floor=0.005, fassade_floor=0.02, min_fotos=3)   # Herkunft der Zahlen: Kopf (RAUSCHGRENZE, SITZ-TOR)


def messen(objekt, nr, bild=None, stl=None, dmed_fix=None, modell_trafo=None):
    """Rohmasken eines Stands (Modell + Kamera aus objekt/messprotokoll/K-<nr>.json) auf Bild `bild` (Standard fotos_dir/<nr>.*).
    modell_trafo = dict(d=[dx,dy,dz] m, s=Massstab, p=Drehpunkt [m]) - NUR Nachweis: Modell X' = p + s (X - p) + d, gleichwertig als Kamera t' = (R((1-s)p + d) + t) / s
    gerechnet (Bild identisch bis auf Tiefeneinheit; spart je Variante ein 120-MB-STL auf der vollen Datenplatte)."""
    import foto_diff as FD
    argv = [objekt, nr] + (["--bild", bild] if bild else []) + (["--stl", stl] if stl else [])
    FD._RUECK = {"nur_masken": True, **({"dmed_fix": float(dmed_fix)} if dmed_fix else {})}
    alt = FD.FF.kamera_laden
    if modell_trafo:
        d_ = np.asarray(modell_trafo.get("d", [0, 0, 0]), float); s_ = float(modell_trafo.get("s", 1.0)); p_ = np.asarray(modell_trafo.get("p", [0, 0, 0]), float)
        def _kl(*x, **k):
            R, t, f, q, z = alt(*x, **k); R = np.asarray(R, float); return R, (R @ ((1 - s_) * p_ + d_) + np.asarray(t, float)) / s_, f, q + f" +Modelltrafo {modell_trafo}", z
        FD.FF.kamera_laden = _kl
    try:
        FD.main(argv); m = FD._RUECK.get("masken")
    finally: FD._RUECK = None; FD.FF.kamera_laden = alt
    if m is None: raise RuntimeError(f"foto_diff lieferte keine Masken fuer {nr}")
    m["lab"] = fassaden_label(m["nrm"], m["sil"]); del m["nrm"]; m["sitz"] = sitz(m)
    return m


def sitz_sperre(sb, sn, p=None):
    """True = Foto nicht beurteilbar: weder Bezug noch neuer Stand sitzen (Kopf, Punkt 4)."""
    p = {**STANDARD, **(p or {})}; g = [x.get("gewinn") for x in (sb or {}, sn or {}) if x.get("gewinn") is not None]
    return bool(g) and min(g) >= p["sitz_max"]


def sitz(m, ppm=None):
    """Sitzt der Stand in diesem Foto? Globale Bildverschiebung (+-1 m, foto_diff.versatz_schaetzen, GPU wenn da) im Bereich Silhouette + 1 m.
    gewinn = relative Kostensenkung durch die beste Verschiebung (0 = sitzt)."""
    import foto_diff as FD
    ppm = ppm or m["ppm"]; inner = cv2.dilate(m["sil"].astype(np.uint8), np.ones((int(2 * ppm) | 1,) * 2, np.uint8)) > 0
    f_ = FD._versatz_gpu if FD._cuda() else FD.versatz_schaetzen
    try: v = f_(m["mk"], m["fk"], inner, ppm, 1.0 / ppm, weite_m=1.0)
    except RuntimeError: v = FD.versatz_schaetzen(m["mk"], m["fk"], inner, ppm, 1.0 / ppm, weite_m=1.0)
    return dict(gewinn=v.get("gewinn"), versatz_m=v.get("versatz_m"), versatz_px=v.get("versatz_px"))


def fassaden_label(nrm, sil):
    """Fassade je Pixel aus der (zur Kamera gedrehten) Normalen: Dach (nz > 0,5) sonst Himmelsrichtung der waagerechten Normalen; ausserhalb der Silhouette
    das Label des naechsten Silhouettenpixels (Fotokanten im Randband gehoeren zur angrenzenden Fassade)."""
    n = nrm.astype(np.float32); az = (np.degrees(np.arctan2(n[..., 0], n[..., 1])) + 360.0) % 360.0
    lab = np.where(az >= 315, 1, np.where(az >= 225, 4, np.where(az >= 135, 3, np.where(az >= 45, 2, 1)))).astype(np.uint8)
    lab[n[..., 2] > 0.5] = 5; lab[~sil | (np.abs(n).sum(2) < 1e-3)] = 0
    if not (lab > 0).any(): return lab
    _, L = cv2.distanceTransformWithLabels((lab == 0).astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    werte = lab[lab > 0]                                                                     # Nullpixel des Quellbilds (= lab > 0) in Zeilenreihenfolge, Label 1..n
    return werte[np.clip(L - 1, 0, len(werte) - 1)].astype(np.uint8)


def _sha(p, n=1 << 20):
    if not p or not os.path.exists(p): return None
    h = hashlib.sha1(); st = os.stat(p); h.update(f"{st.st_size}".encode())
    with open(p, "rb") as fh: h.update(fh.read(n))
    return h.hexdigest()[:16]


def _kachel_summen(s, M, kap, kpx, lab):
    """je Kachel (und Fassade) Summen der gekappten Abstaende und Anzahlen: Modell->Foto (A) und Foto->Modell (B)."""
    H, W = M.shape; nx = (W + kpx - 1) // kpx; ny = (H + kpx - 1) // kpx; nk = nx * ny
    dF = np.minimum(cv2.distanceTransform((~s["fk"]).astype(np.uint8), cv2.DIST_L2, 5), kap)
    dM = np.minimum(cv2.distanceTransform((~s["mk"]).astype(np.uint8), cv2.DIST_L2, 5), kap)
    kid = (np.arange(H) // kpx)[:, None] * nx + (np.arange(W) // kpx)[None, :]; key = lab.astype(np.int64) * nk + kid; nkey = 6 * nk
    mA = s["mk"] & M; mB = s["fk"] & M
    return dict(sA=np.bincount(key[mA], dF[mA], nkey), nA=np.bincount(key[mA], None, nkey).astype(float),
                sB=np.bincount(key[mB], dM[mB], nkey), nB=np.bincount(key[mB], None, nkey).astype(float), nk=nk,
                dF_m=dF[mA], dM_m=dM[mB])


def _kosten(S, kap, w=None):
    """Kosten aus Kachelsummen (w = Bootstrap-Gewichte, Form (n_boot, n_kachel))."""
    if w is None: return (S["sA"].sum() / max(1, S["nA"].sum()) + S["sB"].sum() / max(1, S["nB"].sum())) / kap
    return ((w @ S["sA"]) / np.maximum(1, w @ S["nA"]) + (w @ S["sB"]) / np.maximum(1, w @ S["nB"])) / kap


def vergleichen(b, n, p=None, seed=0):
    """Bezug b gegen neuen Stand n (Masken-dicts). Rueckgabe dict je Foto mit gesamt + je Fassade."""
    p = {**STANDARD, **(p or {})}
    if b["mk"].shape != n["mk"].shape: return dict(urteil="nicht beurteilbar", grund=f"Bildgroesse {b['mk'].shape} != {n['mk'].shape}")
    ppm = b.get("ppm") or n["ppm"]; kap = max(1.0, p["tol"] * ppm); kpx = max(16, int(round(p["kachel"] * ppm)))
    r = int(2 * p["rand"] * ppm) | 1
    M = (cv2.dilate((b["sil"] | n["sil"]).astype(np.uint8), np.ones((r, r), np.uint8)) > 0) & ~(b["occ"] | n["occ"])
    Sb = _kachel_summen(b, M, kap, kpx, b["lab"]); Sn = _kachel_summen(n, M, kap, kpx, b["lab"])
    nk = Sb["nk"]; rng = np.random.default_rng(seed); erg = dict(ppm=round(ppm, 2), kappe_px=round(kap, 1), kachel_px=kpx, bereich_px=int(M.sum()))
    mpp = 1.0 / ppm
    def urteil(sel):
        S1 = {k: Sb[k][sel] for k in ("sA", "nA", "sB", "nB")}; S2 = {k: Sn[k][sel] for k in ("sA", "nA", "sB", "nB")}
        akt = (S1["nA"] + S1["nB"] + S2["nA"] + S2["nB"]) > 0; S1 = {k: v[akt] for k, v in S1.items()}; S2 = {k: v[akt] for k, v in S2.items()}
        nkach = int(akt.sum()); px = [int(S1["nA"].sum()), int(S1["nB"].sum()), int(S2["nA"].sum()), int(S2["nB"].sum())]
        e = dict(kacheln=nkach, kanten_px=dict(bezug_modell=px[0], bezug_foto=px[1], neu_modell=px[2], neu_foto=px[3]))
        if nkach < p["min_kacheln"] or min(px) < p["min_px"]:
            e.update(urteil="nicht beurteilbar", grund=f"zu wenig Kanten/Kacheln (Kacheln {nkach} < {p['min_kacheln']} oder Kantenpixel {min(px)} < {p['min_px']})"); return e
        k1, k2 = _kosten(S1, kap), _kosten(S2, kap)
        w = np.stack([np.bincount(rng.integers(0, nkach, nkach), minlength=nkach) for _ in range(p["n_boot"])]).astype(float)
        d = _kosten(S2, kap, w) - _kosten(S1, kap, w); lo, hi = np.percentile(d, [2.5, 97.5]); dd = k2 - k1
        u = "schlechter" if (lo > 0 and dd > p["min_diff"]) else ("besser" if (hi < 0 and dd < -p["min_diff"]) else "gleich")
        e.update(kosten_bezug=round(float(k1), 5), kosten_neu=round(float(k2), 5), diff=round(float(dd), 5), ki95=[round(float(lo), 5), round(float(hi), 5)], urteil=u,
                 a_bezug=round(float(S1["sA"].sum() / max(1, S1["nA"].sum()) / kap), 4), a_neu=round(float(S2["sA"].sum() / max(1, S2["nA"].sum()) / kap), 4),
                 b_bezug=round(float(S1["sB"].sum() / max(1, S1["nB"].sum()) / kap), 4), b_neu=round(float(S2["sB"].sum() / max(1, S2["nB"].sum()) / kap), 4))
        return e
    alle = np.ones(6 * nk, bool); g = urteil(alle)
    for nm, S in (("bezug", Sb), ("neu", Sn)):                                                   # robuste Zusatzwerte (Median / 90 %) in m, nur Bericht
        if len(S["dF_m"]) and len(S["dM_m"]): g[f"chamfer_m_{nm}"] = dict(modell_med=round(float(np.median(S["dF_m"])) * mpp, 3), modell_q90=round(float(np.quantile(S["dF_m"], 0.9)) * mpp, 3),
                                                                         foto_med=round(float(np.median(S["dM_m"])) * mpp, 3), foto_q90=round(float(np.quantile(S["dM_m"], 0.9)) * mpp, 3))
    erg.update(g); erg["fassaden"] = {}
    for l, nm in FASSADE.items():
        sel = np.zeros(6 * nk, bool); sel[l * nk:(l + 1) * nk] = True; erg["fassaden"][nm] = urteil(sel)
    erg["_kacheln"] = (Sb, Sn, kpx, kap)
    return erg


def bild(pfad, im, b, n, e):
    """Foto gedimmt, Kacheln nach Differenz eingefaerbt, Kanten beider Staende; halbe Groesse."""
    Sb, Sn, kpx, kap = e["_kacheln"]; H, W = b["mk"].shape; nx = (W + kpx - 1) // kpx; ny = (H + kpx - 1) // kpx; nk = nx * ny
    def je(S): s = S["sA"].reshape(6, nk).sum(0) + S["sB"].reshape(6, nk).sum(0); c = S["nA"].reshape(6, nk).sum(0) + S["nB"].reshape(6, nk).sum(0); return s, c
    s1, c1 = je(Sb); s2, c2 = je(Sn); d = (s2 / np.maximum(1, c2) - s1 / np.maximum(1, c1)) / kap; ok = (c1 > 20) & (c2 > 20)
    o = (im.astype(np.float32) * 0.45)
    for k in np.nonzero(ok & (np.abs(d) > 0.05))[0]:
        y0, x0 = (k // nx) * kpx, (k % nx) * kpx; col = np.array([0, 0, 255] if d[k] > 0 else [0, 200, 0], np.float32); a_ = min(0.6, abs(d[k]) * 2)
        o[y0:y0 + kpx, x0:x0 + kpx] = o[y0:y0 + kpx, x0:x0 + kpx] * (1 - a_) + col * a_
    o = o.astype(np.uint8); k3 = np.ones((3, 3), np.uint8)
    o[cv2.dilate(b["mk"].astype(np.uint8), k3) > 0] = (255, 0, 255); o[cv2.dilate(n["mk"].astype(np.uint8), k3) > 0] = (255, 255, 0)
    t = f"{e.get('urteil')} diff {e.get('diff')} KI {e.get('ki95')} | " + " ".join(f"{k}:{v.get('urteil', '')[:6]}" for k, v in e.get("fassaden", {}).items() if v.get("urteil") != "nicht beurteilbar")
    o = cv2.resize(o, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA); cv2.putText(o, t, (10, 34), 0, 0.8, (0, 0, 0), 5); cv2.putText(o, t, (10, 34), 0, 0.8, (255, 255, 255), 2)
    cv2.imwrite(pfad, o, [cv2.IMWRITE_JPEG_QUALITY, 85])


def gesamt(fotos_erg, p=None, seed=0):
    """Gesamturteil (und je Fassade) aus dem Mittel der Foto-Differenzen, Bootstrapping ueber Fotos (Kopf, Punkt 6)."""
    p = {**STANDARD, **(p or {})}; rng = np.random.default_rng(seed)
    def pool(es, floor):
        es = [e for e in es if e and e.get("urteil") in ("besser", "schlechter", "gleich") and e.get("diff") is not None]
        z = dict(beurteilbar=len(es), schlechter=sum(e["urteil"] == "schlechter" for e in es), besser=sum(e["urteil"] == "besser" for e in es), gleich=sum(e["urteil"] == "gleich" for e in es))
        if len(es) < p["min_fotos"]: return dict(urteil="nicht beurteilbar", grund=f"{len(es)} beurteilbare Fotos < {p['min_fotos']}", **z)
        d = np.array([e["diff"] for e in es]); b = d[rng.integers(0, len(d), (2000, len(d)))].mean(1); lo, hi = np.percentile(b, [5, 95]); m = float(d.mean())
        u = "schlechter" if (lo > 0 and m > floor) else ("besser" if (hi < 0 and m < -floor) else "gleich")
        return dict(urteil=u, mittel_diff=round(m, 5), ki90=[round(float(lo), 5), round(float(hi), 5)], vorzeichen_plus=int((d > 0).sum()), **z)
    g = pool(list(fotos_erg.values()), p["pool_floor"])
    g["fassaden"] = {nm: pool([e.get("fassaden", {}).get(nm) for e in fotos_erg.values() if e.get("urteil") != "nicht beurteilbar"], p["fassade_floor"]) for nm in FASSADE.values()}   # nur HINWEIS (Kopf)
    return g


def _speichern(npz, m):
    os.makedirs(os.path.dirname(npz), exist_ok=True); tmp = npz + ".tmp.npz"
    np.savez_compressed(tmp, **{k: np.packbits(m[k]) for k in ("mk", "fk", "sil", "occ")}, lab=m["lab"], shape=np.array(m["mk"].shape)); os.replace(tmp, npz)


def _laden(npz):
    z = np.load(npz); sh = tuple(z["shape"]); n = sh[0] * sh[1]
    return {**{k: np.unpackbits(z[k])[:n].reshape(sh).astype(bool) for k in ("mk", "fk", "sil", "occ")}, "lab": z["lab"]}


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--fotos", required=True, help="Fotonummern (ohne Endung), Komma")
    ap.add_argument("--bilder_dir", help="Bilder <dir>/<foto>.* statt fotos_dir"); ap.add_argument("--stl", help="anderes STL als neuer Stand (Versuch)")
    ap.add_argument("--bezug_setzen", action="store_true", help="aktuellen Stand als Bezug speichern (ohne Vergleich)")
    ap.add_argument("--setzen_wenn_ok", action="store_true", help="nach Vergleich: Bezug fuer Fotos ohne Bezug anlegen; bei Gesamturteil nicht 'schlechter' alle Bezuege auf den neuen Stand")
    ap.add_argument("--aus"); ap.add_argument("--keine_bilder", action="store_true"); ap.add_argument("--audit", help="Versuch: Ordner fuer Bezug, Bilder, Masken statt audit/ + Datenplatte")
    for k, v in STANDARD.items(): ap.add_argument("--" + k, type=type(v), default=v)
    a = ap.parse_args(argv); p = {k: getattr(a, k) for k in STANDARD}
    obj = json.load(open(a.objekt)); name = os.path.basename(os.path.dirname(os.path.abspath(a.objekt)))
    aud = a.audit or os.path.join(ROOT, obj.get("audit", os.path.dirname(obj["masstabelle"]) + "/audit")); os.makedirs(aud, exist_ok=True)
    mdir = os.path.join(a.audit, "masken") if a.audit else os.path.join(DATEN, name)
    bj = os.path.join(aud, "fototor_bezug.json"); B = json.load(open(bj)) if os.path.exists(bj) else {"fotos": {}}
    stl = a.stl or os.path.join(ROOT, obj["stl"]); fotos = [f for f in a.fotos.split(",") if f]
    def bildpfad(nr):
        for d in ([a.bilder_dir] if a.bilder_dir else []) + [os.path.join(ROOT, obj["fotos_dir"])]:
            g = sorted(glob.glob(os.path.join(d, nr + ".*")) + glob.glob(os.path.join(d, nr + "_*")))
            if g: return g[0]
        try: return (__import__("pfade").foto_aus_k(json.load(open(os.path.join(os.path.dirname(os.path.abspath(a.objekt)), "messprotokoll", f"K-{nr}.json"))).get("kamera")) or [None])[0]   # 28.11.2026: Zusatzfotos (kameras_zusatz.py)
        except (OSError, ValueError): return None
    erg = dict(objekt=name, zeit=time.strftime("%Y-%m-%d %H:%M"), stl=os.path.relpath(stl, ROOT), parameter=p, fotos={}); neu_m = {}
    for nr in fotos:
        t0 = time.time(); bp = bildpfad(nr); eb = B["fotos"].get(nr); npz = os.path.join(mdir, nr + ".npz")
        if bp is None: erg["fotos"][nr] = dict(urteil="nicht beurteilbar", grund="Bild nicht gefunden"); continue
        hat_bezug = bool(eb and os.path.exists(npz) and not a.bezug_setzen)
        try: m = messen(a.objekt, nr, bp, stl, dmed_fix=eb["dmed"] if hat_bezug else None)
        except (Exception, SystemExit) as ex: erg["fotos"][nr] = dict(urteil="nicht beurteilbar", grund=f"Messung gescheitert: {str(ex)[:160]}"); continue
        neu_m[nr] = (m, bp)
        if not hat_bezug:
            erg["fotos"][nr] = dict(urteil="nicht beurteilbar", grund="kein Bezugsstand" if not a.bezug_setzen else "Bezug gesetzt", sekunden=round(time.time() - t0, 1)); continue
        if abs(m["dmed"] - eb["dmed"]) > 1e-6: erg["fotos"][nr] = dict(urteil="nicht beurteilbar", grund="dmed nicht uebernommen"); continue
        bz = _laden(npz); st = eb.get("sitz") or sitz(bz, eb["ppm"])
        e = vergleichen(bz, m, p); e["sekunden"] = round(time.time() - t0, 1); e["sitz_bezug"] = st; e["sitz_neu"] = m.get("sitz")
        if sitz_sperre(st, m.get("sitz"), p) and e.get("urteil") != "nicht beurteilbar":
            e["urteil_roh"] = e["urteil"]; e["urteil"] = "nicht beurteilbar"; e["grund"] = f"kein Stand sitzt in diesem Foto (Bezug: Verschiebung {st.get('versatz_m')} m senkt die Kosten um {100 * (st.get('gewinn') or 0):.0f} %, neu: {100 * ((m.get('sitz') or {}).get('gewinn') or 0):.0f} %, Grenze {100 * p['sitz_max']:.0f} %): Kamera- oder Modellfehler groesser als die Aenderung"
        e["kamera_gleich"] = (_sha(m["kamera_datei"]) == eb.get("kamera_sha")); e["bezug_zeit"] = eb.get("zeit")
        if not a.keine_bilder:
            im = cv2.imread(bp)
            if im is not None:
                import foto_diff as FD, fehlteile_finden as FF                                        # Masken liegen im entzerrten Bild (foto_diff: skalieren + k1)
                try:
                    K_ = json.load(open(m["kamera_datei"])); im, K_ = FD.foto_skalieren(im, K_); im, _ = FF.foto_entzerren(im, K_.get("kamera", {}))
                except Exception: pass
            if im is not None and im.shape[:2] == m["mk"].shape: bild(os.path.join(aud, f"fototor_{nr}.jpg"), im, bz, m, e)
        e.pop("_kacheln", None); erg["fotos"][nr] = e
        fz = " ".join(f"{k}:{v['urteil']}" for k, v in e["fassaden"].items() if v.get("urteil") != "nicht beurteilbar")
        print(f"  {nr}: {e['urteil']:17s} (Sitz {st.get('gewinn')}) Kosten {e.get('kosten_bezug')} -> {e.get('kosten_neu')} (diff {e.get('diff')}, KI95 {e.get('ki95')}) | {fz} | {e['sekunden']} s", flush=True)
    erg["gesamt"] = gesamt(erg["fotos"], p); u = erg["gesamt"]["urteil"]
    setzen = a.bezug_setzen or a.setzen_wenn_ok
    if setzen:
        for nr, (m, bp) in neu_m.items():
            if a.bezug_setzen or u in ("gleich", "besser") or nr not in B["fotos"]:
                if not a.bezug_setzen and u == "schlechter": continue
                _speichern(os.path.join(mdir, nr + ".npz"), m)
                B["fotos"][nr] = dict(bild=os.path.relpath(bp, ROOT), dmed=m["dmed"], ppm=m["ppm"], sitz=m.get("sitz"), kamera_datei=os.path.relpath(m["kamera_datei"], ROOT), kamera_sha=_sha(m["kamera_datei"]),
                                      stl=os.path.relpath(stl, ROOT), stl_sha=_sha(stl), zeit=erg["zeit"], npz=os.path.join(mdir, nr + ".npz"))
        B["parameter"] = p; tmp = bj + ".tmp"; json.dump(B, open(tmp, "w"), indent=1, ensure_ascii=False); os.replace(tmp, bj); erg["bezug_geschrieben"] = sorted(neu_m)
    json.dump(erg, open(a.aus or os.path.join(aud, "fototor_vergleich.json"), "w"), indent=1, ensure_ascii=False)
    gf = " ".join(f"{k}:{v['urteil']}" for k, v in erg["gesamt"]["fassaden"].items() if v["urteil"] != "nicht beurteilbar")
    print(f"foto_tor_bezug {name}: GESAMT {u} (Mittel {erg['gesamt'].get('mittel_diff')}, KI90 {erg['gesamt'].get('ki90')}; je Foto {erg['gesamt'].get('schlechter')} schlechter / {erg['gesamt'].get('besser')} besser / {erg['gesamt'].get('gleich')} gleich von {erg['gesamt'].get('beurteilbar')} beurteilbaren) | Fassaden {gf}", flush=True)
    return erg


if __name__ == "__main__":
    import gpu_slot; gpu_slot.belegen("foto_tor_bezug")
    e = main(); u = e["gesamt"]["urteil"]
    sys.exit(3 if u == "schlechter" else (2 if u == "nicht beurteilbar" else 0))      # 2 auch nach Anlage des Bezugs: kein Urteil ist kein Bestanden
