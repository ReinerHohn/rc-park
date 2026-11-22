#!/usr/bin/env python3
"""neben_details.py <objekt.json> [--daten DIR] [--stl a.stl] [--aus DIR] [--max 24] [--kandidaten 6] [--ohne-verdecker] - je erkanntem Bauteil eine DETAILANSICHT Foto | Modell
aus der dafuer besten SfM-Kamera -> audit/neben_detail_<bauteil>.jpg, Uebersicht audit/neben_details.jpg (Raster), Wahl + Wertung audit/neben_details.json.

Anlass 22.11.2026 (0_DURCHBRUCH_AGENTEN_SCHLEIFE.md, Lehre "Ein Nebenbild reicht nicht"): am festen Nebenbild neben_eigen__IMG_20261106_113231 (Steilblick,
Licht von vorn) waren Vordach-Schweifung und Laterne nicht zu erkennen -> Fehlbefund "Vordach flach, Laterne fehlt", obwohl das Ketten-STL beides hatte
(belegt erst durch Renders aus 4 passenden SfM-Kameras). Befunde je Bauteil gelten erst an einer Detailansicht aus passender Kamera.

Bauteile (generisch, nichts objektbezogen):
  Fassadenzonen  befundliste.bauteil_zonen(audit): alle audit/*_auto.json (vorbauten, oeffnungen, fenster, uhren, ...) + vordach_profil.json mit u/z-Kasten je
                 Fassade fNN; Fassadenrahmen o/d/n aus <daten>/fassade/fassaden.json bzw. aus den JSON selbst. Tiefe w = aus dem MODELL (98-%-Wert der Dreiecke im
                 Kasten, 0,3 .. 4 m) - so zeigt das Bild, was gebaut wurde, ohne Annahme ueber die Ausladung.
  Rundteile      audit/dach_profil.json: jeder Eintrag mit 'profil' [[z, r, ...], ...] (laterne_foto, spitze_foto, ...) + 'achse' (sonst Achse eines Geschwisters).
  Profil-Bauteile (Ansicht von der Seite zusaetzlich): Name vordach/vorbau/erker/gesims/umgang/balkon/dach ODER Modell-Ausladung > 0,8 m; Rundteile immer.
Kamerawahl (kamera_wertung, rein geometrisch, dann Bildguete fuer die besten --kandidaten):
  Lage       Bauteil-Kasten ganz vor der Kamera und >= 85 % im Bild (nicht angeschnitten), laengste Seite >= 6 % des Bildes
  Groesse    min(1, Anteil/0,35), ab 90 % Bildanteil leicht abgewertet;  Mitte: 1 - 0,6 x Abstand Kastenmitte-Bildmitte / halbe Bildseite
  Blick      front: cos(Blick gegen Aussennormale, 3D - Steilblicke von unten verlieren); seite: sin(waagrechter Winkel 45..100 Grad) x cos(Hoehenwinkel);
             rund: cos^2(Hoehenwinkel), zweite Ansicht >= 60 Grad im Azimut versetzt
  Herkunft   eigene Fotos 1,3, Videobilder 0,6 (wie neben_fotos_waehlen.py)
  Sicht      Anteil der Bauteil-Pixel, die im Render des GANZEN Modells + LoD2-Nachbarn (befundliste.verdecker_netz) nicht verdeckt sind (Maler-Raster, CPU)
  Beleg      Anteil des sichtbaren Bauteilumrisses mit Fotokante (Canny, 3 px) - Kamera dort falsch / Bauteil im Foto nicht da -> klein (Faktor (Beleg - 0,1)/0,4 in 0,02 .. 1)
  Passung    Modellkanten (Render) gegen Fotokanten ohne Verschiebung / bestes Verschieben um <= 10 % des Ausschnitts (Kamerapose dort daneben -> < 1), Faktor Passung^2
  Quelle     Fotos, mit denen die messende Stufe das Bauteil fand ('fotos'), x 1,5; ihre 'ausreisser'/'verworfen' gemieden
  Bild       Schaerfe (Laplace-Varianz, relativ zum besten Kandidaten) x Licht (Ausschnitt nicht viel dunkler als das Gesamtbild = kein Gegenlicht, Kontrast)
Render: Maler-Algorithmus (cv2.fillPoly, fern -> nah, Rueckseiten weg) nur im Ausschnitt, CPU, kein GPU-Bedarf; Licht wie modell_neben_foto.py; Bauteil-Dreiecke
leicht blau getoent. Foto wie modell_neben_foto.py mit k1 entzerrt.
GRENZEN (ANNAHME): Baeume, Tram, Schilder sieht die Sicht-Wertung nicht (Beleg faengt nur einen Teil); Maler-Raster kann bei sehr grossen Dreiecken die Reihenfolge
vertauschen. Die Bilder ANSEHEN - sie sind Sichtpruefung, kein Tor.
rc 0 = Bilder geschrieben, rc 3 = kein Bauteil/keine Kamera gefunden (Bericht, kein Fehler der Kette).
Umgebung: cv2/numpy -> venv-seg (`tools/py tools/neben_details.py ...`), Speicher ~ 0,5 GB fuer 1,4 Mio. Dreiecke.
"""
import sys, os, re, json, glob, math, struct
import numpy as np
import cv2

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)

PROFIL_NAMEN = re.compile(r"vordach|vorbau|erker|gesims|umgang|balkon|dach|traufe|kranz", re.I)
KACHEL_H = 420


# ---------------------------------------------------------------- Netz
def stl_laden(pfad, faktor):
    """Binaeres STL -> Dreiecke (n, 3, 3) in Metern (faktor = m je STL-Einheit). ASCII-STL ueber trimesh."""
    raw = open(pfad, "rb").read()
    n = struct.unpack("<I", raw[80:84])[0] if len(raw) >= 84 else 0
    if len(raw) == 84 + 50 * n and n > 0:
        A = np.frombuffer(raw, dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]), count=n, offset=84)
        return A["v"].astype(np.float64) * faktor
    import trimesh
    return np.asarray(trimesh.load(pfad, force="mesh").triangles, float) * faktor


# ---------------------------------------------------------------- Kamera
def kamera_matrix(K, skala=1.0):
    R = cv2.Rodrigues(np.asarray(K["rvec"], float))[0]; t = np.asarray(K["t"], float).ravel()
    tr = np.asarray(K.get("rahmen_verschiebung") or [0, 0, 0], float)
    return R, t + R @ tr, K["f_px"] * skala, K["cx"] * skala, K["cy"] * skala, -R.T @ t - tr


def bildgroesse(K):
    b = K.get("bild")
    return (float(b[0]), float(b[1])) if b else (2.0 * K["cx"], 2.0 * K["cy"])


def kameras_laden(od, fotos_dir):
    """Messkameras K-*.json wie neben_fotos_waehlen.py: rvec da, nicht tiefe_unsicher, Buendel-Tor nicht rot, Foto im fotos_dir."""
    out = {}
    for kf in sorted(glob.glob(os.path.join(od, "messprotokoll", "K-*.json"))):
        nm = os.path.basename(kf)[2:-5]
        try: k = json.load(open(kf)).get("kamera")
        except Exception: continue
        if not isinstance(k, dict) or "rvec" not in k or "f_px" not in k or k.get("tiefe_unsicher"): continue
        if "buendel_tor" in k and not (k["buendel_tor"] or {}).get("ok", True): continue
        pf = glob.glob(os.path.join(fotos_dir, glob.escape(nm) + ".*")) or glob.glob(os.path.join(fotos_dir, glob.escape(nm) + "_*"))
        pf = [p for p in pf if p.lower().endswith((".jpg", ".jpeg", ".png"))]
        if pf: out[nm] = (k, pf[0])
    return out


def herkunft(nm):
    return 1.3 if nm.startswith("eigen") else 0.6 if ("video" in nm or "__vf_" in nm) else 1.0


def kamera_wertung(K, ecken, mitte, n=None, modus="front", nm=""):
    """Geometrische Wertung einer Kamera fuer ein Bauteil (Kastenecken in m). None = unbrauchbar. modus front | seite | rund."""
    R, t, f, cx, cy, C = kamera_matrix(K); W, H = bildgroesse(K)
    X = np.asarray(ecken, float) @ R.T + t
    if (X[:, 2] <= 0.5).any(): return None
    u = f * X[:, 0] / X[:, 2] + cx; v = f * X[:, 1] / X[:, 2] + cy
    x0, x1, y0, y1 = u.min(), u.max(), v.min(), v.max(); bw, bh = x1 - x0, y1 - y0
    if bw < 2 or bh < 2: return None
    innen = (max(0.0, min(x1, W) - max(x0, 0.0)) * max(0.0, min(y1, H) - max(y0, 0.0))) / (bw * bh)
    if innen < 0.85: return None
    g = max(bw / W, bh / H)
    if g < 0.06: return None
    groesse = min(1.0, g / 0.35) * (1.0 if g < 0.9 else 0.9 / g)
    dm = math.hypot((x0 + x1) / 2 - W / 2, (y0 + y1) / 2 - H / 2) / (0.5 * min(W, H)); m_ = 1.0 - 0.6 * min(1.0, dm)
    r = C - np.asarray(mitte, float); dist = float(np.linalg.norm(r)); r = r / max(dist, 1e-9)
    hoehe = math.asin(max(-1.0, min(1.0, float(r[2])))); rh = r[:2] / max(np.linalg.norm(r[:2]), 1e-9)
    if modus == "rund":
        blick = math.cos(hoehe) ** 2; wi = None
    else:
        nn = np.array([n[0], n[1], 0.0]) / max(math.hypot(n[0], n[1]), 1e-9)
        wi = math.degrees(math.acos(max(-1.0, min(1.0, float(rh @ nn[:2])))))
        if modus == "front":
            blick = float(r @ nn)
            if blick < 0.2: return None
        else:
            if not 45.0 <= wi <= 100.0: return None
            blick = math.sin(math.radians(min(wi, 90.0))) * math.cos(hoehe)
    w = groesse * m_ * blick * herkunft(nm)
    return dict(wert=float(w), groesse=round(float(g), 3), mitte=round(float(m_), 3), blick=round(float(blick), 3), winkel=None if wi is None else round(wi),
                hoehe_grad=round(math.degrees(hoehe)), abstand_m=round(dist, 1), azimut=round(math.degrees(math.atan2(rh[1], rh[0]))),
                px=[float(x0), float(y0), float(x1), float(y1)])


# ---------------------------------------------------------------- Bauteile
def _rahmen_sammeln(x, fid, out, tiefe=0):
    if tiefe > 6: return
    if isinstance(x, dict):
        f2 = x["id"] if isinstance(x.get("id"), str) and re.fullmatch(r"f\d\d", x["id"]) else fid
        if f2 and all(isinstance(x.get(a), list) and len(x[a]) >= 2 for a in ("o", "d", "n")) and f2 not in out:
            out[f2] = dict(o=[float(v) for v in x["o"][:2]], d=[float(v) for v in x["d"][:2]], n=[float(v) for v in x["n"][:2]])
        for a, v in x.items(): _rahmen_sammeln(v, a if re.fullmatch(r"f\d\d", str(a)) else f2, out, tiefe + 1)
    elif isinstance(x, list):
        for v in x: _rahmen_sammeln(v, fid, out, tiefe + 1)


def fassaden_rahmen(audit, daten=None):
    out = {}
    fj = os.path.join(daten, "fassade", "fassaden.json") if daten else None
    if fj and os.path.exists(fj):
        try:
            for f in json.load(open(fj)).get("fassaden") or []:
                if f.get("id") and all(k in f for k in ("o", "d", "n")): out[f["id"]] = dict(o=f["o"][:2], d=f["d"][:2], n=f["n"][:2])
        except Exception: pass
    for p in sorted(glob.glob(os.path.join(audit, "*_auto.json"))) + [os.path.join(audit, "vordach_profil.json")]:
        if not os.path.exists(p): continue
        try: _rahmen_sammeln(json.load(open(p)), None, out)
        except Exception: pass
    return out


def _kurz(name):
    name = name.replace("_profil", "").replace("oeffnungen/", "oeffnung_").replace("uhren", "uhr").replace("fenster/", "fenster_")
    return re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_")


def _namen(x):
    return [os.path.splitext(os.path.basename(q))[0] for q in x if isinstance(q, str)] if isinstance(x, list) else []


def quell_fotos(e):
    """Fotos, mit denen die Quelle das Bauteil gemessen hat (bevorzugt) bzw. die sie verworfen hat (meiden: ausreisser/verworfen)."""
    return dict(bevorzugt=_namen(e.get("fotos")), meiden=_namen(e.get("ausreisser")) + _namen(e.get("verworfen")))


def _zonen_quelle(audit, zz):
    """Eintrag der Quell-JSON zu einer Zone aus befundliste.bauteil_zonen (gleiche Fassade, gleiches u0) -> quell_fotos, sonst leer."""
    stamm = zz["name"].split("/")[0]; datei = {"vorbau": "vorbauten_auto.json", "vordach_profil": "vordach_profil.json"}.get(stamm, stamm + "_auto.json")
    try: j = json.load(open(os.path.join(audit, datei)))
    except Exception: return {}
    gef = []

    def geh(x, fid, t=0):
        if t > 6 or gef: return
        if isinstance(x, dict):
            f2 = x["id"] if isinstance(x.get("id"), str) and re.fullmatch(r"f\d\d", x["id"]) else fid
            k = x.get("kasten") if isinstance(x.get("kasten"), list) else [x.get("u0")]
            if f2 == zz["fassade"] and k and isinstance(k[0], (int, float)) and abs(float(k[0]) - zz["u0"]) < 1e-6 and (x.get("fotos") or x.get("ausreisser")):
                gef.append(quell_fotos(x)); return
            for a, v in x.items(): geh(v, a if re.fullmatch(r"f\d\d", str(a)) else f2, t + 1)
        elif isinstance(x, list):
            for v in x: geh(v, fid, t + 1)
    geh(j, None)
    return gef[0] if gef else {}


def rund_bauteile(audit):
    p = os.path.join(audit, "dach_profil.json")
    if not os.path.exists(p): return []
    try: j = json.load(open(p))
    except Exception: return []
    achsen = [v["achse"] for v in j.values() if isinstance(v, dict) and isinstance(v.get("achse"), list) and len(v["achse"]) >= 2]
    out = []
    for k, v in j.items():
        if not isinstance(v, dict) or not isinstance(v.get("profil"), list): continue
        pr = [q for q in v["profil"] if isinstance(q, (list, tuple)) and len(q) >= 2 and all(isinstance(a, (int, float)) for a in q[:2])]
        if len(pr) < 3: continue
        ach = v.get("achse") if isinstance(v.get("achse"), list) and len(v["achse"]) >= 2 else (achsen[0] if achsen else None)
        if ach is None: continue
        z = [float(q[0]) for q in pr]; r = max(float(q[1]) for q in pr); z0, z1 = min(z), max(z)
        for a, w in v.items():                                     # Spitze/Nadel ueber dem letzten Profilschnitt (spitze_z, nadel_z ...)
            if a.endswith("_z") and not a.endswith("roh_z") and isinstance(w, (int, float)) and z1 < w < z1 + 10: z1 = float(w)
        if r > 15 or z1 - z0 < 0.3: continue
        out.append(dict(name=_kurz(k.replace("_foto", "")), art="rund", achse=[float(ach[0]), float(ach[1])], r=r, z0=z0, z1=z1, profil=True,
                        quelle=f"dach_profil.json/{k}", gueltig=v.get("gueltig", True), **quell_fotos(v)))
    return out


def zonen_bauteile(audit, rahmen):
    import befundliste as BL
    out = []
    for zz in BL.bauteil_zonen(audit):
        fr = rahmen.get(zz["fassade"])
        if not fr: continue
        nm = _kurz(zz["name"]) + "_" + zz["fassade"]
        out.append(dict(name=nm, art="fassade", fassade=zz["fassade"], o=fr["o"], d=fr["d"], n=fr["n"], u0=zz["u0"], u1=zz["u1"], z0=zz["z0"], z1=zz["z1"],
                        w0=-0.3, w1=None, profil=bool(PROFIL_NAMEN.search(zz["name"])), quelle=zz["name"], **_zonen_quelle(audit, zz)))
    return out


def lokal(T, b):
    """Dreiecksmitten im Bauteilrahmen: fassade -> (u, w, z), rund -> (r, z)."""
    c = T.mean(1)
    if b["art"] == "rund":
        return np.hypot(c[:, 0] - b["achse"][0], c[:, 1] - b["achse"][1]), c[:, 2]
    rel = c[:, :2] - np.asarray(b["o"], float)
    return rel @ np.asarray(b["d"], float), rel @ np.asarray(b["n"], float), c[:, 2]


def auswahl(T, b, L=None):
    L = lokal(T, b) if L is None else L
    if b["art"] == "rund":
        r, z = L; return (r <= b["r"] + 0.2) & (z >= b["z0"] - 0.1) & (z <= b["z1"] + 0.1)
    u, w, z = L; return (u >= b["u0"] - 0.1) & (u <= b["u1"] + 0.1) & (w >= b["w0"]) & (w <= b["w1"]) & (z >= b["z0"] - 0.1) & (z <= b["z1"] + 0.1)


def tiefe_aus_modell(T, b):
    """Ausladung w1 aus dem Modell: 98-%-Wert der Dreiecke im u/z-Kasten vor der Wand (0,3 .. 4 m)."""
    u, w, z = lokal(T, b)
    s = (u >= b["u0"]) & (u <= b["u1"]) & (z >= b["z0"]) & (z <= b["z1"]) & (w > -0.5) & (w < 4.5)
    return float(np.clip(np.percentile(w[s], 98), 0.3, 4.0)) if s.sum() >= 5 else 0.5


def ecken(b):
    if b["art"] == "rund":
        a = np.linspace(0, 2 * np.pi, 16, endpoint=False); q = []
        for z in (b["z0"], b["z1"]): q += [[b["achse"][0] + b["r"] * math.cos(t_), b["achse"][1] + b["r"] * math.sin(t_), z] for t_ in a]
        return np.array(q), np.array([b["achse"][0], b["achse"][1], (b["z0"] + b["z1"]) / 2])
    o, d, n = (np.asarray(b[k], float) for k in ("o", "d", "n"))
    q = [list(o + u * d + w * n) + [z] for u in (b["u0"], b["u1"]) for w in (b["w0"], b["w1"]) for z in (b["z0"], b["z1"])]
    q = np.array(q); return q, q.mean(0)


def bauteile_sammeln(audit, T, daten=None):
    rahmen = fassaden_rahmen(audit, daten); B = zonen_bauteile(audit, rahmen) + rund_bauteile(audit); namen = {}
    for b in B:
        if b["art"] == "fassade":
            b["w1"] = tiefe_aus_modell(T, b)
            if b["w1"] > 0.8: b["profil"] = True
        k = b["name"]; namen[k] = namen.get(k, 0) + 1
        if namen[k] > 1: b["name"] = f"{k}_{namen[k]}"
    return B


# ---------------------------------------------------------------- Render (Maler-Algorithmus, CPU)
_MITTEN = {}
def _mitten(T):
    k = (T.__array_interface__["data"][0], len(T), T.strides)
    if k not in _MITTEN:
        if len(_MITTEN) > 2: _MITTEN.clear()
        _MITTEN[k] = T.mean(1)
    return _MITTEN[k]


def rendern(T, FN, K, kasten, skala, wh, hervor=None, klein=1.0):
    """Graues Render im Ausschnitt kasten (x0, y0, x1, y1 in Originalpixeln, Foto entzerrt) mit Ausgabegroesse wh = (w, h). -> (BGR, fid-Karte).
    Dreiecke >= klein px: Maler (fillPoly fern -> nah) mit Tiefenbild; kleinere als Punkt (Mitte) mit Tiefentest gegen dieses Tiefenbild und
    untereinander (naechstes gewinnt) - vektoriell, sonst kostete die Python-Schleife ueber 1,4 Mio. Dreiecke je Kandidat Sekunden."""
    R, t, f, cx, cy, C = kamera_matrix(K); x0, y0, x1, y1 = kasten; ow, oh = wh; sx = ow / (x1 - x0); sy = oh / (y1 - y0)
    X = T.reshape(-1, 3) @ R.T + t; z = X[:, 2].reshape(-1, 3)
    zs = np.maximum(X[:, 2], 1e-6); u = ((f * X[:, 0] / zs + cx - x0) * sx).reshape(-1, 3); v = ((f * X[:, 1] / zs + cy - y0) * sy).reshape(-1, 3)
    ok = (z > 0.3).all(1) & (u.max(1) >= 0) & (u.min(1) < ow) & (v.max(1) >= 0) & (v.min(1) < oh)
    ids = np.nonzero(ok)[0]
    ids = ids[np.einsum("ij,ij->i", FN[ids], C - _mitten(T)[ids]) > 0]         # Rueckseiten weg
    zm = z[ids].mean(1); o_ = np.argsort(-zm); ids = ids[o_]; zm = zm[o_]       # fern -> nah
    ui, vi = u[ids], v[ids]; gross = np.maximum(ui.max(1) - ui.min(1), vi.max(1) - vi.min(1)) >= klein
    fid = np.full((oh, ow), -1, np.int32); tief = np.full((oh, ow), np.inf, np.float32)
    q = np.round(np.stack([ui[gross], vi[gross]], -1) * 16).astype(np.int32)
    for i, p, zz in zip(ids[gross], q, zm[gross]):
        cv2.fillPoly(fid, [p], int(i), lineType=cv2.LINE_8, shift=4); cv2.fillPoly(tief, [p], float(zz), lineType=cv2.LINE_8, shift=4)
    kl = ~gross
    if kl.any():
        px = np.floor(ui[kl].mean(1) + 0.5).astype(np.int64); py = np.floor(vi[kl].mean(1) + 0.5).astype(np.int64); zk = zm[kl]; ik = ids[kl]
        m = (px >= 0) & (px < ow) & (py >= 0) & (py < oh); px, py, zk, ik = px[m], py[m], zk[m], ik[m]
        lin = py * ow + px; m = zk < tief.ravel()[lin]; lin, zk, ik = lin[m], zk[m], ik[m]
        if len(lin):
            o_ = np.lexsort((zk, lin)); lin, ik = lin[o_], ik[o_]; erst = np.r_[True, lin[1:] != lin[:-1]]
            fid.ravel()[lin[erst]] = ik[erst]
    li = R.T @ np.array([-0.45, -0.75, -1.0]); li = li / np.linalg.norm(li)   # Licht wie modell_neben_foto.py
    g = np.full((oh, ow), 235.0); tr = fid >= 0
    g[tr] = 60 + 190 * np.clip(FN[fid[tr]] @ li, 0, 1)
    img = cv2.cvtColor(g.astype(np.uint8), cv2.COLOR_GRAY2BGR)
    if hervor is not None:
        hm = tr.copy(); hm[tr] = hervor[fid[tr]]
        img[hm] = np.clip(img[hm].astype(int) * np.array([1.0, 0.86, 0.72]) + np.array([40, 0, 0]), 0, 255).astype(np.uint8)
    return img, fid


def sicht_anteil(T, FN, K, kasten, sel, gross=200, foto=None, extra=None):
    """Sicht = Anteil der Bauteilpixel (Render nur des Bauteils), die im Render des ganzen Modells (+ extra = Verdecker-Dreiecke, z. B. LoD2-Nachbarn)
    das Bauteil zeigen (= nicht verdeckt). Mit foto (entzerrtes Bild): Beleg = Anteil der sichtbaren Bauteil-Umrisspixel mit einer Fotokante (Canny) in <= 3 px
    (Kamera an der Stelle falsch / Bauteil im Foto nicht zu sehen -> klein); Passung = Treffer der Modellkanten auf Fotokanten ohne Verschiebung / bestes
    Verschieben um <= 10 % (< 1: Kamera sitzt an dieser Stelle daneben). -> (sicht, beleg oder None, passung oder None)."""
    x0, y0, x1, y1 = kasten; s = gross / max(x1 - x0, y1 - y0); wh = (max(8, int(round((x1 - x0) * s))), max(8, int(round((y1 - y0) * s))))
    ids = np.nonzero(sel)[0]
    if not len(ids): return 0.0, None, None
    _, f_b = rendern(T[ids], FN[ids], K, kasten, s, wh)
    nb = int((f_b >= 0).sum())
    if nb == 0: return 0.0, None, None
    if extra is not None and len(extra[0]):
        T = np.concatenate([T, extra[0]]); FN = np.concatenate([FN, extra[1]]); sel = np.r_[sel, np.zeros(len(extra[0]), bool)]
    img_a, f_a = rendern(T, FN, K, kasten, s, wh)
    sicht = float((sel[f_a[f_b >= 0]] & (f_a[f_b >= 0] >= 0)).sum() / nb)
    if foto is None: return sicht, None, None
    sb = np.zeros(f_a.shape, np.uint8); sb[f_a >= 0] = sel[f_a[f_a >= 0]]
    rand = cv2.morphologyEx(sb, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
    c = foto[int(y0):int(y0) + int(round(y1 - y0)), int(x0):int(x0) + int(round(x1 - x0))]
    if rand.sum() < 10 or c.size == 0: return sicht, None, None
    g = cv2.GaussianBlur(cv2.cvtColor(cv2.resize(c, wh, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY), (3, 3), 0)
    kan = cv2.Canny(g, 20, 50)                                                    # niedrige feste Schwellen: Beleg ist ein Veto gegen "nichts da", kein Formmass
    d = cv2.distanceTransform((kan == 0).astype(np.uint8), cv2.DIST_L2, 3)
    beleg = float((d[rand] <= 3.0).mean())
    # Passung: Modellkanten (Render) gegen Fotokanten, um bis zu 10 % verschoben - liegt das Optimum weit weg, sitzt die Kamera hier daneben
    mk = (cv2.Canny(cv2.cvtColor(img_a, cv2.COLOR_BGR2GRAY), 20, 50) > 0) | rand        # Schattierungskanten + Bauteilumriss
    yy, xx = np.nonzero(mk)
    if len(xx) < 20: return sicht, beleg, None
    r_ = max(3, int(0.1 * max(wh))); H_, W_ = d.shape; best = 0.0; null = None
    for dy in range(-r_, r_ + 1, 2):
        for dx in range(-r_, r_ + 1, 2):
            x_, y_ = xx + dx, yy + dy; m = (x_ >= 0) & (x_ < W_) & (y_ >= 0) & (y_ < H_)
            if m.sum() < 0.5 * len(xx): continue
            q = float((d[y_[m], x_[m]] <= 2.0).mean())
            if dx == 0 and dy == 0: null = q
            best = max(best, q)
    return sicht, beleg, (None if null is None or best <= 0 else null / best)


# ---------------------------------------------------------------- Foto
_FOTO = {}
def foto_laden(pf, K):
    if pf in _FOTO: return _FOTO[pf]
    im = cv2.imread(pf)
    if im is None: return None
    W, H = bildgroesse(K)
    if abs(im.shape[1] - W) > 1 or abs(im.shape[0] - H) > 1: im = cv2.resize(im, (int(W), int(H)), interpolation=cv2.INTER_AREA)
    k1 = float(K.get("k1") or 0.0)
    if k1: im = cv2.undistort(im, np.array([[K["f_px"], 0, K["cx"]], [0, K["f_px"], K["cy"]], [0, 0, 1.0]]), np.array([k1, 0, 0, 0.0]))
    if len(_FOTO) > 4: _FOTO.clear()
    _FOTO[pf] = im; return im


def bild_guete(im, kasten):
    x0, y0, x1, y1 = [int(round(a)) for a in kasten]; H, W = im.shape[:2]
    c = im[max(0, y0):min(H, y1), max(0, x0):min(W, x1)]
    if c.size == 0: return 0.0, 0.0
    g = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY); s = 256.0 / max(g.shape); g = cv2.resize(g, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else g
    lap = float(cv2.Laplacian(g, cv2.CV_64F).var())
    gm = float(cv2.cvtColor(cv2.resize(im, (64, 64), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).mean())
    licht = float(np.clip(g.mean() / max(gm, 1.0) / 0.8, 0.4, 1.0) * np.clip(g.std() / 30.0, 0.4, 1.0))
    return lap, licht


def ausschnitt(px, W, H, rand=0.25):
    x0, y0, x1, y1 = px; bw, bh = x1 - x0, y1 - y0; m = max(bw, bh) * rand
    x0, y0, x1, y1 = x0 - m, y0 - m, x1 + m, y1 + m
    return [max(0.0, x0), max(0.0, y0), min(float(W), x1), min(float(H), y1)]


# ---------------------------------------------------------------- Wahl
def kamera_waehlen(b, kams, T, FN, sel, modus, n_kand=6, ausser=(), azimut_weg=None, min_az=0.0, extra=None, bevorzugt=(), meiden=()):
    """Beste Kamera fuer ein Bauteil: geometrische Vorwahl (kamera_wertung), dann fuer die besten n_kand Sicht (Modell + extra-Verdecker), Beleg (Fotokanten am
    Bauteilumriss), Licht, Schaerfe. bevorzugt = Fotos, mit denen die Quelle das Bauteil gemessen hat (x 1,5); meiden = dort verworfene Fotos (Ausreisser)."""
    E, M = ecken(b); kand = []
    for nm, (K, pf) in kams.items():
        if nm in ausser or nm in meiden: continue
        w = kamera_wertung(K, E, M, b.get("n"), modus, nm)
        if not w: continue
        if azimut_weg is not None and abs((w["azimut"] - azimut_weg + 180) % 360 - 180) < min_az: continue
        if nm in bevorzugt: w["wert"] *= 1.5; w["quelle_foto"] = True
        kand.append((w["wert"], nm, w))
    kand.sort(key=lambda x: -x[0]); quelle = [k_ for k_ in kand[n_kand:] if k_[1] in bevorzugt][:3]
    kand = kand[:n_kand] + quelle; best = None; laps = []                       # Quellfotos (haben das Bauteil nachweislich gesehen) immer mitpruefen
    for wert, nm, w in kand:
        K, pf = kams[nm]; im = foto_laden(pf, K)
        if im is None: continue
        H, W = im.shape[:2]; ka = ausschnitt(w["px"], W, H)
        lap, licht = bild_guete(im, w["px"]); laps.append(lap)
        si, be, pa = sicht_anteil(T, FN, K, ka, sel, foto=im, extra=extra)
        w.update(sicht=round(si, 3), beleg=None if be is None else round(be, 3), passung=None if pa is None else round(pa, 3), licht=round(licht, 3), _lap=lap, kasten=ka)
    if not laps: return None
    mx = max(laps) or 1.0
    for wert, nm, w in kand:
        if "_lap" not in w: continue
        w["schaerfe"] = round(0.5 + 0.5 * w.pop("_lap") / mx, 3)
        bf = (1.0 if w["beleg"] is None else float(np.clip((w["beleg"] - 0.1) / 0.4, 0.02, 1.0))) * (1.0 if w["passung"] is None else float(np.clip(w["passung"], 0.3, 1.0)) ** 2)
        w["gesamt"] = round(w["wert"] * max(w["sicht"], 0.05) ** 1.5 * bf * w["licht"] * w["schaerfe"], 4)
        if best is None or (not schwach(w), w["gesamt"]) > (not schwach(best[1]), best[1]["gesamt"]): best = (nm, w)     # brauchbare Ansicht vor schwacher
    return best


def kachel(im, txt, h=KACHEL_H):
    s = h / im.shape[0]; k = cv2.resize(im, (max(1, int(round(im.shape[1] * s))), h), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
    for i, z in enumerate(txt):
        cv2.putText(k, z, (5, 17 + 17 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 3, cv2.LINE_AA)
        cv2.putText(k, z, (5, 17 + 17 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 0, 200), 1, cv2.LINE_AA)
    return k


def schwach(w):
    """Beste verfuegbare Ansicht ist trotzdem unbrauchbar: Bauteil ueberwiegend verdeckt (Modell/LoD2-Nachbarn) oder kaum Fotokanten am Umriss."""
    be, pa = w.get("beleg"), w.get("passung")
    return w["sicht"] < 0.3 or (be is not None and be < 0.2) or (pa is not None and pa < 0.5) or (be is not None and pa is not None and be < 0.35 and pa < 0.85)


def ansicht_bild(T, FN, sel, kams, nm, w, b, modus):
    K, pf = kams[nm]; im = foto_laden(pf, K); x0, y0, x1, y1 = w["kasten"]
    fc = im[int(y0):int(y1), int(x0):int(x1)]; s = KACHEL_H / max(fc.shape[0], 1); wh = (max(8, int(round(fc.shape[1] * s))), KACHEL_H)
    r, _ = rendern(T, FN, K, (int(x0), int(y0), int(x0) + fc.shape[1], int(y0) + fc.shape[0]), s, wh, hervor=sel)
    kopf = [f"{b['name']} ({modus})", f"Foto {nm[-28:]}", f"Sicht {w['sicht']:.0%}  Beleg {'-' if w.get('beleg') is None else format(w['beleg'], '.0%')}  Passung {'-' if w.get('passung') is None else format(w['passung'], '.0%')}", f"Blick {w['blick']:.2f}  Hoehe {w['hoehe_grad']} Grad  {w['abstand_m']} m"]
    if b.get("gueltig") is False: kopf.append("Messung ungueltig (Quelle)")
    if schwach(w): kopf.append("SCHWACH: verdeckt/kein Fotobeleg - nicht bewerten")
    return np.hstack([kachel(fc, kopf), np.full((KACHEL_H, 6, 3), 255, np.uint8), kachel(r, ["Modell (Ketten-STL), Bauteil blau"])])


def raster(bilder, spalten=3, zw=640, zh=420):
    if not bilder: return None
    zellen = []
    for p in bilder:
        im = cv2.imread(p)
        if im is None: continue
        s = min(zw / im.shape[1], zh / im.shape[0]); im = cv2.resize(im, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        z = np.full((zh, zw, 3), 255, np.uint8); z[:im.shape[0], :im.shape[1]] = im; zellen.append(cv2.rectangle(z, (0, 0), (zw - 1, zh - 1), (180, 180, 180), 1))
    while len(zellen) % spalten: zellen.append(np.full((zh, zw, 3), 255, np.uint8))
    return np.vstack([np.hstack(zellen[i:i + spalten]) for i in range(0, len(zellen), spalten)])


def main(argv=None):
    a = sys.argv[1:] if argv is None else argv
    pos = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or not a[i - 1].startswith("--"))]
    if not pos: sys.exit(__doc__)
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    op = os.path.abspath(pos[0]); od = os.path.dirname(op); obj = json.load(open(op)); ziel = os.path.basename(od); audit = os.path.join(od, "audit")
    root = os.path.dirname(os.path.dirname(od))                                   # Repo-Wurzel aus dem Objektpfad (wie neben_fotos_waehlen.py), nicht aus dem Werkzeugpfad
    daten = opt("--daten", f"/media/oem/scan/rc-park_daten/{ziel}"); aus = os.path.abspath(opt("--aus", audit)); mx = int(opt("--max", 24)); nk = int(opt("--kandidaten", 6))
    stl = opt("--stl") or os.path.join(root, obj.get("stl") or os.path.join("modelle", "stl", ziel + "_1-87.stl"))
    faktor = float(obj.get("stl_massstab", 87)) / 1000.0 if obj.get("stl_einheit_mm", True) else 1.0
    if not os.path.exists(stl): print("kein STL:", stl); return 3
    T = stl_laden(stl, faktor); FN = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); FN /= np.maximum(np.linalg.norm(FN, axis=1, keepdims=True), 1e-12)
    kams = kameras_laden(od, os.path.join(root, obj["fotos_dir"]))
    extra = None
    if "--ohne-verdecker" not in a:                                                # LoD2-Nachbarn als fremde Verdecker (befundliste.verdecker_netz, wiederverwendet)
        try:
            import befundliste as BL
            vn = BL.verdecker_netz(obj)
            if vn is not None and len(vn.faces):
                TV = np.asarray(vn.triangles, float); NV = np.cross(TV[:, 1] - TV[:, 0], TV[:, 2] - TV[:, 0]); NV /= np.maximum(np.linalg.norm(NV, axis=1, keepdims=True), 1e-12)
                extra = (np.concatenate([TV, TV[:, [0, 2, 1]]]), np.concatenate([NV, -NV]))          # LoD2-Flaechen beidseitig (Orientierung unsicher)
                print(f"Verdecker: {len(TV)} LoD2-Nachbardreiecke")
        except Exception as e: print("Verdecker nicht geladen (Sicht nur gegen das eigene Modell):", type(e).__name__, str(e)[:160])
    TA, FA = (np.concatenate([T, extra[0]]), np.concatenate([FN, extra[1]])) if extra else (T, FN)   # einmal zusammenfuegen (Sicht-Render), T/FN = Sicht auf TA[:len(T)]
    T, FN = TA[:len(T)], FA[:len(FN)]
    B = bauteile_sammeln(audit, T, daten)
    B.sort(key=lambda b: (not b["profil"], -((b["r"] * 2) ** 2 if b["art"] == "rund" else (b["u1"] - b["u0"])) * (b["z1"] - b["z0"])))
    if len(B) > mx: print(f"{len(B)} Bauteile, nur die ersten {mx} (Profil-Bauteile, dann groesste) - Rest mit --max"); B = B[:mx]
    print(f"{len(T)} Dreiecke, {len(kams)} Messkameras mit Foto, {len(B)} Bauteile")
    os.makedirs(aus, exist_ok=True)
    for p in glob.glob(os.path.join(aus, "neben_detail_*.jpg")): os.remove(p)       # nur eigene Bilder des vorigen Laufs
    ergebnis = []; bilder = []
    for b in B:
        sel = auswahl(T, b); e = dict(name=b["name"], quelle=b["quelle"], art=b["art"], profil=b["profil"], dreiecke=int(sel.sum()), ansichten=[])
        if b["art"] == "fassade": e.update(fassade=b["fassade"], u=[b["u0"], b["u1"]], z=[round(b["z0"], 2), round(b["z1"], 2)], w=[b["w0"], round(b["w1"], 2)])
        else: e.update(achse=b["achse"], r=round(b["r"], 2), z=[round(b["z0"], 2), round(b["z1"], 2)])
        if not sel.any(): e["fehlt"] = "keine Modelldreiecke im Bauteilkasten (Bauteil nicht gebaut?)"
        modi = ["rund", "rund"] if b["art"] == "rund" else (["front", "seite"] if b["profil"] else ["front"])
        zeilen = []; erst = None
        for i, md in enumerate(modi):
            best = kamera_waehlen(b, kams, TA, FA, np.r_[sel, np.zeros(len(TA) - len(T), bool)], md, nk, ausser=(erst[0],) if erst else (),
                                  azimut_weg=erst[1]["azimut"] if (erst and md == "rund") else None, min_az=60.0,
                                  bevorzugt=set(b.get("bevorzugt") or ()), meiden=set(b.get("meiden") or ()))
            if not best: e["ansichten"].append(dict(modus=md, foto=None, grund="keine Kamera zeigt das Bauteil ganz, gross genug und passend gerichtet")); continue
            nm, w = best; erst = erst or best
            zeilen.append(ansicht_bild(T, FN, sel, kams, nm, w, b, md + ("" if i == 0 or md != "rund" else " 2")))
            e["ansichten"].append(dict(modus=md, foto=nm, schwach=schwach(w), **{k: v for k, v in w.items() if k not in ("px",)}))
        if zeilen:
            wm = max(z.shape[1] for z in zeilen); zeilen = [cv2.copyMakeBorder(z, 0, 4, 0, wm - z.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255)) for z in zeilen]
            p = os.path.join(aus, f"neben_detail_{b['name']}.jpg"); cv2.imwrite(p, np.vstack(zeilen), [cv2.IMWRITE_JPEG_QUALITY, 85]); bilder.append(p); e["bild"] = os.path.relpath(p, od)
        ergebnis.append(e)
        print(f"  {b['name']:28s} " + "  ".join(f"{x['modus']}: {(x.get('foto') or 'KEINE')[-26:]} (Sicht {x.get('sicht', 0):.0%}, Beleg {x.get('beleg')}, Passung {x.get('passung')}{', SCHWACH' if x.get('schwach') else ''})" for x in e["ansichten"]), flush=True)
    r = raster(bilder)
    if r is not None: cv2.imwrite(os.path.join(aus, "neben_details.jpg"), r, [cv2.IMWRITE_JPEG_QUALITY, 82])
    json.dump(dict(quelle="tools/neben_details.py (Detailansicht je Bauteil, beste SfM-Kamera)", stl=os.path.relpath(stl, root), bauteile=ergebnis,
                   uebersicht="neben_details.jpg" if r is not None else None), open(os.path.join(aus, "neben_details.json"), "w"), indent=1, ensure_ascii=False)
    print(f"-> {len(bilder)} Detailbilder, Uebersicht {os.path.join(aus, 'neben_details.jpg') if r is not None else '-'} (ANSEHEN)")
    return 0 if bilder else 3


if __name__ == "__main__":
    sys.exit(main())
