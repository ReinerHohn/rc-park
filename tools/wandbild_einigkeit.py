#!/usr/bin/env python3
"""wandbild_einigkeit.py - Deckungsgleichheit eines Wandbilds (ortho_<id>.png) aus seinen Einzelprojektionen (fassade_ortho.py --einzeln).

Befund 23.11.2026 (Lauf 1122t, schwabentor-1122): Wand f01 bekam per Nachholen 31 Fotos, Abdeckung 0,037 -> 0,998, das Tor (seiten_wiederholung gewinn)
meldete GEWINN - aber ortho_f01.png war verschmiert (Nachbarhaeuser, Efeu, Drachenbild doppelt/versetzt), die Tiefe Rauschen. Abdeckung allein sagt nicht,
ob die Fotos dort DASSELBE zeigen. Zwei Masse, beide ohne Wand-IDs und ohne feste Bildinhalte:

1. WAND (wiederverwendet, kein neues Mass): fassade_ortho.py schreibt seit 16.11.2026 die Struktur-Uneinigkeit struktur_<id>.png (je 0,1-m-Block lokal
   normierte Helligkeit je Foto, MAD ueber die Fotos, x100; Doku dort: ~0-25 = dieselbe Struktur, > ~45 = verschiedene Dinge). wand_einigkeit() liest sie
   zusammen mit abdeckung_<id>.png (Fotos je Zelle x 20) und der Wandmaske (polys_uz) und gibt den Anteil EINIGER Zellen (struktur <= S_GRENZE) unter den
   BEURTEILBAREN (>= 3 Fotos, wie fassade_ortho) zurueck. S_GRENZE = 45 ist die dort dokumentierte Grenze, nicht neu gewaehlt.
2. FOTO (neu, braucht ortho_<id>_einzeln/): foto_einigkeit() korreliert je Foto seine lokal normierte Helligkeit (dieselbe Normierung wie struktur_) mit dem
   Median der UEBRIGEN Fotos (leave-one-out, Pearson r ueber die gemeinsam gesehenen Bloecke). Ein Foto mit falscher Kamera zeigt an der Stelle anderes -> r ~ 0.
   Nur Fotos aus fassaden.json 'fotos' der Wand zaehlen (der _einzeln-Ordner sammelt Dateien frueherer Laeufe - 1122t f01: 69 Dateien, 31 gueltig).

Gemessen 23.11.2026 an schwabentor-1122/fassade (Stand nach Teillauf 1122t, Wandmaske), Wand-Einigkeit (Anteil einig unter beurteilbar):
  f00 Nord 0,777 · f03 0,846 · f02 0,779 (nur 4 % beurteilbar) · f04-f07 0,72-0,95 · f01 Sued (verschmiert) 0,459.
  Foto-r gewichtet nach Bloecken: f00 0,58 · f03 0,56 · f01 0,26. Stapel-Nachrechnung (struktur_aus_stapel) f00 0,766 gegen Karte 0,777: gleiches Mass.
  Ausschluss r < R_MIN an f01: 13 von 31 Fotos weg -> einig 0,442 -> 0,721, bedeckt 0,90 -> 0,75 (rettet die Wand teilweise).
ANNAHME E_MIN 0,60: zwischen der schlechtesten guten Wand (f05 0,722) und der verschmierten f01 (0,459), auf 0,05 gerundet; EINE schlechte Wand,
  nicht belastbar als Verteilung - mit jedem weiteren Befund nachmessen (RCPARK_EINIG_MIN).
ANNAHME R_MIN 0,20 (Foto gilt als uneinig): f00 hat eine klare Luecke zwischen 6 Fotos mit |r| <= 0,01 und dem Rest ab 0,27; an f03 liegen 0,16/0,21 nahe
  der Grenze, an f01 ist die Verteilung durchgehend (0,13-0,29) - die Grenze trennt dort nicht sauber (RCPARK_EINIG_R_MIN).
Grenze des Masses: struktur_ ist ein MAD (robust) - bis knapp die Haelfte unabhaengig falscher Fotos gilt eine Wand noch als einig (synthetisch 5 von 9).
Verwandt, nicht ersetzt: wand_feinausrichtung.py (cm-Feinversatz per NCC gegen den Median der anderen, GPU) - hier geht es um grobe Uneinigkeit (falsche Kamera).

  tools/py tools/wandbild_einigkeit.py <fassaden-ordner> [--id f01] [--fotos]      (Bericht je Wand, mit --fotos die schlechtesten Fotos)
"""
import os, sys, json, argparse
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

S_GRENZE = 45.0                                                     # struktur_<id>.png: > ~45 = verschiedene Dinge (fassade_ortho.py, Doku der Karte)
E_MIN = float(os.environ.get("RCPARK_EINIG_MIN", "0.60"))           # ANNAHME, siehe Kopf
R_MIN = float(os.environ.get("RCPARK_EINIG_R_MIN", "0.20"))         # ANNAHME, siehe Kopf
MIN_FOTOS = 3                                                        # wie fassade_ortho (struktur erst ab 3 Fotos je Block)


def wand_maske(F):
    R = F["raster"]; m = np.zeros((R["nz"], R["nu"]), np.uint8)
    for poly in F.get("polys_uz") or []:
        cv2.fillPoly(m, [np.array([[(u - R["u0"]) / R["zelle"], (R["z1"] - z) / R["zelle"]] for u, z in poly], np.int32)], 1)
    if not m.any(): m[:] = 1                                         # ohne Polygone: ganzes Raster
    return m > 0


def wand_einigkeit(ordner, F, maske=None):
    """-> dict(einig_anteil, beurteilt_anteil, einig_flaeche_anteil, zellen) oder None (Karten fehlen/passen nicht).
    einig_anteil = einige / beurteilbare Wandzellen; einig_flaeche_anteil = einige / alle Wandzellen (= 'Abdeckung mit Deckungsgleichheit')."""
    fid = F.get("id"); st = cv2.imread(os.path.join(ordner, f"struktur_{fid}.png"), 0); ab = cv2.imread(os.path.join(ordner, f"abdeckung_{fid}.png"), 0)
    if st is None or ab is None or st.shape != ab.shape: return None
    m = wand_maske(F) if maske is None else maske
    if m.shape != st.shape: return None
    beu = m & (ab >= 20 * MIN_FOTOS); nb = int(beu.sum()); nw = int(m.sum())
    if nb == 0: return dict(einig_anteil=None, beurteilt_anteil=0.0, einig_flaeche_anteil=0.0, zellen=nw)
    ein = beu & (st <= S_GRENZE)
    return dict(einig_anteil=round(float(ein.sum() / nb), 3), beurteilt_anteil=round(nb / max(nw, 1), 3), einig_flaeche_anteil=round(float(ein.sum() / max(nw, 1)), 3), zellen=nw)


def _block_normiert(bgr, ks, k=9):
    """Ein Einzelbild -> lokal normierte Helligkeit je ks-Block (NaN = nicht gesehen); gleiche Normierung wie fassade_ortho struktur_ ((L-mu)/(sd+6), 9er-Fenster)."""
    da = bgr.max(2) > 0; L = bgr.astype(np.float32).mean(2); H, W = L.shape; h, w = -(-H // ks) * ks, -(-W // ks) * ks
    Lp = np.zeros((h, w), np.float32); Lp[:H, :W] = L; dp = np.zeros((h, w), bool); dp[:H, :W] = da
    c = dp.reshape(h // ks, ks, w // ks, ks).sum((1, 3)); s = (Lp * dp).reshape(h // ks, ks, w // ks, ks).sum((1, 3))
    Lb = (s / np.maximum(c, 1)).astype(np.float32); db = c >= 0.3 * ks * ks; wf = db.astype(np.float32)
    n_ = np.maximum(cv2.blur(wf, (k, k)), 1e-6); mu = cv2.blur(Lb * wf, (k, k)) / n_; sd = np.sqrt(np.maximum(cv2.blur(Lb * Lb * wf, (k, k)) / n_ - mu * mu, 0))
    return np.where(db & (cv2.blur(wf, (k, k)) > 0.5), (Lb - mu) / (sd + 6.0), np.nan).astype(np.float32)


def stapel(ordner, F, fotos=None):
    """-> (namen, Ns[nf, bz, bu]) aus ortho_<id>_einzeln/<nr>.png; nur Fotos aus F['fotos'] (oder fotos)."""
    fid = F.get("id"); ed = os.path.join(ordner, f"ortho_{fid}_einzeln"); ks = max(1, int(round(0.1 / float(F["raster"]["zelle"]))))
    namen, Ns = [], []
    for nr in (fotos if fotos is not None else list((F.get("fotos") or {}).keys())):
        im = cv2.imread(os.path.join(ed, f"{nr}.png"))
        if im is None: continue
        namen.append(nr); Ns.append(_block_normiert(im, ks))
    return namen, (np.stack(Ns) if Ns else np.zeros((0, 1, 1), np.float32))


def struktur_aus_stapel(Ns):
    """MAD ueber die Fotos x 100 (wie struktur_<id>.png, Blockaufloesung), NaN wo < MIN_FOTOS."""
    with np.errstate(all="ignore"):
        md = np.nanmedian(Ns, 0); st = np.nanmedian(np.abs(Ns - md), 0) * 1.48
    st = np.where(np.isfinite(Ns).sum(0) >= MIN_FOTOS, np.nan_to_num(st), 0).astype(np.float32); st = cv2.blur(st, (3, 3)) * 100
    return np.where(np.isfinite(Ns).sum(0) >= MIN_FOTOS, st, np.nan)


def einig_aus_stapel(Ns):
    """Anteil einiger Bloecke (struktur <= S_GRENZE) unter den beurteilbaren, aus dem Stapel (fuer 'ohne diese Fotos')."""
    st = struktur_aus_stapel(Ns); b = np.isfinite(st)
    return (round(float((st[b] <= S_GRENZE).mean()), 3) if b.any() else None), round(float(np.isfinite(Ns).any(0).mean()), 3)


def foto_einigkeit(ordner, F, min_bloecke=200, Ns=None, namen=None):
    """-> Liste dict(nr, r, bloecke), aufsteigend nach r (None = zu wenig gemeinsame Bloecke). r = Pearson der Normierten gegen den Median der uebrigen Fotos."""
    if Ns is None: namen, Ns = stapel(ordner, F)
    fin = np.isfinite(Ns); raus = []
    sm = np.nansum(Ns, 0); cn = fin.sum(0)
    for q in range(len(namen)):
        o = np.delete(Ns, q, 0)
        with np.errstate(all="ignore"): md = np.nanmedian(o, 0)
        m = fin[q] & ((cn - fin[q]) >= 2) & np.isfinite(md)
        if m.sum() < min_bloecke: raus.append(dict(nr=namen[q], r=None, bloecke=int(m.sum()))); continue
        a, b = Ns[q][m], md[m]; sa, sb = a.std(), b.std()
        r = float(((a - a.mean()) * (b - b.mean())).mean() / (sa * sb)) if sa > 0 and sb > 0 else 0.0
        raus.append(dict(nr=namen[q], r=round(r, 3), bloecke=int(m.sum())))
    return sorted(raus, key=lambda d: (9 if d["r"] is None else d["r"]))


def ausschluss_vorschlag(ordner, F, r_min=R_MIN, e_min=E_MIN):
    """Fotos mit r < r_min aus dem Stapel nehmen und Einigkeit/Bedeckung des Rests messen. -> dict(ohne=[nr], einig_vorher, einig_nachher, bedeckt_vorher,
    bedeckt_nachher, reicht=bool). reicht = Rest ist einig (>= e_min); sonst sind die Kameras insgesamt ungenau (Ausschluss rettet die Wand nicht)."""
    namen, Ns = stapel(ordner, F)
    if not namen: return None
    fe = foto_einigkeit(ordner, F, Ns=Ns, namen=namen); ohne = [d["nr"] for d in fe if d["r"] is not None and d["r"] < r_min]
    e0, b0 = einig_aus_stapel(Ns); keep = [i for i, n in enumerate(namen) if n not in set(ohne)]
    e1, b1 = einig_aus_stapel(Ns[keep]) if keep else (None, 0.0)
    return dict(ohne=ohne, fotos=len(namen), einig_vorher=e0, einig_nachher=e1, bedeckt_vorher=b0, bedeckt_nachher=b1, r_min=r_min,
                reicht=bool(ohne and e1 is not None and e1 >= e_min), foto_r=fe)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("ordner"); ap.add_argument("--id"); ap.add_argument("--fotos", action="store_true", help="Foto-r und Ausschluss-Probe (braucht _einzeln)")
    ap.add_argument("--aus"); a = ap.parse_args(argv)
    FJ = json.load(open(os.path.join(a.ordner, "fassaden.json")))["fassaden"]; erg = {}
    for F in FJ:
        if a.id and F.get("id") != a.id: continue
        w = wand_einigkeit(a.ordner, F); erg[F["id"]] = dict(wand=w)
        print(f"{F['id']}: " + ("Karten fehlen" if w is None else f"einig {w['einig_anteil']} unter beurteilbar {w['beurteilt_anteil']} (Grenze E_MIN {E_MIN}) -> " + ("EINIG" if (w['einig_anteil'] or 0) >= E_MIN else ("nicht beurteilbar" if w['einig_anteil'] is None else "UNEINIG"))))
        if a.fotos:
            v = ausschluss_vorschlag(a.ordner, F); erg[F["id"]]["ausschluss"] = v
            if v: print(f"   {v['fotos']} Fotos, {len(v['ohne'])} mit r < {v['r_min']}; Einigkeit (Stapel) {v['einig_vorher']} -> ohne sie {v['einig_nachher']}, bedeckt {v['bedeckt_vorher']} -> {v['bedeckt_nachher']}"
                        + (" -> Ausschluss reicht" if v["reicht"] else ""))
    if a.aus: __import__("json_sicher").schreiben(a.aus, erg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
