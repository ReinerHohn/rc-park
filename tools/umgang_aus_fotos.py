#!/usr/bin/env python3
"""umgang_aus_fotos.py <objekt.json> <fassade_fein-Ordner> [--aus audit/umgang_auto.json] [--bilder DIR] - OFFENER UMGANG unter der Traufe aus den Fotos (Kettenstufe 'bauplan').

Warum (21.11.2026, Schwabentor-Kette: hand_vergleich 'umgang FEHLT'): das 1-cm-Wandbild (fassade_ortho/fassade_fein) endet unter dem Dachueberstand - das Stufenmodell
verdeckt dort jede Kamera, der Laufgang unter der Traufe kommt im Wandbild nie vor. Darum hier direkt aus den kalibrierten Einzelfotos (K-*.json, Vertrauensregel wie fassade_ortho):
  1. je Hauptwand (Wandoberkante innerhalb 2 m der hoechsten, >= 3 m breit) das Band z_top - BAND .. z_top + 0,6 m jeder Frontkamera auf die Wandebene entzerren (2 cm Zellen);
  2. ZONE = KANTEN: Zeilenprofil des senkrechten Helligkeitsgradienten im Wandmittelteil (Eckquader-Raender aussen vor), je Foto; Median ueber die Fotos.
     Unterkante z0 = staerkste Hell->Dunkel-Kante (von unten gesehen) im Band (Schwelle des Umgangs vor dem Schatten des Ruecksprungs),
     Oberkante z1 = die Wandoberkante, an der das Dach ansetzt (staerkste Kante darueber, hoechstens 3 m ueber z0).
     DURCHBLICK-Probe: zwischen z0 und z1 muss das Bild dunkler sein als die Wand darunter (Schatten der zurueckgesetzten Wand) UND senkrechte Kanten (Pfosten) tragen,
     sonst kein Umgang (Fries/Gesims ohne Ruecksprung).
  3. PFOSTEN ZAEHLEN am entzerrten Band (wie foto_zaehlung, aber automatisch): Spaltenprofil des waagrechten Gradienten in der Zone, Paare (Pfostenkante links/rechts) mit
     Breite 0,1-0,6 m; Zahl je Foto, Ergebnis = Mehrheit ueber >= 2 Fotos je Wand. 24.11.2026: JE WAND gebaut (pfosten_kanten, Zaehlen nur am Foto); die Mehrheit
     ueber die Waende nur fuer Waende ohne eigene Zaehlung (ANNAHME im JSON).
24.11.2026 (Befund Hoehen-Angleich 1122): Entzerrung auf der GESETZTEN Wandlage (audit/schleife_korrekturen.json 'wandversatz', wie der Generator; ohne Eintrag
LoD2-Ebene wie bisher) statt immer auf der LoD2-Ebene (Wand 0,29-0,36 m dahinter -> Zeilen um Versatz x tan(Blickhoehe) zu tief). Der Deckel der Oberkante auf die
LoD2-Wandoberkante faellt nur, wenn triangulierte Fotokanten (Kantenstufe sweep.npz mit Traufzone) die Kante z1 auf der gesetzten Wand belegen (oberkante_belegt).
Ausgabe: audit/umgang_auto.json (z0, z1, pfosten_je_seite, ecken der Wand-Hauptflucht, je Wand/Foto die Einzelwerte) + audit/umgang_auto.jpg (Kontrollbild mit Zone und Pfosten).
Exit 0 = Umgang gefunden, 3 = keiner belegt (JSON mit gefunden=false, Generator baut nichts).
ANNAHMEN (im JSON): Ruecksprungtiefe (kein Foto misst sie; bauteile.umgang Standard 0,9 m), Querschnitte.
"""
import sys, os, json, glob, argparse, numpy as np, cv2

ZELLE = 0.02


def kamera_ok(n, c, mit_tor):
    if n.startswith(("dl_", "neu__")): return bool(c.get("vertrauen"))
    if c.get("buendel_tor", {}).get("ok"): return True
    return (not mit_tor) and not n.startswith("video")


def projizieren(K, X):
    R = cv2.Rodrigues(np.array(K["rvec"], float))[0]; p = X @ R.T + np.array(K["t"], float); z = p[:, 2]
    x = p[:, 0] / z; y = p[:, 1] / z; f_ = 1 + float(K.get("k1") or 0) * (x * x + y * y)
    return K["f_px"] * x * f_ + K["cx"], K["f_px"] * y * f_ + K["cy"], z


def hauptwaende(F_all):
    zt = max(F["z"][1] for F in F_all)
    return [F for F in F_all if F["z"][1] >= zt - 2.0 and F["u"][1] - F["u"][0] >= 3.0]


def band_entzerren(F, K, im, z_lo, z_hi, versatz=0.0):
    """Band der Wand auf die Ebene o + versatz * n entzerren (versatz = gesetzte Wandlage, + = aussen; 0 = LoD2-Ebene wie vor dem 24.11.2026)."""
    o = np.array(F["o"], float) + float(versatz) * np.array(F["n"], float)[:2]; d = np.array(F["d"], float)
    uu = np.arange(F["u"][0], F["u"][1], ZELLE); zz = np.arange(z_hi, z_lo, -ZELLE)
    U, Zg = np.meshgrid(uu, zz); X = np.stack([o[0] + U * d[0], o[1] + U * d[1], Zg], -1).reshape(-1, 3)
    mx, my, zc = projizieren(K, X); H, W = im.shape[:2]
    ok = (zc > 0.5) & (mx >= 0) & (mx < W - 1) & (my >= 0) & (my < H - 1)
    b = cv2.remap(im, mx.reshape(U.shape).astype(np.float32), my.reshape(U.shape).astype(np.float32), cv2.INTER_AREA if False else cv2.INTER_LINEAR, borderValue=(0, 0, 0))
    return b, ok.reshape(U.shape), uu, zz


def wandlage(F, korrekturen_json, z):
    """GESETZTE Wandlage der Fassade (m, + = aussen) aus audit/schleife_korrekturen.json (tools/wandlage_fotokanten.py: Fotokanten-Ebene + Wolke bestaetigt),
    gleiche Zuordnung wie der Generator (bauteile.wandversatz_fassade, Hoehenbereich z). Ohne belegten Eintrag 0 = LoD2-Ebene (Fallback wie bisher).
    24.11.2026 (Befund Hoehen-Angleich 1122): entzerrt auf der LoD2-Ebene, die Wand liegt 0,29-0,36 m dahinter -> jede Zeile im Foto um Versatz x tan(Blickhoehe)
    zu tief (bei 60 Grad 0,6 m), die Einzelfotos streuten z1 36,46..37,32."""
    try:
        import bauteile as BT
        return float(BT.wandversatz_fassade(korrekturen_json, np.array(F["o"], float), F["n"], z=z))
    except Exception: return 0.0


KANTE_MIN_PUNKTE, KANTE_DECKUNG, KANTE_REFS, KANTE_TOL = 20, 0.5, 3, 0.15   # wie traufe_aus_fotos.stirn_aus_kanten (Linie ueber die Wand, Formfamilie >= 3 Fotos)


def oberkante_belegt(P, ref, W, versatz, z1, tol=KANTE_TOL, rand=0.2):
    """Belegen triangulierte FOTOKANTEN (Kantenstufe sweep.npz, seit 24.11. mit Traufzone ueber der Wandoberkante) eine waagrechte Kante in z1 auf der
    gesetzten Wand? Je Hauptwand: Punkte |w - versatz| <= tol, Wandmittelteil, |z - z1| <= 0,1 -> >= KANTE_MIN_PUNKTE, >= 2 x mittlere 0,2-m-Scheibe in z1 +-0,6,
    Deckung >= KANTE_DECKUNG der 0,5-m-Abschnitte, >= KANTE_REFS Referenzfotos. Belegt, wenn mindestens die Haelfte der Hauptwaende zustimmt.
    Liefert (belegt, je Wand dict)."""
    if P is None or not len(P) or not W: return False, []
    erg = []
    for F in W:
        o = np.array(F["o"], float); d = np.array(F["d"], float); n = np.array(F["n"], float)[:2]; u0, u1 = F["u"]; b_ = rand * (u1 - u0)
        q = P[:, :2] - o; w = q @ n - versatz.get(F["id"], 0.0); u = q @ d; ins = (np.abs(w) <= tol) & (u >= u0 + b_) & (u <= u1 - b_)
        k = ins & (np.abs(P[:, 2] - z1) <= 0.1); um = ins & (np.abs(P[:, 2] - z1) <= 0.6); c = int(k.sum()); mittel = float(um.sum()) / 6.0
        ab = np.arange(u0 + b_, u1 - b_ + 1e-9, 0.5); deck = (len(np.unique(np.digitize(u[k], ab))) / max(len(ab) - 1, 1)) if c else 0.0; nref = len(np.unique(np.asarray(ref)[k])) if c else 0
        ok = c >= KANTE_MIN_PUNKTE and c >= 2.0 * mittel and deck >= KANTE_DECKUNG and nref >= KANTE_REFS
        erg.append(dict(id=F["id"], punkte=c, mittel=round(mittel, 1), deckung=round(min(deck, 1.0), 2), refs=nref, belegt=bool(ok)))
    return sum(e["belegt"] for e in erg) >= max(1, (len(W) + 1) // 2), erg


def band_verschiebung(wv, C, o_wand, n, zt, band):
    """Hoehenverschiebung des Bands auf der gesetzten Wand: dieselbe Bildzeile, die auf der LoD2-Ebene z zeigte, zeigt auf der um wv (+ = aussen) versetzten Wand
    z - wv * tan(Blickhoehe). Das Band wird um diesen Betrag (an der Wandoberkante zt) mitgeschoben, damit die Zonen-Suchfenster (Anteile des Bands) denselben
    Bildausschnitt sehen wie bisher - 1122 f00: sonst lag die Umgang-Unterkante (36,3) ueber dem Suchfenster und z0 sprang auf 34,1. Guard: |Verschiebung| <= band/2."""
    hd = float((np.asarray(C, float)[:2] - np.asarray(o_wand, float)[:2]) @ np.asarray(n, float)[:2])
    if wv == 0 or hd <= 0.5: return 0.0
    return float(np.clip(-wv * (zt - float(C[2])) / hd, -band / 2, band / 2))


def zone_aus_band(grau, ok, zz, rand=0.2):
    """Zeilenprofil im Wandmittelteil -> (z0, z1, probe) oder None. grau float 0..1, Zeile 0 = oben."""
    n = grau.shape[1]; a, b = int(n * rand), int(n * (1 - rand))
    g = grau[:, a:b]; m = ok[:, a:b]
    if m.mean() < 0.6: return None
    zeile = np.array([np.median(g[i][m[i]]) if m[i].sum() > 10 else np.nan for i in range(g.shape[0])])
    if np.isnan(zeile).mean() > 0.2: return None
    zeile = np.where(np.isnan(zeile), np.nanmedian(zeile), zeile); s = cv2.GaussianBlur(zeile.reshape(-1, 1).astype(np.float32), (1, 5), 0).ravel()
    dz = s[2:] - s[:-2]                                  # Zeile i+1: >0 = nach unten heller (dunkler Streifen darueber hoert auf)
    unten = int(len(s) * 0.85)                           # untere 15 % = Referenzwand
    ref = float(np.median(s[unten:]))
    # Unterkante: Uebergang dunkel (oben) -> hell (unten): groesstes dz in der unteren Bandhaelfte (oberhalb der Referenz)
    lo, hi = int(len(s) * 0.25), unten
    i0 = lo + int(np.argmax(dz[lo:hi])) + 1
    # Oberkante: oberhalb i0 die staerkste Zeilenkante (Raehm/Dachansatz/Traufe - Untersicht dunkler ODER Himmel heller: Betrag) zwischen i0 - 3 m und i0 - 0,6 m
    j_lo = max(1, i0 - int(3.0 / ZELLE)); j_hi = max(j_lo + 1, i0 - int(0.6 / ZELLE))
    i1 = j_lo + int(np.argmax(np.abs(dz[j_lo:j_hi]))) + 1
    zone = s[i1:i0]
    probe = dict(kante_unten=round(float(dz[i0 - 1]), 3), kante_oben=round(float(dz[i1 - 1]), 3), hell_wand=round(ref, 3), hell_zone=round(float(np.median(zone)), 3))
    return float(zz[i0]), float(zz[i1]), probe


def pfosten_zaehlen(grau, ok, zz, uu, z0, z1, b_max=0.4, rand=0.08):
    """Pfosten vor dem Ruecksprung: im unteren Teil der Zone (z0 + 10 % .. z0 + 45 %: unter Raehm/Oeffnungen der Rueckwand) das Spaltenprofil der Helligkeit,
    SCHMALE dunkle Senken (Black-Hat mit Fensterbreite b_max: breite dunkle Flaechen wie Eckquader der Rueckwand fallen heraus), Hoehe > 4 x MAD.
    Gezaehlt werden die inneren Pfosten (Mittelteil ohne 'rand' je Seite); die Eckpfosten stehen in der dunklen Ecke vor den Eckquadern und sind dort nicht
    trennbar -> + 2 (ANNAHME Eckpfosten, im JSON vermerkt), wenn die Zone bis an beide Wandenden reicht. Liefert (anzahl_mit_ecken, lagen_u_innen)."""
    h = z1 - z0; r = (zz >= z0 + 0.1 * h) & (zz <= z0 + 0.45 * h)
    if r.sum() < 5: return None, []
    g = grau[r]; m = ok[r]
    if m.mean() < 0.6: return None, []
    sp = np.array([np.median(g[:, j][m[:, j]]) if m[:, j].sum() > 3 else np.nan for j in range(g.shape[1])])
    if np.isnan(sp).mean() > 0.2: return None, []
    sp = np.where(np.isnan(sp), np.nanmedian(sp), sp).astype(np.float32)
    k = 2 * int(b_max / ZELLE / 2) + 1
    bh = cv2.morphologyEx(sp.reshape(1, -1), cv2.MORPH_BLACKHAT, np.ones((1, k), np.uint8)).ravel()
    a, b = int(len(bh) * rand), int(len(bh) * (1 - rand)); x = bh[a:b]
    mad = float(np.median(np.abs(x - np.median(x)))) + 1e-3; thr = float(np.median(x)) + max(4 * mad, 0.04)
    L = []; j = 0
    while j < len(x):
        if x[j] > thr:
            e = j
            while e < len(x) and x[e] > thr: e += 1
            u_ = float(uu[a + (j + e - 1) // 2])                                             # Mitte des Abschnitts (Pfostenachse)
            if (e - j) * ZELLE >= 0.04 and not (L and u_ - L[-1] < b_max): L.append(u_)      # Doppelspitze (zwei Kanten desselben Pfostens) = ein Pfosten
            j = e
        else: j += 1
    return len(L) + 2, L


def pfosten_konsens(listen, toleranz=0.25, anteil=0.5):
    """Pfostenlagen mehrerer Fotos derselben Wand: Haeufung (Abstand < toleranz) zaehlt, wenn sie in >= anteil der Fotos (mind. 2) vorkommt
    (Kabel, Laternen, Rueckwand-Quader treffen nur einzelne Fotos). Liefert sortierte Mittellagen."""
    n = len(listen)
    if n < 2: return None
    alle = sorted((u, i) for i, L in enumerate(listen) for u in L); hauf = []
    for u, i in alle:
        if hauf and u - hauf[-1][-1][0] < toleranz: hauf[-1].append((u, i))
        else: hauf.append([(u, i)])
    return [round(float(np.mean([u for u, _ in h])), 2) for h in hauf if len({i for _, i in h}) >= max(2, anteil * n)]


def waende_umlauf(W):
    """Hauptwaende nach Winkel um den Schwerpunkt sortiert (Reihenfolge der Ecken/Kanten im Umlauf)."""
    mitte = np.mean([np.array(F["o"], float) for F in W], axis=0)
    return sorted(W, key=lambda F: np.arctan2(F["o"][1] - mitte[1], F["o"][0] - mitte[0]))


def pfosten_kanten(W, je_wand_zahl, fallback):
    """PFOSTENZAHL JE KANTE des Umlaufs (24.11.2026, Weg-Analyse WEG_HAND_ZU_KETTE: Mehrheit ueber alle Waende gab 2 je Seite, obwohl f00 allein 4 zaehlt -
    Zaehlen nur am Foto). Kante k (Ecke k -> Ecke k+1, ecken_aus_waenden) liegt auf der Wand waende_umlauf(W)[k+1]; sie bekommt die Zahl aus DEREN Fotos
    (pfosten_konsens), nur ohne eigene Zaehlung die Mehrheit 'fallback' (als ANNAHME genannt). Liefert (liste, annahmen)."""
    U = waende_umlauf(W); n = len(U); out = []; ann = []
    for k in range(n):
        F = U[(k + 1) % n]; z = je_wand_zahl.get(F["id"])
        if z is None: out.append(int(fallback)); ann.append(f"ANNAHME: Wand {F['id']} ohne eigene Pfostenzaehlung -> Mehrheit der Waende ({int(fallback)})")
        else: out.append(int(z))
    return out, ann


def ecken_aus_waenden(W):
    """Schnittpunkte aufeinanderfolgender Wandfluchten (nach Winkel um den Schwerpunkt sortiert) = Umgangs-Ecken im Umlauf."""
    W = waende_umlauf(W); E = []
    for A, B in zip(W, W[1:] + W[:1]):
        pa, da = np.array(A["o"], float), np.array(A["d"], float); pb, db = np.array(B["o"], float), np.array(B["d"], float)
        M_ = np.array([da, -db]).T
        if abs(np.linalg.det(M_)) < 0.3: return None    # zwei fast parallele Fluchten nebeneinander - kein geschlossener Umlauf
        s = np.linalg.solve(M_, pb - pa); E.append((pa + s[0] * da).tolist())
    return E


def mehrheit(werte):
    w = [x for x in werte if x is not None]
    if not w: return None, 0
    v, n = np.unique(w, return_counts=True); return int(v[np.argmax(n)]), int(n.max())


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("fein"); ap.add_argument("--aus"); ap.add_argument("--band", type=float, default=5.0)
    ap.add_argument("--max_fotos", type=int, default=6); ap.add_argument("--max_mpp", type=float, default=0.03)
    ap.add_argument("--kanten", help="sweep.npz der Kantenstufe (Standard <daten>/<objekt>/kanten/sweep.npz): Beleg fuer eine Oberkante ueber der LoD2-Wandoberkante")
    ap.add_argument("--korrekturen", help="schleife_korrekturen.json (Standard audit/ des Objekts): gesetzte Wandlage"); a = ap.parse_args()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od)); obj = json.load(open(a.objekt))
    aus = a.aus or os.path.join(od, "audit", "umgang_auto.json"); os.makedirs(os.path.dirname(aus), exist_ok=True)
    F_all = json.load(open(os.path.join(a.fein, "fassaden.json")))["fassaden"]; W = hauptwaende(F_all)
    kams = {}
    for kf in glob.glob(os.path.join(od, "messprotokoll", "K-*.json")):
        c = json.load(open(kf)).get("kamera")
        if isinstance(c, dict) and "rvec" in c and "cx" in c: kams[os.path.basename(kf)[2:-5]] = c
    mit_tor = any("buendel_tor" in c for c in kams.values()); kams = {n: c for n, c in kams.items() if kamera_ok(n, c, mit_tor)}
    fd = obj.get("fotos_dir", ""); fd = fd if os.path.isabs(fd) else os.path.join(root, fd)
    erg = dict(quelle="tools/umgang_aus_fotos.py: Band unter der Traufe aus kalibrierten Einzelfotos auf die Wandebene entzerrt, Zone aus Zeilenkanten, Pfosten aus Spaltenprofil",
               fotos_dir=obj.get("fotos_dir", ""), waende=[], gefunden=False); kontroll = []
    kj = a.korrekturen or os.path.join(od, "audit", "schleife_korrekturen.json"); versatz = {}
    for F in W:
        zt = float(F["z"][1]); z_lo, z_hi = zt - a.band, zt + 0.6; wv = wandlage(F, kj, (z_lo, z_hi)); versatz[F["id"]] = wv
        o = np.array(F["o"], float) + wv * np.array(F["n"], float)[:2]; d = np.array(F["d"], float); nv = np.array([F["n"][0], F["n"][1], 0.0])
        Pm = np.array([o[0] + d[0] * np.mean(F["u"]), o[1] + d[1] * np.mean(F["u"]), zt - 1.0]); kand = []
        for n, K in kams.items():
            R = cv2.Rodrigues(np.array(K["rvec"], float))[0]; C = -R.T @ np.array(K["t"], float); v = C - Pm; dist = float(np.linalg.norm(v)); cw = float(v @ nv / dist)
            if cw < 0.3: continue
            mpp = dist / (K["f_px"] * cw)
            if mpp <= a.max_mpp: kand.append((mpp, n, K, C))
        kand.sort(key=lambda q: q[0]); je = []
        for mpp, n, K, C in kand:
            if len(je) >= a.max_fotos: break
            pf = glob.glob(os.path.join(fd, n + ".*")) or glob.glob(os.path.join(fd, n + "_*"))
            if not pf: continue
            im = cv2.imread(pf[0])
            if im is None: continue
            dz_ = band_verschiebung(wv, C, o, nv[:2], zt, a.band)                         # gleicher Bildausschnitt wie auf der LoD2-Ebene (Zonen-Suchfenster unveraendert)
            b, ok, uu, zz = band_entzerren(F, K, im, z_lo + dz_, z_hi + dz_, wv)
            if ok.mean() < 0.6: continue
            grau = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
            z_ = zone_aus_band(grau, ok, zz)
            if z_ is None: continue
            z0, z1, probe = z_
            npf, lagen = pfosten_zaehlen(grau, ok, zz, uu, z0, z1)
            je.append(dict(foto=n, mpp=round(mpp, 4), z0=round(z0, 2), z1=round(z1, 2), pfosten=npf, pfosten_u=[round(x, 2) for x in lagen], **probe))
            kontroll.append((F["id"], n, b, ok, uu, zz, z0, z1, lagen))
        erg["waende"].append(dict(id=F["id"], z_top=zt, wandlage=round(wv, 3), fotos=je))
    # Konsens: Zone = Median ueber alle Fotos mit Durchblick-Probe (Zone dunkler als Wand), Pfosten = Mehrheit je Wand, dann ueber die Waende
    gut = [f for w in erg["waende"] for f in w["fotos"] if f["hell_zone"] < f["hell_wand"] - 0.05 and f["kante_unten"] > 0.03]
    if len(gut) >= 3:
        z0 = float(np.median([f["z0"] for f in gut])); z1_foto = float(np.median([f["z1"] for f in gut]))
        # Die Traufkante steht 'Ueberstand' vor der Wand; von unten gesehen faellt sie auf der Wandebene HOEHER ab -> Oberkante hoechstens die Wandoberkante (Traufe) des Modells.
        # 24.11.2026: der LoD2-Deckel gilt nur noch, wenn keine triangulierten Fotokanten eine Kante in z1_foto AUF der gesetzten Wand belegen (dann ist es der Raehm,
        # nicht die vorstehende Traufkante; Kantenstufe mit Traufzone). Ohne sweep.npz / ohne Beleg: Deckel wie bisher.
        deckel = max(float(F["z"][1]) for F in W); z1 = min(z1_foto, deckel); erg["z1_foto"] = round(z1_foto, 2)
        if z1_foto > deckel + 0.02:
            kp = a.kanten
            if not kp:
                import pfade; kp = os.path.join(pfade.DATEN, os.path.basename(od), "kanten", "sweep.npz")
            try: Zk = np.load(kp); Pk, Rk = Zk["P"].astype(float), Zk["ref"]
            except Exception: Pk, Rk = None, None
            bel, je_k = oberkante_belegt(Pk, Rk, W, versatz, z1_foto); erg["oberkante_kanten"] = dict(datei=kp, belegt=bel, waende=je_k)
            if bel: z1 = z1_foto; erg["oberkante_quelle"] = "Fotokanten der Kantenstufe auf der gesetzten Wand (ueber der LoD2-Wandoberkante, kein Deckel)"
            else: erg["oberkante_quelle"] = f"LoD2-Deckel {deckel:.2f} (Fotokanten belegen z1_foto {z1_foto:.2f} nicht)"
        je_wand = []
        for w in erg["waende"]:
            fz = [f for f in w["fotos"] if f in gut and abs(f["z0"] - z0) < 0.4]
            lagen = pfosten_konsens([f["pfosten_u"] for f in fz if f["pfosten"] is not None])
            if lagen is None: continue
            w["pfosten_u_konsens"] = lagen; w["pfosten"] = len(lagen) + 2; w["pfosten_fotos"] = len(fz); je_wand.append(w["pfosten"])
        p, np_ = mehrheit(je_wand)
        E = ecken_aus_waenden(W)
        if p is not None and p >= 2 and E and z1 - z0 >= 0.6:
            pk, ann_k = pfosten_kanten(W, {w["id"]: w["pfosten"] for w in erg["waende"] if w.get("pfosten") is not None and w["pfosten"] >= 2}, p)
            erg.update(gefunden=True, z0=round(z0, 2), z1=round(z1, 2), pfosten_je_seite=p, pfosten_waende=np_, pfosten_kanten=pk, ecken=[[round(x, 3) for x in e] for e in E], fotos_gut=len(gut),
                       annahmen=["Ruecksprungtiefe 0,9 m (kein Foto misst sie; bauteile.umgang Standard)", "Querschnitte Pfosten 0,24 m, Schwelle/Raehm 0,25 m",
                                 "Pfostenzahl je Kante aus den Fotos DIESER Wand (pfosten_kanten); pfosten_je_seite = Mehrheit nur Anzeige/Fallback"] + ann_k)
        else: erg["grund"] = f"Pfostenzahl ohne Mehrheit (je Wand {je_wand}) oder keine Ecken/Zone zu schmal"
    else: erg["grund"] = f"nur {len(gut)} Fotos mit Durchblick-Probe (Zone dunkler als Wand + Kante an der Schwelle), mindestens 3 noetig"
    json.dump(erg, open(aus, "w"), indent=1, ensure_ascii=False)
    if kontroll:                                         # Kontrollbild: je Foto das entzerrte Band, Zone (gelb), Konsens (gruen), Pfosten (rot)
        zeilen = []
        for fid, n, b, ok, uu, zz, z0_, z1_, lagen in kontroll[:12]:
            c = b.copy(); c[~ok] = 0; H_ = c.shape[0]
            zi = lambda z: int(np.clip(np.searchsorted(-zz, -z), 0, H_ - 1))
            for z_, col in ((z0_, (0, 255, 255)), (z1_, (0, 255, 255))): cv2.line(c, (0, zi(z_)), (c.shape[1], zi(z_)), col, 1)
            if erg["gefunden"]:
                for z_ in (erg["z0"], erg["z1"]): cv2.line(c, (0, zi(z_)), (c.shape[1], zi(z_)), (0, 255, 0), 1)
            for u_ in lagen: j_ = int((u_ - uu[0]) / ZELLE); cv2.line(c, (j_, zi(z1_)), (j_, zi(z0_)), (0, 0, 255), 2)
            c = cv2.resize(c, (600, int(600 * c.shape[0] / c.shape[1])))
            cv2.putText(c, f"{fid} {n[-24:]}", (5, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1); zeilen.append(c)
        pad = max(z.shape[0] for z in zeilen)
        zeilen = [cv2.copyMakeBorder(z, 0, pad - z.shape[0], 0, 0, cv2.BORDER_CONSTANT) for z in zeilen]
        if len(zeilen) % 2: zeilen.append(np.zeros_like(zeilen[0]))
        cv2.imwrite(os.path.splitext(aus)[0] + ".jpg", np.vstack([np.hstack(zeilen[i:i + 2]) for i in range(0, len(zeilen), 2)]))
    print(f"umgang: gefunden={erg['gefunden']}" + (f" z {erg['z0']}..{erg['z1']}, {erg['pfosten_je_seite']} Pfosten je Seite ({erg['fotos_gut']} Fotos)" if erg["gefunden"] else f" - {erg.get('grund')}"))
    for w in erg["waende"]: print(" ", w["id"], "z_top", w["z_top"], [(f["foto"][-12:], f["z0"], f["z1"], f["pfosten"], f["hell_zone"], f["hell_wand"]) for f in w["fotos"]])
    return 0 if erg["gefunden"] else 3


if __name__ == "__main__":
    sys.exit(main())
