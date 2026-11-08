#!/usr/bin/env python3
"""elementbuch.py - Elementbuch der Stufen-Laeufer (S1b, 2026-11-06): jedes neue/geaenderte/entfernte Element eines Kandidaten muss LOKAL bestehen.

Hintergrund (modelle/LOG_2026-11-05_FEHLER_UND_STAND.md, Fehler 5): ein Kandidat war im Mittel ueber alle Fotos besser, hat aber ein gutes Altelement
(4 Boegen der Hauptfassade) verloren; der globale Gewinn kam aus anderen Elementen. Der Mittelwert sieht das nicht.

Daten: Elementdatei des Baus (ELEMENTE_AUS; Beleg-Felder `geo_elemente` + `rahmen` + `fassade` aus baukasten_gen.fassade_auto / bloecke_wolke) und je Foto
die Kostenkarte von foto_diff (--kostenkarte: mkp, fkp, dF, dM; dF/dM in Kappen, 1.0 = Kappe = Abstand >= tol).
Je Element und Foto: Bildrechteck (3D-Box + 0.5 m Rand, mit der Kamera des Fotos projiziert), lokale Kennzahlen
  rot_lok  = Anteil der Modellkantenpixel im Rechteck mit Abstand >= tol (Modellkante ohne Fotokante)
  gelb_lok = Anteil der Fotokantenpixel im Rechteck mit Abstand >= tol (Fotokante ohne Modellkante)
ABWEICHUNG von SPEC_S1b ("dF > 1.0"): dF/dM sind durch die Kappe geteilt UND auf die Kappe gekappt (foto_diff Z. 456: np.minimum(..., kap_)), also nie > 1.0;
"Abstand >= tol" ist daher `>= 0.999` (Beweis: T0/T1 in test_tor_elementbuch.py).

Regel je Element (GEAENDERT nach Test T2 (5.11.), Koordinator-Entscheid): rot und gelb tauschen sich bei jeder Kantenkorrektur aus (T2-Umkehrung von T4: Foto 000 rot 0.23->0.40,
gelb 0.23->0.10; die alte Regel 'ein Foto schlechter' lehnte die RICHTIGE Korrektur ab, in 8-9 von 10 Fotos besser). Darum gilt je Foto die SUMME rot_lok+gelb_lok (ueber die in alt und
neu beurteilbaren Arten): besser = Summe faellt um >= EPS in >= 2/3 der beurteilbaren Fotos (mindestens 2) und steigt in keinem um > EPS; schlechter spiegelbildlich;
gleich = in keinem Foto Aenderung > EPS; sonst 'gemischt' (blockiert NICHT, Log). nicht beurteilbar = < 30 Kantenpixel je Art in allen Fotos.
Ein Kandidat faellt durch (e) nur, wenn ein Element 'schlechter' ist; nur 'nicht beurteilbar' = ungeprueft (Log).
Nicht umgesetzt (Spec "optional"): Verdeckungspruefung der Elementmitte (die Kostenkarte nimmt Verdecker aus mkp heraus, foto_diff occ).
Element-Schluessel: fassade|klasse|u-Mitte(0.1)|z-Mitte(0.1) auch fuer Bloecke (Erker/Galerie): sie tragen ebenfalls Fassadenkoordinaten; die 3D-Box folgt aus dem Rahmen.
"""
import os, sys, json, glob, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

EPS = 0.02          # Spec 3: lokale Besserung/Verschlechterung ab 2 Prozentpunkten (ANNAHME aus der Spec, nicht nachjustiert)
MIN_KANTEN = 30     # Spec 3: Mindestzahl Kantenpixel je Art
MIN_PIXEL = 400     # Spec 3: Bildrechteck mindestens 400 Pixel
RAND_M = 0.5        # Spec 3: Rand der Box
FORM_TOL = 0.005    # Elemente mit gleichem Schluessel gelten als 'gleich', wenn Box und Formwerte auf 5 mm uebereinstimmen


def schluessel(fid, klasse, g):
    return f"{fid}|{klasse}|{0.5 * (g['u0'] + g['u1']):+.1f}|{0.5 * (g['z0'] + g['z1']):.1f}"


def elemente_laden(pfad):
    """Elementdatei -> ({schluessel: element}, uebersprungen). Elemente ohne Geometrie (Belege ohne geo_elemente auf Fassaden) werden gemeldet, nicht still ignoriert."""
    E = json.load(open(pfad)); out = {}; weg = []
    for b in E:
        if b.get("geo_elemente") and b.get("rahmen"):
            for g in b["geo_elemente"]:
                k = schluessel(b["fassade"], g["klasse"], g); i = 2
                while k in out: k = f"{schluessel(b['fassade'], g['klasse'], g)}#{i}"; i += 1
                out[k] = dict(g, fassade=b["fassade"], rahmen=b["rahmen"], key=k)
        elif b.get("seite") in ("+x", "-x", "+y", "-y") and str(b.get("element", "")).startswith("Fassade"):
            weg.append(f"{b['seite']}: {b['element'][:80]}")
    return out, weg


def gleich_geformt(a, b):
    za = [a[k] for k in ("u0", "u1", "z0", "z1", "s0", "s1")] + list(a.get("form", [])); zb = [b[k] for k in ("u0", "u1", "z0", "z1", "s0", "s1")] + list(b.get("form", []))
    return len(za) == len(zb) and all(abs(x - y) <= FORM_TOL for x, y in zip(za, zb))


def box_ecken(el, rand=RAND_M):
    """8 Ecken der Elementbox (u, s, z) +- rand in Weltkoordinaten: Welt = o + d*u + n*s, z = z (baukasten_gen T)."""
    o = np.array(el["rahmen"]["o"], float); d = np.array(el["rahmen"]["d"], float); n = np.array(el["rahmen"]["n"], float); P = []
    for u in (el["u0"] - rand, el["u1"] + rand):
        for s in (el["s0"] - rand, el["s1"] + rand):
            for z in (el["z0"] - rand, el["z1"] + rand):
                xy = o[:2] + d[:2] * u + n[:2] * s; P.append([xy[0], xy[1], z])
    return np.array(P)


class Kameras:
    """Kamera je Foto (K-<nr>.json wie foto_diff): R, t, f, cx, cy; Aufloesung = Kostenkarte (Originalbild, entzerrt)."""
    def __init__(self, objp, obj, root):
        import fehlteile_finden as FF
        self.FF, self.objp, self.obj, self.root, self.c = FF, objp, obj, root, {}

    def holen(self, nr, W, H):
        if nr not in self.c:
            kp = self.FF.k_datei(self.objp, self.obj, self.root, nr); K = json.load(open(kp)) if os.path.exists(kp) else {}
            R, t, f, _, _ = self.FF.kamera_laden(K, self.obj, nr, self.root, W, H); km = self.FF.kmatrix(K.get("kamera", {}) or {"f_px": f}, W, H)
            self.c[nr] = (np.asarray(R, float), np.asarray(t, float), float(f), float(km[0, 2]), float(km[1, 2]))
        return self.c[nr]


def roi(kam, nr, W, H, boxen):
    """Bildrechteck (x0, y0, x1, y1) der vereinigten Boxen oder None (hinter der Kamera / < MIN_PIXEL / ausserhalb)."""
    R, t, f, cx, cy = kam.holen(nr, W, H); r = None
    for el in boxen:
        P = box_ecken(el); Pc = P @ R.T + t
        if (Pc[:, 2] < 0.5).any(): return None
        uv = np.c_[f * Pc[:, 0] / Pc[:, 2] + cx, f * Pc[:, 1] / Pc[:, 2] + cy]; q = [uv[:, 0].min(), uv[:, 1].min(), uv[:, 0].max(), uv[:, 1].max()]
        r = q if r is None else [min(r[0], q[0]), min(r[1], q[1]), max(r[2], q[2]), max(r[3], q[3])]
    x0, y0, x1, y1 = int(max(0, np.floor(r[0]))), int(max(0, np.floor(r[1]))), int(min(W, np.ceil(r[2]))), int(min(H, np.ceil(r[3])))
    return (x0, y0, x1, y1) if (x1 - x0) * (y1 - y0) >= MIN_PIXEL else None


class Karte:
    """Eine Kostenkarte, auf rote/gelbe Masken reduziert (Speicher: bool statt float16)."""
    def __init__(self, pfad):
        z = np.load(pfad); self.mkp = z["mkp"]; self.fkp = z["fkp"]
        self.rot = self.mkp & (z["dF"] >= 0.999); self.gelb = self.fkp & (z["dM"] >= 0.999); self.H, self.W = self.mkp.shape

    def lokal(self, r):
        x0, y0, x1, y1 = r; sl = (slice(y0, y1), slice(x0, x1)); nm = int(self.mkp[sl].sum()); nf = int(self.fkp[sl].sum())
        return dict(rot=(float(self.rot[sl].sum()) / nm if nm >= MIN_KANTEN else None), gelb=(float(self.gelb[sl].sum()) / nf if nf >= MIN_KANTEN else None), n_modell=nm, n_foto=nf)


def vergleichen(alt_dat, neu_dat, fotos, kam):
    """alt_dat/neu_dat: dict(elemente=<Elementdatei>, karten={nr: npz}). Rueckgabe dict(elemente={schluessel: dict(status, art, fotos)}, ungeprueft, uebersprungen, geschaetzt)."""
    A, wa = elemente_laden(alt_dat["elemente"]); N, wn = elemente_laden(neu_dat["elemente"]); res = {}
    for k in sorted(set(A) | set(N)):
        if k in A and k in N: art = "gleich_geformt" if gleich_geformt(A[k], N[k]) else "geaendert"
        else: art = "neu" if k in N else "entfernt"
        res[k] = dict(art=art, fassade=(N.get(k) or A.get(k))["fassade"], klasse=(N.get(k) or A.get(k))["klasse"], fotos={})
    pruef = [k for k, v in res.items() if v["art"] != "gleich_geformt"]
    nr_ok = [nr for nr in fotos if nr in alt_dat.get("karten", {}) and nr in neu_dat.get("karten", {}) and os.path.exists(alt_dat["karten"][nr]) and os.path.exists(neu_dat["karten"][nr])]
    for nr in nr_ok:
        if not pruef: break
        ka, kn = Karte(alt_dat["karten"][nr]), Karte(neu_dat["karten"][nr])
        for k in pruef:
            boxen = [e[k] for e in (A, N) if k in e]; r = roi(kam, nr, kn.W, kn.H, boxen)
            if r is None: continue
            la, ln = ka.lokal(r), kn.lokal(r); f = {}
            for art in ("rot", "gelb"):
                if la[art] is not None and ln[art] is not None: f[art] = [round(la[art], 3), round(ln[art], 3)]
            res[k]["fotos"][nr] = dict(roi=list(r), **f, n_modell=[la["n_modell"], ln["n_modell"]], n_foto=ln["n_foto"])
        del ka, kn
    for k in pruef:
        b = sc = n = 0
        for nr, v in res[k]["fotos"].items():
            arten = [x for x in ("rot", "gelb") if x in v]                                          # Summe ueber die Arten, die in alt UND neu beurteilbar sind (neue Elemente: alt hat oft < 30 Modellkantenpixel)
            if not arten: continue
            d = sum(v[x][1] - v[x][0] for x in arten); v["summe"] = [round(sum(v[x][0] for x in arten), 3), round(sum(v[x][1] for x in arten), 3)]
            n += 1; bes = d <= -EPS; sch = d > EPS; b += bes; sc += sch
            v["urteil"] = "besser" if bes else "schlechter" if sch else "gleich"
        drittel = 2.0 / 3.0 * n
        st = ("nicht beurteilbar" if n == 0 else "besser" if b >= 2 and b >= drittel and sc == 0 else "schlechter" if sc >= 2 and sc >= drittel and b == 0
              else "gleich" if b == 0 and sc == 0 else "gemischt")
        res[k].update(n_fotos=n, n_besser=b, n_schlechter=sc, status=st)
    for k, v in res.items():
        if v["art"] == "gleich_geformt": v["status"] = "gleich"
    return dict(elemente=res, uebersprungen=sorted(set(wa) | set(wn)), fotos_mit_karte=nr_ok, eps=EPS)


def pruefen(alt_dat, neu_dat, fotos, kam):
    """Tor (e): -> (ok, gruende, detail). gruende: eine Zeile je schlechtem Element (Buchstabe e)."""
    d = vergleichen(alt_dat, neu_dat, fotos, kam); E = d["elemente"]; gruende = []
    for k, v in E.items():
        if v["status"] == "schlechter":
            schl = [f"{nr} Summe {f['summe'][0]:.2f}->{f['summe'][1]:.2f}" for nr, f in v["fotos"].items() if f.get("urteil") == "schlechter"]
            gruende.append(f"(e) Element {k} ({v['art']}) lokal schlechter in {v['n_schlechter']} von {v['n_fotos']} Fotos: " + "; ".join(schl[:4]))
    z = {s: sum(1 for v in E.values() if v["status"] == s and v["art"] != "gleich_geformt") for s in ("besser", "gleich", "schlechter", "gemischt", "nicht beurteilbar")}
    d["zaehlung"] = z; d["ungeprueft"] = bool(z["nicht beurteilbar"] and not (z["besser"] + z["gleich"] + z["schlechter"] + z["gemischt"]))
    d["gemischt"] = sorted(k for k, v in E.items() if v["status"] == "gemischt")
    return not gruende, gruende, d


def aktualisieren(buch_pfad, neu_dat, fotos, kam, tag, fest_auszug):
    """elemente_best.json nach einer Uebernahme: je Schluessel der uebernommene Stand mit lokalen Kennzahlen je Foto. Nicht mehr vorhandene Elemente fallen raus."""
    N, _ = elemente_laden(neu_dat["elemente"]); buch = json.load(open(buch_pfad)) if os.path.exists(buch_pfad) else {}; neu_b = {}
    for nr in fotos:
        if nr not in neu_dat.get("karten", {}) or not os.path.exists(neu_dat["karten"][nr]): continue
        kn = Karte(neu_dat["karten"][nr])
        for k, e in N.items():
            r = roi(kam, nr, kn.W, kn.H, [e])
            if r is None: continue
            l = kn.lokal(r); neu_b.setdefault(k, {})[nr] = [None if l["rot"] is None else round(l["rot"], 3), None if l["gelb"] is None else round(l["gelb"], 3)]
        del kn
    for k, e in N.items():
        alt = buch.get(k)
        gleich = alt is not None and all(abs(alt["box"][i] - e[c]) <= FORM_TOL for i, c in enumerate(("u0", "u1", "z0", "z1", "s0", "s1"))) and alt.get("form") == e.get("form")
        if gleich and alt.get("lokal"): continue                                                  # unveraendertes Altelement: Eintrag (bester Stand) bleibt
        buch[k] = dict(stand=tag, fassade=e["fassade"], klasse=e["klasse"], box=[e[c] for c in ("u0", "u1", "z0", "z1", "s0", "s1")], form=e.get("form"), fest=fest_auszug, lokal=neu_b.get(k, {}))
    buch = {k: v for k, v in buch.items() if k in N}
    json.dump(buch, open(buch_pfad + ".tmp", "w"), indent=1, ensure_ascii=False); os.replace(buch_pfad + ".tmp", buch_pfad)
    return len(buch)
