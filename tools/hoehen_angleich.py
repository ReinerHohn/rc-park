#!/usr/bin/env python3
"""hoehen_angleich.py <objekt.json> [--stl P] [--wolke P] [--kanten sweep.npz] [--aus audit/hoehen_angleich.json] [--bild PNG] [--nur-messen]
HOEHEN-ANGLEICH WAAGERECHTER BAUTEILE (Kettenstufe 'bauplan_hoehen', Auftrag 24.11.2026 nach dem Hoehensitz-Befund: Modell 1122 sitzt in der Hoehe kaum ueber
Zufall). Synonyme: Hoehe, z, Gesims, Traufe, Galerie, Umgang, Band, Sohlbank, Kaempfer, Uhr, Dachfuss, Vorbau-Dach, Hoehensitz, Hoehenfehler.

WARUM EINE EIGENE STUFE: Die Hoehen der waagerechten Bauteile setzen viele Stufen unabhaengig voneinander (LoD2-Wandoberkante, umgang_aus_fotos: Zone im auf die
Wandebene entzerrten Foto, traufe_aus_fotos: Kanten-Sweep, vorbauten_bauplan: Hoehenfeld je Zelle des Ebenen-Sweeps, rund_aus_umriss: Silhouette, wolke_rest: Baender
aus der Wolke, uhren_wandbild: Kreis im Wandbild). Jede hat ihre eigene Falle (Auskragungs-Falle: Punkt vor/hinter der Messebene wird um Versatz*tan(Blickhoehe)
falsch in z gelesen; Wandebene LoD2 statt gesetzter Wandlage; ANNAHME-Ersatzhoehen). Keine Stufe prueft ihr Ergebnis gegen die anderen Quellen. Diese Stufe prueft
am FERTIG GEBAUTEN Modell jede waagerechte Strukturlinie gegen ZWEI unabhaengige Quellen und gleicht nur an, wo beide dasselbe sagen.

VERFAHREN je Seite (Achse aus objekt.json seiten_konvention, Rahmen wie tools/hoehensitz.py):
 1. Linien: Spruenge der Aussenlage in z fuer Modell und dichte Wolke (hoehensitz.seite_messen, 1-m-Streifen, 5-cm-Zellen).
 2. LINIENZUG = Modell-Linien gleichen Vorzeichens in benachbarten Streifen (<= KETTE_DS) mit |dz| <= KETTE_DZ; nur Zuege ueber >= MIN_STREIFEN Streifen
    (ein Bauteil ist breiter als ein Streifen; Einzellinien sind Fugen/Rauschen).
 3. QUELLE WOLKE (3D, Mehrfoto-Triangulation): Verschiebungs-Abstimmung - fuer jedes delta in +-MAX_DZ zaehlt, in wie vielen Streifen des Zuges eine Wolken-Linie
    gleichen Vorzeichens bei z + delta (+-VOTE_TOL) liegt. delta_wolke = beste Stimme (>= STUETZ_MIN der Streifen), mehrdeutig, wenn eine zweite Spitze
    >= MEHRDEUTIG der besten hat (zwei Gesimse untereinander).
 4. QUELLE FOTOKANTEN (KERNMETHODE, unabhaengig von der Wolke): triangulierte 3D-Kantenpunkte der Kantenstufe (tools/kantenstufe.py -> <daten>/kanten/sweep.npz)
    in der Aussenschale der Seite (<= KANT_SCHALE hinter der Aussenlage) und im t-Bereich des Zuges -> Hoehen-Histogramm. Eine waagerechte Kante ist eine Spitze
    (senkrechte Kanten verteilen sich gleichmaessig ueber z). Beleg, wenn bei z + delta_wolke eine Spitze >= KANT_PROM x Untergrund steht und sie die Stelle der
    Modell-Linie um >= KANT_VORRANG uebertrifft (sonst bestaetigen die Kanten das Modell). Die Kantenpunkte sind 3D-trianguliert - KEINE Auskragungs-Falle.
    Ohne Kantenpunkte im Fenster (Kantenstufe hat dort nicht gesucht, z. B. ueber der LoD2-Wandoberkante): 'Fotokanten nicht abgedeckt' -> keine Aenderung.
 5. ENTSCHEIDUNG (Guard): angleichen NUR, wenn Wolke UND Fotokanten belegt sind, |delta_wolke - delta_kanten| <= EINIG_M, MIN_DZ <= |delta| <= MAX_DZ
    (MAX_DZ = Suchweite der Linienpaarung des Hoehensitzes: weiter weg ist der Partner nicht eindeutig - lieber Befund als falsche Verschiebung). delta = Mittel
    beider Quellen. Sonst bleibt die Linie, Grund im JSON (sitzt / nur Wolke / nur Kanten / uneinig / mehrdeutig / nicht abgedeckt / zu weit / Faltung).
    Zuege, die laut Wolke sitzen (Stimme bei delta 0), sind ANKER (delta 0) und begrenzen jede Verschiebung.
 6. KORREKTUR = monotone Hoehenabbildung je Seite (stueckweise linear zwischen Ankern/Zuegen, Rampe RAMPE_M, im t-Bereich des Zuges mit Rampe T_RAMPE, nur in der
    Aussenschale SCHALE_M der Seite; Ecken = gewichtetes Mittel der Seiten). Faltungs-Guard: Steigung der Abbildung >= FALT_MIN, sonst wird der schwaechere
    Zug verworfen. Der Generator wendet sie als letzten Schritt an (bauteile.hoehen_aus_json -> Manifold.warp_batch); Beleg je Bauteil in elemente.json.
 7. BAUTEIL-ZUORDNUNG (nur Bericht): Elemente aus elemente.json, deren z-Werte (Felder/Text) <= ZUORD_M bei der Linie liegen.
 Basis: Ist das gemessene STL schon MIT einer frueheren Korrektur gebaut (Beleg 'Hoehenangleich' in elemente.json, STL neuer als das JSON), werden die
 Modellpunkte zuerst zurueckgerechnet (Fixpunkt) - die Stufe misst immer gegen den unkorrigierten Bau, kein Aufschaukeln.
Ausgabe: JSON {zeit, stl, kanten, schwellen, rahmen, seiten: {achse: {name, zuege: [...]}}, korrekturen: [...], anker: [...], n_angenommen};
 Bild (optional): je Seite Aufriss t x z mit den Zuegen (gruen angeglichen + Pfeil, grau Anker, orange nur Wolke, blau nur Kanten/uneinig, violett ohne Beleg).
Exit 0 = mindestens eine Korrektur angenommen (Neubau noetig), 2 = gerechnet, keine Korrektur, 1 = Aufruf/Daten falsch, 3 = keine Kantenpunkte (nur Bericht).
Umgebung: /media/oem/scan/venv-seg/bin/python -I (numpy, scipy, cv2; KEINE GPU), RAM ~0,7 GB, < 1 min CPU.
"""
import sys, os, json, time, argparse, re
import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)

MIN_STREIFEN = 3; KETTE_DS = 2; KETTE_DZ = 0.20
VOTE_SCHRITT = 0.05; VOTE_TOL = 0.10; STUETZ_MIN = 0.5; MEHRDEUTIG = 0.8; MEHRDEUTIG_ABST = 0.3
MIN_DZ = 0.10; MAX_DZ = 1.0; EINIG_M = 0.15
KANT_BIN = 0.05; KANT_SCHALE = 1.0; KANT_MIN = 20; KANT_PROM = 2.0; KANT_VORRANG = 1.5; KANT_FENSTER = 0.10
RAMPE_M = 1.0; T_RAMPE = 1.0; SCHALE_M = (1.5, 3.0); FALT_MIN = 0.3; ZUORD_M = 0.3
ELEMENT_BELEG = "Hoehenangleich"


# ---------------------------------------------------------------- Linienzuege
def zuege(Lm, dz, geo, DZ):
    """Modell-Linien -> Linienzuege (Union-Find: gleiches Vorzeichen, Streifenabstand <= KETTE_DS, Hoehenabstand <= KETTE_DZ) mit >= MIN_STREIFEN Streifen."""
    n = len(Lm); par = list(range(n))

    def f(a):
        while par[a] != a: par[a] = par[par[a]]; a = par[a]
        return a
    for a in range(n):
        for b in range(a + 1, n):
            if Lm[a][2] == Lm[b][2] and abs(Lm[a][0] - Lm[b][0]) <= KETTE_DS and abs(Lm[a][1] - Lm[b][1]) * DZ <= KETTE_DZ: par[f(a)] = f(b)
    grp = {}
    for a in range(n): grp.setdefault(f(a), []).append(a)
    out = []
    for idx in grp.values():
        st = sorted({Lm[k][0] for k in idx})
        if len(st) < MIN_STREIFEN: continue
        out.append(dict(idx=idx, vz=int(Lm[idx[0]][2]), streifen=st, zi=[float(Lm[k][1]) for k in idx], staerke=float(np.sum([Lm[k][3] for k in idx]))))
    return out


def wolke_stimme(zug, Lm, Lw, DZ):
    """Verschiebungs-Abstimmung gegen die Wolken-Linien -> dict(delta, stuetze, stuetze0, zweite, mehrdeutig) (delta in m, None ohne Mehrheit)."""
    W = {}
    for s, z, sg, _ in Lw: W.setdefault((s, sg), []).append(z * DZ)
    W = {k: np.asarray(v) for k, v in W.items()}
    zm = [(Lm[k][0], Lm[k][1] * DZ) for k in zug["idx"]]; ns = len(zug["streifen"])
    deltas = np.round(np.arange(-MAX_DZ, MAX_DZ + 1e-9, VOTE_SCHRITT), 3)

    def stimmen(d):
        hit = set(); off = []
        for s, z in zm:
            w = W.get((s, zug["vz"]))
            if w is None: continue
            e = w - (z + d); i = int(np.argmin(np.abs(e)))
            if abs(e[i]) <= VOTE_TOL: hit.add(s); off.append(d + e[i])
        return len(hit), off
    sc = np.array([stimmen(d)[0] for d in deltas], float)
    b = int(np.argmax(sc - 1e-3 * np.abs(deltas))); best = sc[b]
    st0 = stimmen(0.0)[0] / ns
    weit = np.abs(deltas - deltas[b]) > MEHRDEUTIG_ABST; zweite = float(sc[weit].max()) if weit.any() else 0.0
    if best / ns < STUETZ_MIN: return dict(delta=None, stuetze=round(best / ns, 3), stuetze0=round(st0, 3), zweite=round(zweite / ns, 3), mehrdeutig=False)
    d = float(np.median(stimmen(float(deltas[b]))[1]))
    return dict(delta=round(d, 3), stuetze=round(best / ns, 3), stuetze0=round(st0, 3), zweite=round(zweite / ns, 3), mehrdeutig=bool(zweite >= MEHRDEUTIG * best))


def kanten_hist(KP, ax, geo, t0, t1, r_aussen, zlo, zhi):
    """Hoehen-Histogramm der triangulierten Kantenpunkte in der Aussenschale der Seite (o >= r_aussen - KANT_SCHALE), t in [t0, t1] -> (h geglaettet, Mitten, n)."""
    import hoehensitz as HS
    i, sg, j, mitte = HS.seiten_rahmen(ax, geo["lo"], geo["hi"])
    o = (KP[:, i] - mitte) * sg
    m = (o > 0) & (o >= r_aussen - KANT_SCHALE) & (KP[:, j] >= t0) & (KP[:, j] <= t1) & (KP[:, 2] >= zlo) & (KP[:, 2] <= zhi)
    e = np.arange(zlo, zhi + KANT_BIN, KANT_BIN); h, _ = np.histogram(KP[m, 2], bins=e)
    hs = np.convolve(np.pad(h.astype(float), 1, mode="edge"), [0.25, 0.5, 0.25], mode="valid")
    return hs, 0.5 * (e[1:] + e[:-1]), int(m.sum())


def kanten_beleg(h, zc, z_alt, z_soll):
    """Spitze der Kantenpunkte bei z_soll (+-KANT_FENSTER) gegen den Untergrund und gegen die Stelle der Modell-Linie z_alt -> dict(beleg, delta, ...)."""
    if not len(h) or h.sum() < KANT_MIN: return dict(beleg=False, grund="Fotokanten nicht abgedeckt", n=int(h.sum()) if len(h) else 0)
    bg = max(1.0, float(np.median(h)))
    w = np.abs(zc - z_soll) <= KANT_FENSTER; a = np.abs(zc - z_alt) <= KANT_FENSTER
    k_neu = float(h[w].max()) if w.any() else 0.0; k_alt = float(h[a].max()) if a.any() else 0.0
    if k_neu < KANT_PROM * bg:
        if k_alt >= KANT_PROM * bg: return dict(beleg=False, grund=f"Fotokanten bestaetigen die MODELL-Hoehe (Spitze {k_alt:.0f} dort, {k_neu:.0f} bei der Wolken-Hoehe, Untergrund {bg:.0f})", k_neu=k_neu, k_alt=k_alt, untergrund=bg, bestaetigt_modell=True)
        return dict(beleg=False, grund=f"keine Kantenspitze bei der Wolken-Hoehe ({k_neu:.0f} < {KANT_PROM:g} x Untergrund {bg:.0f})", k_neu=k_neu, k_alt=k_alt, untergrund=bg)
    if k_neu < KANT_VORRANG * k_alt: return dict(beleg=False, grund=f"Fotokanten stuetzen die Modell-Hoehe mindestens ebenso ({k_alt:.0f} gegen {k_neu:.0f})", k_neu=k_neu, k_alt=k_alt, untergrund=bg, bestaetigt_modell=k_alt >= KANT_PROM * bg)
    ii = np.nonzero(w)[0]; p = ii[int(np.argmax(h[ii]))]; nb = np.arange(max(0, p - 2), min(len(h), p + 3))
    zp = float(np.average(zc[nb], weights=np.maximum(h[nb] - bg, 1e-6)))
    return dict(beleg=True, delta=round(zp - z_alt, 3), k_neu=k_neu, k_alt=k_alt, untergrund=bg)


# ---------------------------------------------------------------- Hoehenabbildung (auch vom Generator benutzt)
def ueberlappt(a, b):
    """t-Bereiche zweier Zuege (mit Rampe T_RAMPE) ueberlappen - nur dann begrenzt der eine die Verschiebung des anderen."""
    return a["t0"] - T_RAMPE < b["t1"] + T_RAMPE and b["t0"] - T_RAMPE < a["t1"] + T_RAMPE


def _seite_dz(P, s, korr, anker):
    """Verschiebung in z fuer die Punkte P einer Seite s (dict achse/i/sg/j/mitte/r_wand) aus ihren Korrekturen (stueckweise linear zwischen Nullpunkten)."""
    o = (P[:, s["i"]] - s["mitte"]) * s["sg"]; t = P[:, s["j"]]; z = P[:, 2]
    w_s = np.clip((o - (s["r_wand"] - SCHALE_M[1])) / (SCHALE_M[1] - SCHALE_M[0]), 0.0, 1.0)
    d = np.zeros(len(P))
    for q in korr:
        if q["achse"] != s["achse"]: continue
        z0, dz = float(q["z"]), float(q["dz"])
        nullen = [float(r["z"]) for r in list(anker) + list(korr) if r is not q and r["achse"] == s["achse"] and ueberlappt(r, q)]
        unten = max([z0 - abs(dz) - RAMPE_M] + [x for x in nullen if x < z0 - 1e-6]); oben = min([z0 + abs(dz) + RAMPE_M] + [x for x in nullen if x > z0 + 1e-6])
        tri = np.where(z <= z0, np.clip((z - unten) / max(1e-6, z0 - unten), 0, 1), np.clip((oben - z) / max(1e-6, oben - z0), 0, 1))
        wt = np.clip(np.minimum(t - (q["t0"] - T_RAMPE), (q["t1"] + T_RAMPE) - t) / T_RAMPE, 0, 1)
        d += dz * tri * wt
    return d, w_s


def verschiebung(P, J):
    """Hoehenverschiebung dz je Punkt (Modellrahmen, Meter) aus einem hoehen_angleich-JSON (nur angenommene Korrekturen). Ecken: gewichtetes Mittel der Seiten."""
    P = np.asarray(P, float); korr = [q for q in J.get("korrekturen", []) if q.get("angenommen")]
    if not korr or not len(P): return np.zeros(len(P))
    num = np.zeros(len(P)); den = np.zeros(len(P))
    for s in J.get("seiten_rahmen", []):
        if not any(q["achse"] == s["achse"] for q in korr): continue
        d, w = _seite_dz(P, s, korr, J.get("anker", [])); num += w * d; den += w
    return num / np.maximum(1.0, den)


def verschoben(V, J):
    """Fuer Manifold.warp_batch: (n,3) -> (n,3) mit verschobenem z."""
    V = np.array(V, float, copy=True); V[:, 2] += verschiebung(V, J); return V


def zurueckrechnen(P, J, n_iter=6):
    """Umkehrung der Abbildung (Fixpunkt z_b = z - dz(t, z_b)); konvergiert, da die Steigung >= FALT_MIN."""
    Q = np.array(P, float, copy=True)
    for _ in range(n_iter):
        R = Q.copy(); Q[:, 2] = P[:, 2] - verschiebung(R, J)
    return Q.astype(np.float32)


def faltung_pruefen(korr, anker, achse):
    """Steigung der Abbildung zwischen benachbarten Kontrollpunkten einer Seite (Anker dz 0) >= FALT_MIN -> Liste verworfener Korrektur-Indizes."""
    weg = set()
    for k, q in enumerate(korr):
        if q["achse"] != achse or not q.get("angenommen", True): continue
        z0, dz = float(q["z"]), float(q["dz"])
        for r in list(anker) + [x for x in korr if x is not q and x.get("angenommen", True)]:
            if r["achse"] != achse or not ueberlappt(r, q): continue
            zr, dr = float(r["z"]), float(r.get("dz", 0.0)) if r in korr else 0.0
            if abs(zr - z0) < 1e-6 or ((zr + dr) - (z0 + dz)) / (zr - z0) < FALT_MIN:
                weg.add(k if r not in korr or q["stuetze"] <= r["stuetze"] else korr.index(r))
    return sorted(weg)


# ---------------------------------------------------------------- Bauteil-Zuordnung (Bericht)
def element_hoehen(elemente):
    out = []
    for e in elemente or []:
        zs = []
        for k, v in e.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool) and (k.startswith("z") or k.endswith("_z") or "_z" in k or k in ("traufe", "first", "hoehe", "mitte_z", "umgang_z0", "umgang_z1")): zs.append(float(v))
        for m in re.finditer(r"z\s*(-?\d+(?:\.\d+)?)(?:\s*\.\.\s*(-?\d+(?:\.\d+)?))?", str(e.get("element", ""))):
            zs.append(float(m.group(1)))
            if m.group(2): zs.append(float(m.group(2)))
        for m in re.finditer(r"(?:Traufe|Knick|Aussenkante|Wandanschluss|Spitze|Krempe)\s*z\s*(-?\d+(?:\.\d+)?)", str(e.get("element", ""))): zs.append(float(m.group(1)))
        if zs: out.append((str(e.get("element", ""))[:90], sorted(set(round(z, 2) for z in zs))))
    return out


def zuordnen(z, eh):
    tr = [(min(abs(z - x) for x in zs), name) for name, zs in eh if min(abs(z - x) for x in zs) <= ZUORD_M]
    return [n for _, n in sorted(tr)[:3]]


# ---------------------------------------------------------------- Ablauf
def messen(L, KP, geo, eh, rahmen):
    """Alle Seiten -> (seiten-Bericht, korrekturen, anker, seiten_rahmen) im MODELLRAHMEN (Kamerarahmen minus rahmen)."""
    import hoehensitz as HS
    DZ = HS.DZ_M; PM, PW = L["PM"], L["PW"]; seiten, korr, anker, sr = {}, [], [], []
    for ax in L["achsen"]:
        bew, Lm, Lw, rm, rw = HS.seite_messen(PM, PW, ax, geo)
        i, sg, j, mitte = HS.seiten_rahmen(ax, geo["lo"], geo["hi"])
        r_wand = float(np.nanmedian(rm)) if np.isfinite(rm).any() else 0.0
        sr.append(dict(achse=ax, i=i, sg=float(sg), j=j, mitte=float(mitte - rahmen[i]), r_wand=r_wand))
        zl = []
        for zg in zuege(Lm, bew["dz"], geo, DZ):
            z_alt = float(HS.z_m(geo, float(np.median(zg["zi"]))))
            t0 = float(geo["t0"][j] + min(zg["streifen"]) * HS.STREIF_M); t1 = float(geo["t0"][j] + (max(zg["streifen"]) + 1) * HS.STREIF_M)
            st = sorted(zg["streifen"]); ra = np.concatenate([rm[st], rw[st]], axis=1)
            k_lo, k_hi = int((z_alt - 0.5 - geo["z0"]) / DZ), int((z_alt + 0.5 - geo["z0"]) / DZ)
            seg = ra[:, max(0, k_lo):max(1, k_hi)]; r_aussen = float(np.nanmedian(seg)) if np.isfinite(seg).any() else r_wand
            ws = wolke_stimme(zg, Lm, Lw, DZ)
            e = dict(z=round(z_alt - rahmen[2], 3), vorzeichen=zg["vz"], streifen=len(st), t0=round(t0 - rahmen[j], 2), t1=round(t1 - rahmen[j], 2),
                     wolke=ws, bauteile=zuordnen(z_alt - rahmen[2], eh))
            if ws["delta"] is not None and abs(ws["delta"]) < MIN_DZ and not ws["mehrdeutig"]:
                e.update(ergebnis="sitzt", grund=f"Wolken-Linie in {ws['stuetze']:.0%} der Streifen < {MIN_DZ:g} m"); anker.append(dict(achse=ax, z=e["z"], t0=e["t0"], t1=e["t1"], fest="sitzt"))
                zl.append(e); continue
            if ws["delta"] is None: e.update(ergebnis="behalten", grund=f"keine Wolken-Mehrheit (beste Stimme {ws['stuetze']:.0%} < {STUETZ_MIN:.0%})"); zl.append(e); continue
            if ws["mehrdeutig"]: e.update(ergebnis="behalten", grund=f"Wolke mehrdeutig (zweite Spitze {ws['zweite']:.0%} gegen {ws['stuetze']:.0%})"); zl.append(e); continue
            h, zc, nk = kanten_hist(KP, ax, geo, t0, t1, r_aussen, z_alt - MAX_DZ - 0.5, z_alt + MAX_DZ + 0.5) if KP is not None else (np.zeros(0), np.zeros(0), 0)
            kb = kanten_beleg(h, zc, z_alt, z_alt + ws["delta"]); e["kanten"] = dict({k: v for k, v in kb.items() if k != "beleg"}, n=nk)
            if not kb["beleg"]: e.update(ergebnis="behalten", grund="nur Wolke: " + kb["grund"]); zl.append(e); continue
            if abs(kb["delta"] - ws["delta"]) > EINIG_M: e.update(ergebnis="behalten", grund=f"Quellen uneinig (Wolke {ws['delta']:+.2f}, Kanten {kb['delta']:+.2f} m)"); zl.append(e); continue
            d = 0.5 * (kb["delta"] + ws["delta"])
            if abs(d) < MIN_DZ: e.update(ergebnis="sitzt", grund=f"beide Quellen < {MIN_DZ:g} m"); anker.append(dict(achse=ax, z=e["z"], t0=e["t0"], t1=e["t1"], fest="sitzt")); zl.append(e); continue
            if abs(d) > MAX_DZ: e.update(ergebnis="behalten", grund=f"zu weit ({d:+.2f} m > {MAX_DZ:g} m)"); zl.append(e); continue
            e.update(ergebnis="angleichen", dz=round(d, 3), grund=f"Wolke {ws['delta']:+.2f} m ({ws['stuetze']:.0%} der Streifen) und Fotokanten {kb['delta']:+.2f} m einig")
            korr.append(dict(achse=ax, z=e["z"], dz=round(d, 3), t0=e["t0"], t1=e["t1"], stuetze=ws["stuetze"], angenommen=True, grund=e["grund"], bauteile=e["bauteile"]))
            zl.append(e)
        for e in zl:                                   # jede NICHT belegte Linie bleibt, wo sie ist: Festpunkt fuer die Abbildung (keine Mitnahme ohne Beleg)
            if e.get("ergebnis") == "behalten": anker.append(dict(achse=ax, z=e["z"], t0=e["t0"], t1=e["t1"], fest="unbelegt"))
        seiten[ax] = dict(name=L["namen"][ax], zuege=zl)
    for ax in L["achsen"]:
        while True:
            weg = faltung_pruefen(korr, anker, ax)
            if not weg: break
            for k in weg:
                korr[k]["angenommen"] = False; korr[k]["grund"] += " | VERWORFEN: Faltung (unbelegte/sitzende Nachbarlinie zu nah, Steigung < %g)" % FALT_MIN
                anker.append(dict(achse=ax, z=korr[k]["z"], t0=korr[k]["t0"], t1=korr[k]["t1"], fest="verworfen"))
                for e in seiten[ax]["zuege"]:
                    if e.get("ergebnis") == "angleichen" and e["z"] == korr[k]["z"] and e["t0"] == korr[k]["t0"]: e.update(ergebnis="behalten", grund=korr[k]["grund"])
    return seiten, korr, anker, sr


def kontrollbild(pfad, seiten, geo, rahmen):
    import cv2
    px = 14; bilder = []
    farbe = dict(angleichen=(60, 170, 40), sitzt=(150, 150, 150))
    for ax, S in seiten.items():
        j = 1 if ax[1] == "x" else 0; nt = int(geo["nt"][j]); H = int((geo["hi"][2] - geo["z0"] + 2) * px); Wd = nt * px
        img = np.full((H + 30, max(Wd, 220), 3), 255, np.uint8)
        zy = lambda z: 30 + H - int((z + rahmen[2] - geo["z0"]) * px); tx = lambda t: int((t + rahmen[j] - geo["t0"][j]) * px)
        for zm in range(0, int(geo["hi"][2]) + 1, 5): cv2.line(img, (0, zy(zm)), (5, zy(zm)), (0, 0, 0), 1); cv2.putText(img, str(zm), (7, zy(zm) + 4), 0, 0.3, (0, 0, 0), 1)
        for e in S["zuege"]:
            g = e.get("ergebnis"); gr = e.get("grund", "")
            c = farbe.get(g) or ((40, 40, 220) if "Faltung" in gr else ((220, 120, 40) if ("odell-Hoehe" in gr or "MODELL" in gr or "uneinig" in gr) else ((40, 140, 240) if gr.startswith("nur Wolke") else (160, 60, 160))))
            cv2.line(img, (tx(e["t0"]), zy(e["z"])), (tx(e["t1"]), zy(e["z"])), c, 2)
            if g == "angleichen":
                xm = (tx(e["t0"]) + tx(e["t1"])) // 2; cv2.arrowedLine(img, (xm, zy(e["z"])), (xm, zy(e["z"] + e["dz"])), (0, 120, 0), 1, tipLength=0.3)
            elif e.get("wolke", {}).get("delta") is not None and g != "sitzt":
                cv2.line(img, (tx(e["t0"]), zy(e["z"] + e["wolke"]["delta"])), (tx(e["t1"]), zy(e["z"] + e["wolke"]["delta"])), (200, 200, 200), 1)
        n_a = sum(1 for e in S["zuege"] if e.get("ergebnis") == "angleichen")
        cv2.putText(img, f"{S['name']} ({ax}) Zuege {len(S['zuege'])} angeglichen {n_a}", (3, 14), 0, 0.38, (20, 20, 20), 1, cv2.LINE_AA)
        bilder.append(img)
    if not bilder: return
    hm = max(b.shape[0] for b in bilder); bilder = [np.vstack([b, np.full((hm - b.shape[0], b.shape[1], 3), 255, np.uint8)]) for b in bilder]
    B = np.hstack([np.hstack([b, np.full((hm, 8, 3), 255, np.uint8)]) for b in bilder]); leg = np.full((20, B.shape[1], 3), 255, np.uint8)
    cv2.putText(leg, "gruen angeglichen (Pfeil) | grau sitzt | orange nur Wolke (hellgrau: Wolken-Hoehe) | blau Kanten stuetzen Modell/uneinig | rot beide einig, Faltung verworfen | violett ohne Mehrheit", (4, 14), 0, 0.34, (20, 20, 20), 1, cv2.LINE_AA)
    cv2.imwrite(pfad, np.vstack([B, leg]))


def main(argv=None):
    import hoehensitz as HS
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--stl"); ap.add_argument("--wolke"); ap.add_argument("--fotosatz"); ap.add_argument("--kanten")
    ap.add_argument("--aus"); ap.add_argument("--bild"); ap.add_argument("--nur-messen", action="store_true", help="JSON mit angenommen=false fuer alle Korrekturen (nur Bericht)")
    ap.add_argument("--n-wolke", type=int, default=HS.N_WOLKE); ap.add_argument("--n-modell", type=int, default=HS.N_MODELL); a = ap.parse_args(argv)
    t_start = time.time()
    L = HS.laden(a)
    if isinstance(L, str): print(L); return 1
    rahmen = L["rahmen"]; aus = a.aus or os.path.join(L["audit"], "hoehen_angleich.json")
    # Basis: STL schon mit frueherer Korrektur gebaut? -> Modellpunkte zurueckrechnen (Kamerarahmen -> Modellrahmen -> zurueck -> Kamerarahmen)
    basis = "unkorrigiertes STL"
    if os.path.exists(aus):
        try:
            J0 = json.load(open(aus)); ep = os.path.join(L["root"], L["obj"].get("elemente") or "-")
            beleg = os.path.exists(ep) and any(ELEMENT_BELEG in str(e.get("element", "")) for e in json.load(open(ep)))
            if beleg and any(q.get("angenommen") for q in J0.get("korrekturen", [])) and os.path.getmtime(L["stl"]) > os.path.getmtime(aus):
                PMm = L["PM"].astype(float) - rahmen; L["PM"] = (zurueckrechnen(PMm, J0) + rahmen).astype(np.float32)
                basis = f"zurueckgerechnet aus {os.path.basename(aus)} ({sum(1 for q in J0['korrekturen'] if q.get('angenommen'))} Korrekturen im Bau)"
        except Exception as ex: print(f"HINWEIS: frueheres {aus} nicht lesbar ({type(ex).__name__}: {ex}) - messe das STL wie gebaut")
    kp = a.kanten
    if not kp:
        import pfade
        kp = os.path.join(pfade.DATEN, os.path.basename(L["od"]), "kanten", "sweep.npz")
    KP = None
    if os.path.exists(kp):
        KP = np.load(kp)["P"].astype(np.float32) + rahmen.astype(np.float32)   # ANNAHME (wie kantenstufe): Kantenpunkte im Modellrahmen des STL
    else: print(f"HINWEIS: keine Kantenpunkte ({kp}) - nur Bericht, keine Korrektur (zweite Quelle fehlt)")
    ep = os.path.join(L["root"], L["obj"].get("elemente") or "-"); eh = element_hoehen(json.load(open(ep))) if os.path.exists(ep) else []
    geo = HS.geo_aus(L["lo"], L["hi"])
    seiten, korr, anker, sr = messen(L, KP, geo, eh, rahmen)
    if a.nur_messen:
        for q in korr: q["angenommen"] = False
    n_ang = sum(1 for q in korr if q.get("angenommen"))
    erg = dict(zeit=time.strftime("%Y-%m-%d %H:%M:%S"), quelle="tools/hoehen_angleich.py (Wolken-Linien + triangulierte Fotokanten, beide noetig)", stl=os.path.abspath(L["stl"]),
               kanten=os.path.abspath(kp) if KP is not None else None, basis=basis, rahmen=[round(float(x), 4) for x in rahmen], sek=round(time.time() - t_start, 1),
               schwellen=dict(min_streifen=MIN_STREIFEN, vote_tol=VOTE_TOL, stuetz_min=STUETZ_MIN, min_dz=MIN_DZ, max_dz=MAX_DZ, einig_m=EINIG_M, kant_prom=KANT_PROM,
                              kant_vorrang=KANT_VORRANG, kant_schale=KANT_SCHALE, rampe_m=RAMPE_M, t_rampe=T_RAMPE, schale_m=list(SCHALE_M), falt_min=FALT_MIN),
               seiten=seiten, seiten_rahmen=sr, korrekturen=korr, anker=anker, n_angenommen=n_ang)
    os.makedirs(os.path.dirname(os.path.abspath(aus)), exist_ok=True)
    json.dump(erg, open(aus + ".tmp", "w"), indent=1, ensure_ascii=False); os.replace(aus + ".tmp", aus)
    if a.bild:
        try: kontrollbild(a.bild, seiten, geo, rahmen)
        except Exception as ex: print(f"HINWEIS: Kontrollbild nicht geschrieben ({type(ex).__name__}: {ex})")
    print(f"HOEHEN-ANGLEICH ({basis}; Kanten {'ja' if KP is not None else 'FEHLEN'}):")
    for ax, S in seiten.items():
        print(f"  {S['name']} ({ax}): {len(S['zuege'])} Linienzuege")
        for e in S["zuege"]:
            if e.get("ergebnis") == "sitzt": continue
            print(f"    z {e['z']:6.2f} ({e['streifen']} Streifen, t {e['t0']}..{e['t1']}) -> {e['ergebnis']}" + (f" dz {e['dz']:+.2f}" if e.get("dz") is not None else "")
                  + f": {e['grund']}" + (f" | {e['bauteile'][0]}" if e.get("bauteile") else ""))
    print(f"{n_ang} Korrektur(en) angenommen -> {aus} ({erg['sek']} s)")
    if KP is None: return 3
    return 0 if n_ang else 2


if __name__ == "__main__":
    sys.exit(main())
