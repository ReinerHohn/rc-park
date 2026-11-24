#!/usr/bin/env python3
"""konvergenz.py <objekt.json> --lauf ID [--daten DIR] [--lesen DIR] [--fein-json F] [--aus DIR] [--k 5] [--schwelle 0.02] [--trocken]
FESTE, OBJEKTIVE Messgroesse je Seite und Lauf + PLATEAU-Erkennung (Nutzer 24.11.2026: "Augenmass ist doof").

Warum: Jeder Kettenlauf waehlte fuer das Foto-Tor andere Fotos (kam_wahl der Kantenstufe) -> audit/foto_diff_*.json gemischt aus 22.-24.11., keine Seite,
keine Zeitreihe, Laeufe nicht vergleichbar (Lehre NICHTS_GEBRACHT 10.11. Kreis a205314: Tor-Gewinn nur auf GEMEINSAMEN Fotos rechnen).

1. FESTER FOTOSATZ je Seite (audit/konvergenz_fotosatz.json, einmal automatisch gewaehlt, danach NICHT geaendert):
   Seite = Wand des Grundrisses objekt.json rahmen_wand (u0..u1 x v0..v1, z 0..hoehe_m; sonst STL-Huelle) mit Aussennormale +x/-x/+y/-y;
   Name IMMER aus objekt.json seiten_konvention (keine eigene Kompassrechnung, Lehre 24.11.).
   Je K-Datei (messprotokoll/K-*.json, kamera_rahmen.kamera_ok, sfm_guete nicht 'schlecht'): Wand mit groesster Guete
      g = cos(Blick gegen Aussennormale, 3D) x Abdeckung (Anteil eines 9x9-Wandgitters im Bild) x Groesse (Bildanteil der Wand / 0,3, max 1),
      nur Kamera vor der Wand, cos >= cos 40 Grad, Abdeckung >= 0,5. Fuer die besten 4k je Seite Schaerfe (Laplace-Varianz, relativ zum besten);
      Wertung g x Schaerfe(0,2..1); Vielfalt: kein zweites Foto < 3 m und < 15 Grad Blickunterschied zu einem gewaehlten (Videobilder-Dubletten).
   k = 5 je Seite (BEGRUENDUNG): Seitenwert = MEDIAN je Seite; der Median aus 5 haelt 2 ausgefallene/falsche Kameras aus (aus 3 nur 1). Nachweis
      foto_tor_bezug 17.11.: je Foto traegt das Vorzeichen nur zu ~83 %, erst das Mittel ueber Fotos trennt (6 Fotos 84 %, ~10 Fotos 92 %) -> 4 Seiten x 5
      = 20 Fotos im Ganzen; mehr kostet je Foto ~10 s GPU am Kettenende, Seiten mit wenig Fotos (Rueckseite) haben ohnehin selten mehr als 5 gute.
   Pflege: verschwindet ein Foto (K-Datei weg/veraltet/'schlecht', Bild weg, Kamera nicht mehr vor dieser Seite), wird es durch das beste noch nicht
   gewaehlte Foto dieser Seite ersetzt, gemeldet und die Seite in diesem Lauf als BRUCH markiert (Reihe beginnt dort neu). Sonst bleibt der Satz.
2. GROBES F1 je Foto aus foto_diff (Kettenmodus: tools/foto_diff_batch.py auf das End-STL, Ausgabe <daten>/konvergenz/<lauf>/, das Objekt-audit bleibt
   unberuehrt): P = 1 - anteil_modellkanten_ohne_foto, R = 1 - anteil_fotokanten_ohne_modell, F1 = 2PR/(P+R); nicht beurteilbar -> zaehlt nicht.
   Seite = Median der F1 ihrer Fotos; keine beurteilbare Aufnahme -> "kein Beleg" (None, NIE 0).
   GRENZE (ANNAHME): foto_diff bewertet das ganze im Foto sichtbare Modell (bei senkrechtem Blick ueberwiegt die Seite, Nachbarseiten/Dach zaehlen mit);
   tol 0,35 m (= 4 mm H0) -> Feinteile bewegen das grobe F1 kaum, deshalb 3.
3. FEINES F1 je Bauteil (Nachtrag 24.11.): Bauteile + Kamerawahl aus audit/neben_details.json (Stufe neben_details: beste SfM-Kamera je Bauteil), Geometrie
   (Fassadenrahmen o/d/n + u/z/w bzw. Achse/r/z) und Kameras beim ersten Lauf EINGEFROREN. Messung tools/teil_fotoform.py f1_fein (voll aufgeloeste Kanten,
   FEIN_TOL_M 3 cm ueber die Teiltiefe in Pixel; trennt Formfamilien, wo das Haupt-F1 blind war - kanten-messen.md 11.11.) am Bauteil-STL, das aus dem
   End-STL mit neben_details.auswahl ausgeschnitten wird. BELASTBAR nur, wenn die wirksame Aufloesung am Bauteil 2 x rms_px x Abstand / f (Kamerafehler in
   Metern) und 3 cm hoechstens 5 cm ist (Ziel ~5 cm: 0,6 mm H0, unter dem Druckmindestmass 0,8 mm = 7 cm echt - feiner bringt nichts). Fernere Kameras ->
   "fein nicht belastbar (x cm)" -> Fotoauftrag (Nahaufnahme). Seite fein = Median der Bauteile ihrer Fassaden (Normale -> Achse -> seiten_konvention);
   Rundteile (dach_profil) eigene Gruppe "rund".
4. STATUS je Seite (KEIN "fertig"; Nutzer 24.11.: Plateau = Methode erschoepft, nicht Stillstand): Reihe ab dem letzten Bruch, nur Laeufe mit Beleg.
   Gewinn der letzten zwei Laeufe je < Schwelle (grob UND fein, soweit belegt) -> "PLATEAU (Methode erschoepft)" + WO der Restfehler sitzt (groesste
   FEHLT/FALSCH-Treffer der foto_diff je Bauteil/Zone, Bauteile mit groesstem Fein-Defizit) -> gezielt neue Methode; sonst "steigt";
   letzter Gewinn < -Schwelle -> "faellt (Rueckschritt)"; < 3 belegte Laeufe -> "Reihe zu kurz"; kein Beleg -> "kein Beleg (Datendecke -> Fotoauftrag)".
   SCHWELLE 2 Prozentpunkte (BEGRUENDUNG): gleicher Stand + gleiche Kameras messen bitgleich (foto_tor_bezug-Nachweis 17.11.: Wiederholung = 0); die echte
   Lauf-zu-Lauf-Streuung kommt aus den neu geschaetzten Kameras. Gibt es in der Reihe zwei Laeufe mit gleichem STL-Hash (= gleicher Stand), wird ihre
   Differenz als gemessene Streuung genommen: Schwelle = max(2 pp, 2 x Streuung). Zusaetzlich je Seite die Standardabweichung der F1 ueber die
   Fotos (spreizung_fotos: Lage der Fotos zueinander, KEIN Rauschen - der Gewinn wird deshalb GEPAART je Foto gerechnet, siehe gewinn()).
5. VERLUST WOLKE -> MODELL je Seite (Nachtrag 24.11., tools/konvergenz_wolke.py): dieselben Fotos, dieselbe foto_diff-Kantenlogik fuer die DICHTE WOLKE der
   Kette (Punkte + PCA-Normalen, Splat/Tiefentest des Punktrenders) und gepaart fuer das Modell in derselben Punktfassung; Bewertungsbereich, dmed und
   Verdecker vom Modell -> f1_wolke, f1_modell_gleich, verlust = f1_wolke - f1_modell_gleich (Median je Foto), status_wolke "Modellierung verliert" /
   "Daten fehlen" / "Modell besser als Wolke" / "gleich" (Schwellen ANNAHME mit Begruendung dort). --ohne-wolke schaltet ab; --lesen liest
   DIR/konvergenz_wolke.json, sonst <quelle>/konvergenz_wolke.json.
6. FORMSITZ (Nachtrag 24.11. abends, tools/formsitz.py; MESSFEHLER: das grobe F1 lag am Schwabentor je Seite nur 0,00-0,16 ueber Zufall = blind fuer den
   Formsitz): Tiefen-IoU Modell gegen dichte Wolke aus denselben Kameras (|dz| < 25 cm), Zufall = Modell 1,3/2,1 m verschoben, Trennschaerfe = Wolkenhaelfte
   gegen Wolkenhaelfte minus deren Zufall (was ein perfektes Modell hier ueber Zufall laege). Felder formsitz, formsitz_null, formsitz_trennschaerfe,
   formsitz_relativ, formsitz_trennt, med_dz, a10, a25, kontur. ER ERSETZT DAS GROBE F1 IM URTEIL: status = steigt/PLATEAU/faellt aus der formsitz-Reihe
   (+ fein wie bisher), aber NUR wenn formsitz_trennt; sonst "nicht trennbar (Zufallsniveau)" (kein PLATEAU). Ohne Formsitz (keine Wolke, --ohne-formsitz)
   bleibt das alte Urteil aus dem groben F1 mit HINWEIS (Rueckfall, nicht trennscharf). --lesen liest DIR/formsitz.json.
Ausgabe: Zeile in audit/konvergenz.jsonl (lauf, zeit, git, stl_sha, je Seite F1 grob/fein + n + Status + Restfehler), Text, audit/konvergenz.png (F1 je
Seite ueber die Laeufe, grob und fein). --lesen DIR: foto_diff_<foto>.json aus DIR statt neu rechnen (Probe/Test); --fein-json: teil_fotoform-Bericht lesen.
--aus DIR: Fotosatz/Reihe/Bild dorthin statt audit/ (Probe ohne Objektordner). --trocken: keine Zeile anhaengen.
Exit 0 = Zeile geschrieben, 1 = Aufruf falsch, 3 = keine Seite mit Beleg (Bericht, kein Kettenfehler).
Umgebung: cv2/numpy (Kettenmodus ruft foto_diff_batch/teil_fotoform mit venv-seg auf): /media/oem/scan/venv-seg/bin/python -I tools/konvergenz.py ...
"""
import sys, os, json, glob, math, time, hashlib, subprocess, argparse
import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HIER)
sys.path.insert(0, HIER)
PY_SEG = "/media/oem/scan/venv-seg/bin/python"
ACHSEN = {"+x": (1.0, 0.0), "-x": (-1.0, 0.0), "+y": (0.0, 1.0), "-y": (0.0, -1.0)}
COS_MIN = math.cos(math.radians(40)); ABD_MIN = 0.5; K_STD = 5; SCHWELLE = 0.02
FEIN_TOL_M = 0.03; FEIN_ZIEL_M = 0.05; FEIN_MIN_PX = 150
PLATEAU = "PLATEAU (Methode erschoepft)"; STEIGT = "steigt"; FAELLT = "faellt (Rueckschritt)"; KURZ = "Reihe zu kurz"
KEIN = "kein Beleg (Datendecke -> Fotoauftrag)"


# ---------------------------------------------------------------- Geometrie
def rodrigues(rv):
    rv = np.asarray(rv, float); th = np.linalg.norm(rv)
    if th < 1e-12: return np.eye(3)
    k = rv / th; Kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(th) * Kx + (1 - math.cos(th)) * Kx @ Kx


def kamera(K):
    """K-Datei-Inhalt -> dict(R, t, C, d (Blickrichtung Welt), f, cx, cy, W, H, rms)."""
    k = K.get("kamera") or K; R = rodrigues(k["rvec"]); t = np.asarray(k["t"], float)
    W, H = (k.get("bild") or [2 * k.get("cx", 1000), 2 * k.get("cy", 750)])[:2]
    return dict(R=R, t=t, C=-R.T @ t, d=R.T @ np.array([0, 0, 1.0]), f=float(k["f_px"]), cx=float(k.get("cx", W / 2)), cy=float(k.get("cy", H / 2)),
                W=float(W), H=float(H), rms=float(k.get("rms_px") or 1.0), guete=((k.get("sfm_guete") or {}).get("klasse")))


def projizieren(cam, X):
    Xc = X @ cam["R"].T + cam["t"]; z = Xc[:, 2]
    with np.errstate(divide="ignore", invalid="ignore"):
        u = cam["f"] * Xc[:, 0] / z + cam["cx"]; v = cam["f"] * Xc[:, 1] / z + cam["cy"]
    return u, v, z


def waende(obj, huelle=None):
    """Vier Waende {achse: dict(name, n, mitte, gitter)}; Rechteck aus rahmen_wand (sonst huelle = (x0, x1, y0, y1, z1)), Namen aus seiten_konvention."""
    rw = obj.get("rahmen_wand") or {}; sk = obj.get("seiten_konvention") or {}
    if all(k in rw for k in ("u0", "u1", "v0", "v1")): x0, x1, y0, y1 = (float(rw[k]) for k in ("u0", "u1", "v0", "v1")); z1 = float(obj.get("hoehe_m") or 20.0)
    elif huelle is not None: x0, x1, y0, y1, z1 = huelle
    else: raise ValueError("weder rahmen_wand noch STL-Huelle - Seiten nicht bestimmbar")
    if obj.get("hoehe_m"): z1 = float(obj["hoehe_m"])
    s = np.linspace(0.05, 0.95, 9); out = {}
    for ax, (nx, ny) in ACHSEN.items():
        if nx: xw = x1 if nx > 0 else x0; P = [[xw, y0 + a * (y1 - y0), b * z1] for a in s for b in s]
        else: yw = y1 if ny > 0 else y0; P = [[x0 + a * (x1 - x0), yw, b * z1] for a in s for b in s]
        P = np.array(P); out[ax] = dict(name=str(sk.get(ax, ax)).split()[0], n=np.array([nx, ny, 0.0]), mitte=P.mean(0), gitter=P)
    return out


def wand_guete(cam, w):
    """(g, cos, abdeckung, groesse) der Kamera fuer Wand w; g = 0, wenn die Kamera nicht vor der Wand steht oder zu schraeg/zu wenig sieht."""
    vor = float((cam["C"] - w["mitte"]) @ w["n"]); cosb = float(-cam["d"] @ w["n"])
    if vor <= 0.5 or cosb < COS_MIN: return 0.0, cosb, 0.0, 0.0
    u, v, z = projizieren(cam, w["gitter"]); im = (z > 0.5) & (u >= 0) & (u < cam["W"]) & (v >= 0) & (v < cam["H"]); abd = float(im.mean())
    if abd < ABD_MIN: return 0.0, cosb, abd, 0.0
    pu, pv = u[im], v[im]; flaeche = (pu.max() - pu.min()) * (pv.max() - pv.min()) / (cam["W"] * cam["H"])
    gr = float(min(1.0, flaeche / 0.3)); return cosb * abd * gr, cosb, abd, gr


def seite_von(cam, W_):
    best = (None, 0.0, 0, 0, 0)
    for ax, w in W_.items():
        g = wand_guete(cam, w)
        if g[0] > best[1]: best = (ax,) + g
    return best


# ---------------------------------------------------------------- Kandidaten / Fotosatz
def foto_pfad(fotos_dir, nr):
    p = glob.glob(os.path.join(fotos_dir, glob.escape(nr) + ".*")) or glob.glob(os.path.join(fotos_dir, glob.escape(nr) + "_*"))
    return p[0] if p else None


def schaerfe(pfad):
    try:
        import cv2
        im = cv2.imread(pfad, cv2.IMREAD_GRAYSCALE)
        if im is None: return None
        s = 1200.0 / max(im.shape); im = cv2.resize(im, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else im
        h, w = im.shape; im = im[h // 6:5 * h // 6, w // 6:5 * w // 6]
        return float(cv2.Laplacian(im, cv2.CV_64F).var())
    except Exception: return None


def kandidaten(od, obj, W_, fotos_dir):
    """Alle brauchbaren Kameras {foto: dict(achse, g, cos, abd, gr, C, d, rms, f)} (Seite = beste Wand)."""
    mp = os.path.join(od, "messprotokoll"); out = {}
    try: import kamera_rahmen as KR
    except Exception: KR = None
    for kp in sorted(glob.glob(os.path.join(mp, "K-*.json"))):
        nr = os.path.basename(kp)[2:-5]
        try:
            K = json.load(open(kp)); k = K.get("kamera") or {}
            if KR is not None and not KR.kamera_ok(kp, k, mp): continue
            cam = kamera(K)
        except Exception: continue
        if cam["guete"] == "schlecht" or not foto_pfad(fotos_dir, nr): continue
        ax, g, cosb, abd, gr = seite_von(cam, W_)
        if ax is None: continue
        out[nr] = dict(achse=ax, g=round(g, 4), cos=round(cosb, 3), abd=round(abd, 3), gr=round(gr, 3), C=cam["C"].round(2).tolist(),
                       d=cam["d"].round(4).tolist(), rms=cam["rms"], f=cam["f"])
    return out


def _zu_nah(a, b):
    return np.linalg.norm(np.subtract(a["C"], b["C"])) < 3.0 and float(np.dot(a["d"], b["d"])) > math.cos(math.radians(15))


def seite_waehlen(kand, ax, k, fotos_dir, ausser=(), schaerfe_fn=schaerfe):
    """Beste k Fotos einer Seite (Wertung g x Schaerfe, Vielfalt). ausser = schon gewaehlte (nicht nochmal, aber Vielfalt gegen sie)."""
    c = sorted(((nr, e) for nr, e in kand.items() if e["achse"] == ax and nr not in ausser), key=lambda q: -q[1]["g"])[:4 * k + 4]
    sv = {nr: schaerfe_fn(foto_pfad(fotos_dir, nr) or "") for nr, _ in c}; smax = max([v for v in sv.values() if v] or [1.0])
    c = sorted(c, key=lambda q: -(q[1]["g"] * min(1.0, max(0.2, (sv[q[0]] or 0.2 * smax) / smax))))
    gew = [dict(foto=nr2, **kand[nr2]) for nr2 in ausser if nr2 in kand]; out = []
    for nr, e in c:
        if len(out) >= k: break
        if any(_zu_nah(e, q) for q in gew + out): continue
        out.append(dict(foto=nr, **e, schaerfe=round(sv[nr] / smax, 3) if sv[nr] else None))
    return out


def fotosatz_anlegen(kand, W_, k, fotos_dir, lauf, schaerfe_fn=schaerfe):
    S = dict(version=1, angelegt=dict(lauf=lauf, zeit=time.strftime("%Y-%m-%d %H:%M:%S")), k=k,
             k_grund="Median aus 5 haelt 2 falsche Kameras aus; Foto-Tor-Nachweis 17.11.: erst ~10-20 Fotos trennen sicher (4 Seiten x 5)",
             regel="danach NICHT aendern; nur verschwundene/unbrauchbare Fotos ersetzen (Bruch der Reihe)", seiten={}, ersetzungen=[])
    for ax, w in W_.items():
        fo = seite_waehlen(kand, ax, k, fotos_dir, schaerfe_fn=schaerfe_fn)
        S["seiten"][ax] = dict(name=w["name"], fotos=[f["foto"] for f in fo], wahl=[{q: f[q] for q in ("foto", "g", "cos", "abd", "gr", "schaerfe")} for f in fo],
                               serie_ab=lauf, kandidaten=sum(1 for e in kand.values() if e["achse"] == ax))
    return S


def fotosatz_pflegen(S, kand, fotos_dir, lauf, schaerfe_fn=schaerfe):
    """Fehlende/unbrauchbare Fotos ersetzen -> {achse: [ersetzungen]} (leer = Satz unveraendert)."""
    bruch = {}
    for ax, s in S["seiten"].items():
        weg = [nr for nr in s["fotos"] if nr not in kand or kand[nr]["achse"] != ax]
        if not weg: continue
        bleib = [nr for nr in s["fotos"] if nr not in weg]
        neu = seite_waehlen(kand, ax, len(weg), fotos_dir, ausser=tuple(bleib), schaerfe_fn=schaerfe_fn)
        s["fotos"] = bleib + [f["foto"] for f in neu]; s["serie_ab"] = lauf
        e = dict(lauf=lauf, seite=s["name"], weg=[dict(foto=nr, grund="K-Datei/Bild fehlt oder unbrauchbar" if nr not in kand else f"jetzt Seite {kand[nr]['achse']}") for nr in weg],
                 neu=[f["foto"] for f in neu]); S["ersetzungen"].append(e); bruch[ax] = e
    return bruch


# ---------------------------------------------------------------- Feine Bauteile
def bauteile_einfrieren(nd, rahmen, kams_K, W_):
    """neben_details.json + Fassadenrahmen -> {name: dict(gruppe, geo, kameras=[dict(foto, aufloesung_m, belastbar)])}."""
    out = {}
    for b in nd.get("bauteile") or []:
        nm = b.get("name")
        if not nm: continue
        if b.get("art") == "rund":
            geo = dict(art="rund", achse=b["achse"], r=b["r"], z0=b["z"][0], z1=b["z"][1]); gruppe = "rund"
        else:
            fr = rahmen.get(b.get("fassade"))
            if not fr: continue
            geo = dict(art="fassade", fassade=b["fassade"], o=fr["o"], d=fr["d"], n=fr["n"], u0=b["u"][0], u1=b["u"][1], z0=b["z"][0], z1=b["z"][1],
                       w0=b.get("w", [-0.3, 0.3])[0], w1=b.get("w", [-0.3, 0.3])[1])
            n = np.asarray(fr["n"], float); i = int(np.argmax(np.abs(n[:2]))); gruppe = ("+" if n[i] > 0 else "-") + "xy"[i]
        ks = []
        for a in b.get("ansichten") or []:
            if not a or not a.get("foto") or a["foto"] in [q["foto"] for q in ks]: continue
            cam = kams_K.get(a["foto"])
            if cam is None: continue
            mpx = float(a.get("abstand_m") or 0) / cam["f"]; aufl = max(FEIN_TOL_M, 2.0 * cam["rms"] * mpx)
            ks.append(dict(foto=a["foto"], modus=a.get("modus"), m_je_px=round(mpx, 4), aufloesung_m=round(aufl, 3), belastbar=aufl <= FEIN_ZIEL_M))
            if len(ks) >= 2: break
        out[nm] = dict(gruppe=gruppe, seite=W_[gruppe]["name"] if gruppe in W_ else gruppe, geo=geo, kameras=ks)
    return out


def bauteil_kasten(geo, rand=0.5):
    if geo["art"] == "rund":
        a, r = geo["achse"], geo["r"] + rand; return [a[0] - r, a[1] - r, geo["z0"] - rand], [a[0] + r, a[1] + r, geo["z1"] + rand]
    o, d, n = (np.asarray(geo[k], float) for k in ("o", "d", "n"))
    P = np.array([list(o + u * d + w * n) for u in (geo["u0"], geo["u1"]) for w in (geo["w0"], geo["w1"])])
    return [P[:, 0].min() - rand, P[:, 1].min() - rand, geo["z0"] - rand], [P[:, 0].max() + rand, P[:, 1].max() + rand, geo["z1"] + rand]


def teile_schreiben(stl, obj, bt, td):
    """Bauteil-STLs (STL-Einheit) aus dem End-STL ausschneiden (neben_details.auswahl auf der eingefrorenen Geometrie)."""
    import neben_details as ND
    fk = float(obj.get("stl_massstab", 87)) / 1000.0 if obj.get("stl_einheit_mm", True) else 1.0
    T = ND.stl_laden(stl, fk); n = 0
    for nm, e in bt.items():
        g = dict(e["geo"]); g.setdefault("name", nm)
        sel = ND.auswahl(T, g)
        if not sel.any(): continue                                   # teil_fotoform verwirft selbst zu kleine Teile (min_px)
        V = (T[sel] / fk).astype("<f4"); A = np.zeros(len(V), dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])); A["v"] = V
        with open(os.path.join(td, nm + ".stl"), "wb") as fh: fh.write(b"\0" * 80 + np.uint32(len(V)).tobytes() + A.tobytes())
        n += 1
    return n


# ---------------------------------------------------------------- Messgroessen
def f1(p, r):
    return 2 * p * r / (p + r) if p + r > 0 else 0.0


def f1_foto(d):
    """foto_diff-JSON -> F1 oder None (nicht beurteilbar)."""
    if not d or d.get("beurteilbar") is False: return None
    try: return f1(1.0 - float(d["anteil_modellkanten_ohne_foto"]), 1.0 - float(d["anteil_fotokanten_ohne_modell"]))
    except (KeyError, TypeError, ValueError): return None


def median_oder_none(v):
    v = [x for x in v if x is not None]
    return (float(np.median(v)), len(v), float(np.std(v)) if len(v) > 1 else None) if v else (None, 0, None)


def diff_lesen(d, nr):
    for p in (os.path.join(d, f"foto_diff_{nr}.json"), *glob.glob(os.path.join(d, "*", glob.escape(nr), f"foto_diff_{nr}.json"))):
        if os.path.exists(p):
            try: return json.load(open(p)), p
            except Exception: return None, p
    return None, None


def fein_lesen(tf, bt):
    """teil_fotoform-Bericht -> {bauteil: (f1_fein Median ueber die eingefrorenen belastbaren Kameras | None, n, flecken)}."""
    out = {}
    for nm, e in bt.items():
        je = ((tf or {}).get("teile") or {}).get(nm) or {}; v = []; fl = []
        for k in e["kameras"]:
            q = je.get(k["foto"])
            if not k.get("belastbar") or not isinstance(q, dict) or "f1_f" not in q or min(q.get("mkf_px", 0), q.get("fkf_px", 0)) < FEIN_MIN_PX: continue
            v.append(float(q["f1_f"])); fl += [dict(foto=k["foto"], **{a: f_.get(a) for a in ("px", "xyz", "welt") if a in f_}) for f_ in (q.get("gelb") or [])[:3]]
        m = median_oder_none(v); out[nm] = (m[0], m[1], fl)
    return out


def _wert(x):
    return x[0] if isinstance(x, (tuple, list)) else x


def gewinn(a, b):
    """Gewinn von Lauf a nach Lauf b. a/b = Wert oder (Wert, {foto|bauteil: F1}). GEPAART: Median der Differenzen auf den gemeinsam belegten
    Fotos/Bauteilen (Lehre 10.11.: Gewinn nur auf gemeinsamen Fotos; die Fotos eines Satzes liegen 0,28..0,78 auseinander - eine fehlende Aufnahme
    verschoebe den Median sonst um Zehntel); ohne Gemeinsame: Differenz der Mediane."""
    da = a[1] if isinstance(a, (tuple, list)) and len(a) > 1 else {}; db = b[1] if isinstance(b, (tuple, list)) and len(b) > 1 else {}
    gem = [k for k in (db or {}) if (da or {}).get(k) is not None and db[k] is not None]
    if gem: return float(np.median([db[k] - da[k] for k in gem]))
    return _wert(b) - _wert(a)


def status_reihe(werte, schwelle):
    """werte = Eintraege (Wert oder (Wert, Einzelwerte); Wert None = kein Beleg) ab dem letzten Bruch, aeltester zuerst."""
    if not werte or _wert(werte[-1]) is None: return KEIN
    v = [x for x in werte if _wert(x) is not None]
    if len(v) < 3: return KURZ
    g1, g2 = gewinn(v[-3], v[-2]), gewinn(v[-2], v[-1])
    if g2 < -schwelle: return FAELLT
    return PLATEAU if g1 < schwelle and g2 < schwelle else STEIGT


def status_seite(sg, sf):
    """grob/fein-Status -> Seitenstatus. PLATEAU nur, wenn grob flach und fein flach (oder fein ohne Beleg)."""
    if sg == KEIN: return KEIN
    if FAELLT in (sg, sf): return FAELLT
    if STEIGT in (sg, sf): return STEIGT
    if sg == PLATEAU and sf in (PLATEAU, KEIN): return PLATEAU
    return KURZ


EINZEL = {"f1": "fotos", "f1_fein": "bauteile_fein", "formsitz": "fotos_formsitz"}
TRENNT_NICHT = "nicht trennbar (Zufallsniveau)"


def status_mit_formsitz(sform, sf, trennt):
    """Seitenstatus, wenn ein FORMSITZ vorliegt (tools/formsitz.py, Nachtrag 24.11.): er ersetzt das grobe F1 als Formmass, weil das grobe F1 nur 0,00-0,16
    ueber Zufall lag. Trennt der Formsitz auf dieser Seite nicht (Trennschaerfe < TRENN_MIN), gibt es KEIN PLATEAU/steigt-Urteil aus der Form; nur ein
    belegtes feines steigt/faellt bleibt."""
    if not trennt: return sf if sf in (STEIGT, FAELLT) else TRENNT_NICHT
    return status_seite(sform, sf)


def reihe(zeilen, gruppe, feld):
    """Eintraege (Wert, Einzelwerte) einer Gruppe ab dem letzten Bruch (einschliesslich)."""
    v = []
    for z in zeilen:
        e = (z.get("seiten") or {}).get(gruppe)
        if e is None: continue
        if e.get("bruch"): v = []
        v.append((e.get(feld), e.get(EINZEL.get(feld, "")) or {}))
    return v


def streuung(zeilen, gruppe, feld="f1"):
    """Groesster |gepaarter Gewinn| zwischen aufeinanderfolgenden Laeufen mit GLEICHEM STL (= gleicher Stand zweimal gemessen; Unterschied nur aus den
    neu geschaetzten Kameras) oder None."""
    d = []
    for a, b in zip(zeilen, zeilen[1:]):
        ea, eb = (a.get("seiten") or {}).get(gruppe) or {}, (b.get("seiten") or {}).get(gruppe) or {}
        if a.get("stl_sha") and a.get("stl_sha") == b.get("stl_sha") and ea.get(feld) is not None and eb.get(feld) is not None and not eb.get("bruch"):
            d.append(abs(gewinn((ea[feld], ea.get(EINZEL[feld]) or {}), (eb[feld], eb.get(EINZEL[feld]) or {}))))
    return max(d) if d else None


def restfehler(diffs, fotos, bt, gruppe, fein, n=5):
    """WO sitzt der Rest: groesste foto_diff-Treffer der Seitenfotos, je Bauteil-Kasten (sonst Zone 'Wand z~') summiert; Bauteile mit groesstem Fein-Defizit."""
    kaesten = {nm: bauteil_kasten(e["geo"]) for nm, e in bt.items()}; summe = {}
    for nr in fotos:
        for t in (diffs.get(nr) or {}).get("treffer") or []:
            x = t.get("xyz")
            if not x: continue
            ort = next((nm for nm, (lo, hi) in kaesten.items() if all(lo[i] <= x[i] <= hi[i] for i in range(3))), None) or f"Zone z~{5 * round(x[2] / 5):.0f} m"
            art = "FEHLT" if str(t.get("art", "")).startswith("FEHLT") else "FALSCH"; k_ = (ort, art)
            summe[k_] = summe.get(k_, 0.0) + float(t.get("laenge_m") or 0)
    grob = [dict(ort=o, art=a, laenge=round(l, 1)) for (o, a), l in sorted(summe.items(), key=lambda q: -q[1])[:n]]
    fd = sorted(((nm, v[0]) for nm, v in fein.items() if bt[nm]["gruppe"] == gruppe and v[0] is not None), key=lambda q: q[1])[:n]
    ohne = [nm for nm, e in bt.items() if e["gruppe"] == gruppe and not any(k.get("belastbar") for k in e["kameras"])]
    return dict(grob=grob, fein=[dict(bauteil=nm, f1_fein=round(v, 3), defizit=round(1 - v, 3)) for nm, v in fd], fein_nicht_belastbar=ohne[:n])


# ---------------------------------------------------------------- Bild
def kurve(zeilen, gruppen, pfad):
    """Kleine Vielfache: je Seite ein Feld, F1 grob (blau) und fein (orange) ueber die Laeufe; Bruch = senkrechte Strichlinie."""
    import cv2
    n = len(gruppen); sp = 2 if n > 1 else 1; zl = (n + sp - 1) // sp; FW, FH, M = 520, 320, 48
    img = np.full((zl * FH + 40, sp * FW, 3), (251, 252, 252), np.uint8)
    farbe = {"f1": (214, 120, 42), "f1_fein": (52, 104, 235), "f1_wolke": (96, 160, 34), "formsitz": (150, 50, 140)}   # BGR von #2a78d6 / #eb6834 / #22a060 / #8c3296
    cv2.putText(img, "je Seite: blau F1 grob, orange F1 fein, gruen Wolke, violett FORMSITZ (Urteil); Strich = Bruch", (10, 26), 0, 0.5, (40, 40, 40), 1, cv2.LINE_AA)
    for i, (g, name) in enumerate(gruppen):
        x0, y0 = (i % sp) * FW + M, 40 + (i // sp) * FH + 30; w, h = FW - M - 20, FH - 100
        cv2.putText(img, name, (x0, y0 - 10), 0, 0.6, (11, 11, 11), 1, cv2.LINE_AA)
        for yv in (0.0, 0.25, 0.5, 0.75, 1.0):
            yy = int(y0 + h - yv * h); cv2.line(img, (x0, yy), (x0 + w, yy), (225, 225, 225), 1)
            cv2.putText(img, f"{yv:.2f}", (x0 - 40, yy + 4), 0, 0.38, (82, 81, 78), 1, cv2.LINE_AA)
        L = len(zeilen)
        if not L: continue
        xs = [int(x0 + (j + 0.5) * w / L) for j in range(L)]
        for j, z in enumerate(zeilen):
            e = (z.get("seiten") or {}).get(g) or {}
            if e.get("bruch") and j: cv2.line(img, (xs[j] - int(w / L / 2), y0), (xs[j] - int(w / L / 2), y0 + h), (150, 150, 150), 1, cv2.LINE_4)
        for feld, col in farbe.items():
            pts = [(xs[j], int(y0 + h - ((z.get("seiten") or {}).get(g) or {}).get(feld) * h)) if (((z.get("seiten") or {}).get(g) or {}).get(feld) is not None) else None for j, z in enumerate(zeilen)]
            for a, b in zip(pts, pts[1:]):
                if a and b: cv2.line(img, a, b, col, 2, cv2.LINE_AA)
            for p in pts:
                if p: cv2.circle(img, p, 4, col, -1, cv2.LINE_AA)
        if L <= 8:
            for j, z in enumerate(zeilen): cv2.putText(img, str(z.get("lauf", j))[-10:], (xs[j] - 34, y0 + h + 18), 0, 0.35, (82, 81, 78), 1, cv2.LINE_AA)
        st = ((zeilen[-1].get("seiten") or {}).get(g) or {}).get("status", "")
        cv2.putText(img, st[:44], (x0, y0 + h + 40), 0, 0.45, (11, 11, 11), 1, cv2.LINE_AA)
        ez = (zeilen[-1].get("seiten") or {}).get(g) or {}
        if ez.get("status_wolke"): cv2.putText(img, f"Wolke: {ez['status_wolke']} (verlust {ez.get('verlust')})"[:56], (x0, y0 + h + 58), 0, 0.42, (34, 110, 30), 1, cv2.LINE_AA)
    cv2.imwrite(pfad, img)


# ---------------------------------------------------------------- Ablauf
def git_hash():
    try: return subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=10).stdout.strip() or None
    except Exception: return None


def sha(p):
    try: return hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
    except Exception: return None


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--lauf", required=True); ap.add_argument("--daten")
    ap.add_argument("--lesen", help="foto_diff_<foto>.json hier lesen statt rechnen"); ap.add_argument("--fein-json", help="teil_fotoform-Bericht lesen statt rechnen")
    ap.add_argument("--aus"); ap.add_argument("--k", type=int, default=K_STD); ap.add_argument("--schwelle", type=float, default=SCHWELLE)
    ap.add_argument("--trocken", action="store_true"); ap.add_argument("--ohne-fein", action="store_true")
    ap.add_argument("--ohne-wolke", action="store_true"); ap.add_argument("--wolke", help="dichte Wolke (npy, Kamerarahmen) statt der Standardwolke")
    ap.add_argument("--ohne-formsitz", action="store_true")
    a = ap.parse_args(argv)
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt))
    root = os.path.dirname(os.path.dirname(od)); fotos_dir = os.path.join(root, obj.get("fotos_dir", ""))
    audit = os.path.join(root, obj.get("audit") or os.path.relpath(os.path.join(od, "audit"), root)); aus = a.aus or audit; os.makedirs(aus, exist_ok=True)
    stl = os.path.join(root, obj.get("stl") or "-")
    huelle = None
    if not obj.get("rahmen_wand") and os.path.exists(stl):
        import neben_details as ND
        fk = float(obj.get("stl_massstab", 87)) / 1000.0 if obj.get("stl_einheit_mm", True) else 1.0; T = ND.stl_laden(stl, fk).reshape(-1, 3)
        huelle = (T[:, 0].min(), T[:, 0].max(), T[:, 1].min(), T[:, 1].max(), T[:, 2].max() - T[:, 2].min())
    W_ = waende(obj, huelle)
    if not obj.get("seiten_konvention"): print("HINWEIS: objekt.json ohne seiten_konvention - Seiten heissen nach Achsen (+x/-x/+y/-y)")
    kand = kandidaten(od, obj, W_, fotos_dir)
    sp = os.path.join(aus, "konvergenz_fotosatz.json"); bruch = {}
    if os.path.exists(sp):
        S = json.load(open(sp)); bruch = fotosatz_pflegen(S, kand, fotos_dir, a.lauf)
        for e in bruch.values(): print(f"FOTOSATZ ERSETZT ({e['seite']}): {e['weg']} -> {e['neu']} - BRUCH der Reihe ab {a.lauf}")
    else:
        S = fotosatz_anlegen(kand, W_, a.k, fotos_dir, a.lauf); bruch = {ax: dict(neu=True) for ax in S["seiten"]}
        print(f"FOTOSATZ ANGELEGT (fest ab jetzt): " + "; ".join(f"{s['name']} {len(s['fotos'])}" for s in S["seiten"].values()))
    # feine Bauteile einfrieren (erst, wenn neben_details vorliegt)
    ndp = os.path.join(audit, "neben_details.json")
    if "bauteile" not in S and os.path.exists(ndp) and not a.ohne_fein:
        try:
            import neben_details as ND
            kams_K = {}
            for kp in glob.glob(os.path.join(od, "messprotokoll", "K-*.json")):
                try: kams_K[os.path.basename(kp)[2:-5]] = kamera(json.load(open(kp)))
                except Exception: pass
            S["bauteile"] = bauteile_einfrieren(json.load(open(ndp)), ND.fassaden_rahmen(audit, a.daten), kams_K, W_); S["bauteile_ab"] = a.lauf
            for g in set(e["gruppe"] for e in S["bauteile"].values()): bruch.setdefault(g, dict(neu=True))
            print(f"BAUTEILE EINGEFROREN: {len(S['bauteile'])}, davon fein belastbar {sum(1 for e in S['bauteile'].values() if any(k['belastbar'] for k in e['kameras']))}")
        except Exception as ex: print(f"HINWEIS: Bauteile nicht eingefroren ({type(ex).__name__}: {str(ex)[:160]}) - nur grobes F1")
    bt = S.get("bauteile") or {}
    json.dump(S, open(sp + ".tmp", "w"), indent=1, ensure_ascii=False); os.replace(sp + ".tmp", sp)
    satz = sorted({nr for s in S["seiten"].values() for nr in s["fotos"]})
    # --- grob messen / lesen
    if a.lesen: quelle = a.lesen
    else:
        quelle = os.path.join(a.daten or aus, "konvergenz", a.lauf); os.makedirs(quelle, exist_ok=True)
        if satz and os.path.exists(stl):
            r = subprocess.run([PY_SEG, "-W", "ignore", "-I", os.path.join(HIER, "foto_diff_batch.py"), a.objekt, "--aus", quelle, "--stl", f"m={stl}",
                                "--fotos", ",".join(satz), "--modus", "raster", "--threads", "2"], cwd=root, capture_output=True, text=True)
            if r.returncode: print(f"HINWEIS: foto_diff_batch rc {r.returncode}: {(r.stderr or r.stdout)[-300:]}")
    diffs, alt = {}, []
    for nr in satz:
        d, p = diff_lesen(quelle, nr)
        if d is None: continue
        diffs[nr] = d; kp = os.path.join(od, "messprotokoll", f"K-{nr}.json")
        if p and os.path.exists(kp) and os.path.getmtime(kp) > os.path.getmtime(p) + 1: alt.append(nr)
    if alt: print(f"HINWEIS: {len(alt)} foto_diff aelter als ihre K-Datei (Kamera seither neu): {alt[:6]} - Werte gehoeren zu einem frueheren Stand")
    # --- fein messen / lesen
    tf = None
    if bt and a.fein_json and os.path.exists(a.fein_json): tf = json.load(open(a.fein_json))
    elif bt and not a.lesen and os.path.exists(stl) and not a.ohne_fein:
        from pfade import temp_ordner
        td = temp_ordner("konv_teile_"); nt = teile_schreiben(stl, obj, bt, td)
        fot = sorted({k["foto"] for e in bt.values() for k in e["kameras"] if k["belastbar"]}); tfp = os.path.join(quelle, "teil_fotoform.json")
        if nt and fot:
            r = subprocess.run([PY_SEG, "-W", "ignore", "-I", os.path.join(HIER, "teil_fotoform.py"), a.objekt, "--teile_dir", td, "--fotos", ",".join(fot),
                                "--wolke_verdeckung", "aus", "--fein", "an", "--aus", tfp], cwd=root, capture_output=True, text=True)
            if r.returncode: print(f"HINWEIS: teil_fotoform rc {r.returncode}: {(r.stderr or r.stdout)[-300:]}")
            if os.path.exists(tfp): tf = json.load(open(tfp))
    fein = fein_lesen(tf, bt) if bt else {}
    # --- Wolke gegen Modell (Verlust der Modellierung) messen / lesen
    wolke = None; wj = os.path.join(a.lesen or quelle, "konvergenz_wolke.json")
    if not a.ohne_wolke and not a.lesen and satz and os.path.exists(stl):
        try:
            r = subprocess.run([PY_SEG, "-W", "ignore", "-I", os.path.join(HIER, "konvergenz_wolke.py"), a.objekt, "--aus", os.path.join(quelle, "wolke"), "--fotosatz", sp,
                                "--json", wj] + (["--wolke", a.wolke] if a.wolke else []), cwd=root, capture_output=True, text=True, timeout=2400)
            if r.returncode: print(f"HINWEIS: konvergenz_wolke rc {r.returncode}: {(r.stdout + r.stderr)[-300:]}")
        except subprocess.TimeoutExpired: print("HINWEIS: konvergenz_wolke nach 2400 s abgebrochen - kein Wolkenvergleich in diesem Lauf")
    if not a.ohne_wolke and os.path.exists(wj):
        try: wolke = json.load(open(wj))
        except Exception as ex: print(f"HINWEIS: {wj} unlesbar ({ex})")
    # --- Formsitz (Tiefen-IoU Modell gegen dichte Wolke, Nullprobe + Trennschaerfe; tools/formsitz.py, CPU)
    form = None; fj = os.path.join(a.lesen or quelle, "formsitz.json")
    if not a.ohne_formsitz and not a.lesen and satz and os.path.exists(stl):
        try:
            r = subprocess.run([PY_SEG, "-W", "ignore", "-I", os.path.join(HIER, "formsitz.py"), a.objekt, "--fotosatz", sp, "--json", fj, "--bild", os.path.join(aus, "formsitz.jpg")]
                               + (["--wolke", a.wolke] if a.wolke else []), cwd=root, capture_output=True, text=True, timeout=1200, env=dict(os.environ, CUDA_VISIBLE_DEVICES=""))
            if r.returncode: print(f"HINWEIS: formsitz rc {r.returncode}: {(r.stdout + r.stderr)[-300:]}")
        except subprocess.TimeoutExpired: print("HINWEIS: formsitz nach 1200 s abgebrochen - Status ohne Formsitz (Rueckfall grobes F1, nicht trennscharf)")
    if not a.ohne_formsitz and os.path.exists(fj):
        try: form = json.load(open(fj))
        except Exception as ex: print(f"HINWEIS: {fj} unlesbar ({ex})")
    if form is None and not a.ohne_formsitz: print("HINWEIS: kein Formsitz - Status aus grobem F1 (Nullprobe 24.11.: nur 0,00-0,16 ueber Zufall, PLATEAU-Urteil ungeprueft)")
    # --- Zeile
    jp = os.path.join(aus, "konvergenz.jsonl"); zeilen = []
    if os.path.exists(jp):
        for ln in open(jp):
            try: zeilen.append(json.loads(ln))
            except Exception: pass
    Z = dict(lauf=a.lauf, zeit=time.strftime("%Y-%m-%d %H:%M:%S"), git=git_hash(), stl_sha=sha(stl), quelle=quelle, seiten={},
             wolke=(wolke or {}).get("wolke"), wolke_schwellen=(wolke or {}).get("schwellen"))
    gruppen = [(ax, s["name"]) for ax, s in S["seiten"].items()] + ([("rund", "rund")] if any(e["gruppe"] == "rund" for e in bt.values()) else [])
    for g, name in gruppen:
        fo = S["seiten"][g]["fotos"] if g in S["seiten"] else []
        fv = {nr: (round(f1_foto(diffs.get(nr)), 4) if f1_foto(diffs.get(nr)) is not None else None) for nr in fo}
        m, nn, se = median_oder_none(list(fv.values()))
        fb = {nm: v[0] for nm, v in fein.items() if bt[nm]["gruppe"] == g}; mf, nf, _ = median_oder_none(list(fb.values()))
        e = dict(name=name, f1=round(m, 4) if m is not None else None, n=nn, spreizung_fotos=round(se, 4) if se else None, fotos=fv,
                 f1_fein=round(mf, 4) if mf is not None else None, n_fein=nf, bauteile_fein={k: (round(v, 3) if v is not None else None) for k, v in fb.items()},
                 bruch=g in bruch)
        we = ((wolke or {}).get("seiten") or {}).get(g)
        if we:
            e.update(f1_wolke=we.get("f1_wolke"), f1_modell_gleich=we.get("f1_modell_gleich"), verlust=we.get("verlust"), abdeckung_wolke=we.get("abdeckung"),
                     guete_wolke=we.get("guete_wolke"), guete_modell=we.get("guete_modell"), verlust_zufall=we.get("verlust_zufall"),
                     n_wolke=we.get("n"), status_wolke=we.get("status"), fotos_wolke={nr: q.get("w") for nr, q in (we.get("fotos") or {}).items()})
        fe = ((form or {}).get("seiten") or {}).get(g)
        if fe and fe.get("n"):
            e.update(formsitz=fe.get("formsitz"), formsitz_null=fe.get("formsitz_null"), formsitz_guete=fe.get("guete"), formsitz_relativ=fe.get("relativ"),
                     formsitz_trennschaerfe=fe.get("trennschaerfe"), formsitz_decke=fe.get("decke"), formsitz_trennt=bool(fe.get("trennt")), n_formsitz=fe.get("n"),
                     med_dz=fe.get("med_dz"), a10=fe.get("a10"), a25=fe.get("a25"), kontur=fe.get("kontur"), kontur_null=fe.get("kontur_null"),
                     fotos_formsitz=fe.get("fotos") or {})
        Z["seiten"][g] = e
    allf = [v for e in Z["seiten"].values() for v in e["fotos"].values()]; allb = [v[0] for v in fein.values()]
    Z["gesamt"] = dict(f1=median_oder_none(allf)[0], n=median_oder_none(allf)[1], f1_fein=median_oder_none(allb)[0], n_fein=median_oder_none(allb)[1])
    zeilen_neu = zeilen + [Z]
    for g, name in gruppen:
        e = Z["seiten"][g]; st_, stf_ = streuung(zeilen_neu, g, "f1"), streuung(zeilen_neu, g, "f1_fein")
        s_eff = max(a.schwelle, 2 * st_) if st_ is not None else a.schwelle; sf_eff = max(a.schwelle, 2 * stf_) if stf_ is not None else a.schwelle
        sg = status_reihe(reihe(zeilen_neu, g, "f1"), s_eff) if g != "rund" else KEIN
        sf = status_reihe(reihe(zeilen_neu, g, "f1_fein"), sf_eff)
        e.update(status_grob=sg, status_fein=sf, status=status_seite(sg, sf) if g != "rund" else sf, schwelle=round(s_eff, 4), schwelle_fein=round(sf_eff, 4),
                 streuung_gleicher_stand=round(st_, 4) if st_ is not None else None, streuung_fein_gleicher_stand=round(stf_, 4) if stf_ is not None else None)
        if e.get("formsitz") is not None and g != "rund":                                   # Formsitz ersetzt das grobe F1 im Urteil (nur wenn er trennt)
            sto = streuung(zeilen_neu, g, "formsitz"); so_eff = max(a.schwelle, 2 * sto) if sto is not None else a.schwelle
            sform = status_reihe(reihe(zeilen_neu, g, "formsitz"), so_eff) if e["formsitz_trennt"] else TRENNT_NICHT
            e.update(status_formsitz=sform, schwelle_formsitz=round(so_eff, 4), status=status_mit_formsitz(sform, sf, e["formsitz_trennt"]))
        if e["status"] in (PLATEAU, KEIN, TRENNT_NICHT) or e["status"].startswith("faellt"):
            e["restfehler"] = restfehler(diffs, S["seiten"].get(g, {}).get("fotos", []), bt, g, fein)
    if not a.trocken:
        with open(jp, "a") as fh: fh.write(json.dumps(Z, ensure_ascii=False) + "\n")
    try: kurve(zeilen_neu, gruppen, os.path.join(aus, "konvergenz.png"))
    except Exception as ex: print(f"HINWEIS: Kurvenbild nicht geschrieben ({type(ex).__name__}: {ex})")
    # --- Text
    print(f"KONVERGENZ Lauf {a.lauf} ({len(zeilen_neu)} Laeufe in der Reihe, Satz {len(satz)} Fotos, {len(bt)} Bauteile):")
    for g, name in gruppen:
        e = Z["seiten"][g]
        fg = f"grob F1 {e['f1']:.3f} (n {e['n']}" + (f", Fotos streuen +-{e['spreizung_fotos']:.2f}" if e["spreizung_fotos"] else "") + ")" if e["f1"] is not None else "grob: kein Beleg"
        ff = f"fein F1 {e['f1_fein']:.3f} (n {e['n_fein']})" if e["f1_fein"] is not None else "fein: kein Beleg"
        print(f"  {name}: {fg}; {ff} -> {e['status']}" + (" [BRUCH]" if e["bruch"] else ""))
        if e.get("formsitz") is not None:
            print(f"      Formsitz {e['formsitz']:.3f} (Zufall {e['formsitz_null']}, Trennschaerfe {e['formsitz_trennschaerfe']}, relativ {e['formsitz_relativ']}) med|dz| {e['med_dz']} m"
                  f" a25 {e['a25']} kontur {e['kontur']} -> {e['status_formsitz']}")
        if e.get("status_wolke"): print(f"      Wolke F1 {e['f1_wolke']} / Modell (Punktfassung) {e['f1_modell_gleich']} -> verlust {e['verlust']} (ueber Zufall {e.get('verlust_zufall')}), Abdeckung {e['abdeckung_wolke']} (n {e['n_wolke']}): {e['status_wolke']}")
        for q in (e.get("restfehler") or {}).get("grob", [])[:3]: print(f"      Rest grob: {q['art']} {q['ort']} {q['laenge']} m Kante")
        for q in (e.get("restfehler") or {}).get("fein", [])[:3]: print(f"      Rest fein: {q['bauteil']} F1 {q['f1_fein']}")
        if (e.get("restfehler") or {}).get("fein_nicht_belastbar"): print(f"      fein nicht belastbar (Kamera zu fern/ungenau -> Nahaufnahme): {e['restfehler']['fein_nicht_belastbar']}")
    print(f"Reihe: {jp}  Bild: {os.path.join(aus, 'konvergenz.png')}  Fotosatz: {sp}")
    return 0 if any(e["f1"] is not None or e["f1_fein"] is not None for e in Z["seiten"].values()) else 3


if __name__ == "__main__":
    sys.exit(main())
