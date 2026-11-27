#!/usr/bin/env python3
"""bruecke_bauen.py - Stufe B4/B5 der Kettenstufe BRUECKE (27.11.2026): Massliste (bruecke_messen.py) -> bauteile.ueberdachter_gang -> Tor -> Druckteile + Bilder.

  tools/py tools/bruecke_bauen.py MASSLISTE.json AUSDIR [--fotos a.jpg,b.jpg,...] [--wolke WOLKE.ply] [--bett 250] [--rand 10]

Schreibt nach AUSDIR:
  bruecke_tor.json      Tor (ROT, sobald ein Bauteil fehlt/Ersatzform ist; DOM1-Laenge nur als Gegenprobe: Widerspruch > toleranz = ROT 'spannweite', nie gemittelt)
  bruecke_h0.stl        ganzes Teil in mm (1:87), Modellrahmen (nur Ansicht; zu lang fuer das Bett)
  teil_<i>.stl + Teilung.json  Druckteile (Schnitt an Pfostenachsen, Stiftloecher im Deck), je Teil ein Koerper + wasserdicht geprueft
  neben_<foto>.jpg      Foto | Foto mit projizierten Modellkanten (sichtbare Kanten, Teilmodell-Kameras)
  schnitte_m.jpg        Querschnitt + Laengsschnitt + Draufsicht in Metern: Modell gegen Messkanten (und Wolke als Gegenprobe, falls --wolke)
GENERISCH: alle Masse aus der Massliste; Teilung aus Bettgroesse und Pfostenlagen."""
import sys, os, json, math, copy
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bauteile as BT
import bruecke_messen as BM
from manifold3d import Manifold as M

H0 = 87.0


def gegenprobe_lage(ml, toleranz=1.0):
    """Laenge der Messung gegen DOM1/Wolke-Laenge aus BRUECKE-LAGE.json: nur Meldung + ROT bei Widerspruch (Quellen nicht mitteln)."""
    try: L = json.load(open(ml["lage"]))["steg"]
    except (KeyError, OSError, ValueError): return None
    w = ml["parameter"].get("spannweite", {}).get("wert")
    if w is None: return None
    d = w - float(L["laenge_dach_m"])
    return dict(bauteil="spannweite", gemessen=round(w, 2), lage_dom1=float(L["laenge_dach_m"]), differenz=round(d, 2), toleranz=toleranz,
                widerspruch=abs(d) > toleranz, grund=f"Kantenlaenge {w:.2f} m gegen DOM1-Dachstreifen {L['laenge_dach_m']} m (Differenz {d:+.2f} m > {toleranz} m) - nicht gemittelt, klaeren"
                if abs(d) > toleranz else "")


def lokal_param(P):
    """Parameter im lokalen Rahmen (x laengs ab Ende a) - fuer Teilung und Schnitte."""
    Q = copy.deepcopy(P); a = np.array(Q.pop("achse")["a"]); b = np.array(P["achse"]["b"]); Q["spannweite"] = float(np.linalg.norm(b - a)); return Q


def stl_h0(m, pfad):
    t = BT.als_trimesh(m); t.apply_scale(1000.0 / H0); t.export(pfad); return t


def teilen(gl, P, ms, bett=250.0, rand=10.0, stift_d=2.0, stift_t=6.0):
    """Lokales Teil (Meter) in Druckteile <= bett - 2 rand (mm) teilen; Schnitt an der Pfostenachse, die der gleichmaessigen Teilung am naechsten liegt.
    Verbinder: zwei Stiftloecher (Durchmesser stift_d mm, Tiefe stift_t mm je Seite) im Deck an jeder Schnittflaeche (Messingstift/Filament).
    Jedes Teil muss ein Koerper und wasserdicht sein, sonst 'ok': false (nicht stillschweigend weiter)."""
    L = ms["spannweite"]; Lmm = L * 1000 / H0; nmax = bett - 2 * rand; n = max(1, math.ceil(Lmm / nmax))
    pf = P.get("seiten", {}).get("pfosten_lagen") or []
    schnitte = []
    for i in range(1, n):
        ziel = L * i / n; x = min(pf, key=lambda p: abs(p - ziel)) if pf else ziel; schnitte.append(float(x))
    grenzen = [-1.0] + schnitte + [L + 1.0]; teile = []
    zb = ms.get("hoehe") and P["z_boden"]; db = ms["boden_dicke"]; B = ms["breite"]; r = stift_d / 2 * H0 / 1000; tt = stift_t * H0 / 1000
    for i in range(len(grenzen) - 1):
        x0, x1 = grenzen[i], grenzen[i + 1]
        g = gl.trim_by_plane((1.0, 0.0, 0.0), x0).trim_by_plane((-1.0, 0.0, 0.0), -x1)
        for xs in (x0, x1):
            if xs in schnitte:
                for yq in (-B / 4, B / 4):
                    cyl = M.cylinder(2 * tt, r, r, 24).transform([[0, 0, 1, xs - tt], [0, 1, 0, yq], [-1, 0, 0, P["z_boden"] - db / 2]])   # Achse laengs (x)
                    g = g - cyl
        t = BT.als_trimesh(g); t.apply_scale(1000 / H0); ausd = (t.bounds[1] - t.bounds[0]).tolist()
        teile.append(dict(nr=i + 1, x_von_m=max(x0, 0.0), x_bis_m=min(x1, L), mass_mm=[round(v, 1) for v in ausd], koerper=len(g.decompose()),
                          wasserdicht=bool(t.is_watertight), ok=bool(t.is_watertight and len(g.decompose()) == 1 and max(ausd[:2]) <= nmax + 1e-6), mesh=t))
    return dict(bett_mm=bett, rand_mm=rand, laenge_mm=round(Lmm, 1), teile_n=n, schnitte_m=schnitte,
                verbinder=f"je Schnitt 2 Stiftloecher D {stift_d} mm x {stift_t} mm je Seite im Deck (y = +-Breite/4), Stift Messing 2 mm oder Filamentrest"), teile


def kanten3d(t, winkel=25.0, schritt=0.05):
    """Scharfe Kanten eines Netzes als 3D-Abtastpunkte (Liste von (N,3) je Kante)."""
    ang = t.face_adjacency_angles; e = t.face_adjacency_edges[ang > math.radians(winkel)]; V = t.vertices; out = []
    for a, b in e:
        A, B = V[a], V[b]; n = max(2, int(np.linalg.norm(B - A) / schritt)); out.append(A + (B - A) * np.linspace(0, 1, n)[:, None])
    return out


def neben_bild(t, cam, foto_pfad, aus, titel=""):
    """Foto | Foto mit sichtbaren Modellkanten (Strahltest gegen das Modell selbst; Wolke/Baeume verdecken NICHT - Hinweis im Bild)."""
    im = cv2.imread(foto_pfad); im = cv2.resize(im, (cam["W"], cam["H"])) if im.shape[1] != cam["W"] else im
    ov = im.copy(); C = np.asarray(cam["C"], float); ks = kanten3d(t)
    P = np.concatenate(ks); d = P - C; dist = np.linalg.norm(d, axis=1); d /= dist[:, None]
    try:
        loc, idx, _ = t.ray.intersects_location(np.repeat(C[None], len(P), 0), d, multiple_hits=False)
        first = np.full(len(P), np.inf); first[idx] = np.linalg.norm(loc - C, axis=1); sicht = first >= dist - 0.06
    except Exception: sicht = np.ones(len(P), bool)
    uv, z = BM.projizieren(cam, P); j = 0
    for k in ks:
        n = len(k); u = uv[j:j + n]; s = sicht[j:j + n] & (z[j:j + n] > 0.3); j += n
        for i in range(n - 1):
            if s[i] and s[i + 1]: cv2.line(ov, tuple(np.round(u[i]).astype(int)), tuple(np.round(u[i + 1]).astype(int)), (255, 255, 0), 2)
    for b_, txt in ((im, "Foto " + os.path.basename(foto_pfad)), (ov, "Modell (Kanten, cyan) " + titel)):
        cv2.putText(b_, txt, (20, 50), 0, 1.3, (0, 0, 0), 6); cv2.putText(b_, txt, (20, 50), 0, 1.3, (0, 255, 255), 2)
    cv2.imwrite(aus, np.hstack([im, ov]), [cv2.IMWRITE_JPEG_QUALITY, 85])


def schnitte_bild(gl, ml, P, ms, aus, wolke=None):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    t = BT.als_trimesh(gl); R = BM.Rahmen(ml["rahmen"]["mitte"], ml["rahmen"]["achse"], ml["rahmen"]["neigung_grad"]); sa = ml["s_a"]; qc = ml["qc"]
    W = None
    if wolke:
        X = BM.ply_lesen(wolke, 1_500_000); l = R.lokal(X); l[:, 0] -= sa; l[:, 1] -= qc
        W = l[(l[:, 0] > -8) & (l[:, 0] < ms["spannweite"] + 8) & (np.abs(l[:, 1]) < 6) & (l[:, 2] > -1) & (l[:, 2] < 13)]
    fig, ax = plt.subplots(1, 3, figsize=(24, 7), gridspec_kw=dict(width_ratios=[1, 2.4, 2.4]))
    mitte = ms["spannweite"] / 2; Pm = ml["parameter"]
    sek = t.section((1, 0, 0), (mitte + 0.5, 0, 0))
    if W is not None:
        w = W[np.abs(W[:, 0] - mitte) < 3]; ax[0].scatter(w[:, 1], w[:, 2], s=0.2, c="0.7", label="Wolke |s-mitte|<3 m (nur Gegenprobe)")
    if sek is not None:
        for e in sek.discrete: ax[0].plot(e[:, 1], e[:, 2], "b-", lw=1.5)
    for k, c in (("unterkante", "r"), ("laufebene", "m"), ("holm", "g"), ("riegel", "c"), ("traufe", "orange"), ("first", "k")):
        v = Pm.get(k, {}).get("wert")
        if v is not None: ax[0].axhline(v, color=c, ls="--", lw=0.8, label=f"{k} {v:.2f} (Fotokante)")
    B = ms["breite"]; ax[0].axvline(-B / 2, color="0.3", ls=":", lw=0.8); ax[0].axvline(B / 2, color="0.3", ls=":", lw=0.8, label=f"Pfostenebenen, Breite {B:.2f}")
    ax[0].set_title("Querschnitt Mitte (blau Modell)"); ax[0].set_aspect("equal"); ax[0].legend(fontsize=7, loc="lower left"); ax[0].set_xlabel("quer m"); ax[0].set_ylabel("z m")
    sek = t.section((0, 1, 0), (0, -B / 2 + 0.01, 0))
    if W is not None:
        w = W[np.abs(W[:, 1]) < 2.5]; ax[1].scatter(w[:, 0], w[:, 2], s=0.1, c="0.7")
    if sek is not None:
        for e in sek.discrete: ax[1].plot(e[:, 0], e[:, 2], "b-", lw=1)
    for x in P.get("seiten", {}).get("pfosten_lagen", []): ax[1].axvline(x, color="g", lw=0.5, ls="--")
    ax[1].set_title(f"Laengsschnitt in der Pfostenebene (Spannweite {ms['spannweite']:.2f} m, {ms.get('oeffnungen', 0)} offene Felder; gruen = gemessene Pfostenlagen)")
    ax[1].set_aspect("equal"); ax[1].set_xlabel("laengs m ab Ende a"); ax[1].set_ylabel("z m")
    if W is not None:
        w = W[W[:, 2] > 4]; ax[2].scatter(w[:, 0], w[:, 1], s=0.1, c=w[:, 2], cmap="viridis")
    v = t.vertices; ax[2].plot([0, ms["spannweite"], ms["spannweite"], 0, 0], [-B / 2, -B / 2, B / 2, B / 2, -B / 2], "b-")
    u = P.get("dach", {}).get("ueberstand", 0); ax[2].plot([0, ms["spannweite"], ms["spannweite"], 0, 0], [-B / 2 - u] * 2 + [B / 2 + u] * 2 + [-B / 2 - u], "r-", lw=0.8)
    ax[2].set_title("Draufsicht (blau Pfostenebenen, rot Dachrand; Farbe = Wolke z > 4 m)"); ax[2].set_aspect("equal"); ax[2].set_xlabel("laengs m"); ax[2].set_ylabel("quer m")
    fig.tight_layout(); fig.savefig(aus, dpi=80); plt.close(fig)


def main():
    if len(sys.argv) < 3: print(__doc__); sys.exit(2)
    def opt(n, d, t=str): return t(sys.argv[sys.argv.index(n) + 1]) if n in sys.argv else d
    ml = json.load(open(sys.argv[1])); aus = sys.argv[2]; os.makedirs(aus, exist_ok=True); P = ml.get("gang")
    tor = dict(status="ROT", rot=[dict(bauteil="bruecke", grund="keine Parameter (Massliste ohne Grundmasse)")])
    if P is None:
        json.dump(tor, open(os.path.join(aus, "bruecke_tor.json"), "w"), indent=1, ensure_ascii=False); print("BRUECKE NICHT BELEGT - Tor ROT"); return 1
    g, belege, ms = BT.ueberdachter_gang(P); gl, _, msl = BT.ueberdachter_gang(lokal_param(P))
    tor = BT.bruecke_tor(ms); gp = gegenprobe_lage(ml)
    if gp and gp["widerspruch"]: tor["rot"].append(dict(bauteil="spannweite", grund=gp["grund"])); tor["status"] = "ROT"
    tor.update(gegenprobe_lage=gp, belege=belege, masse={k: v for k, v in ms.items() if k != "rot"})
    if g is None:
        json.dump(tor, open(os.path.join(aus, "bruecke_tor.json"), "w"), indent=1, ensure_ascii=False, default=str); print("nicht gebaut:", ms.get("grund")); return 1
    t = BT.als_trimesh(g); t.export(os.path.join(aus, "bruecke_modell_m.ply")); stl_h0(g, os.path.join(aus, "bruecke_h0.stl"))
    tei, teile = teilen(gl, lokal_param(P), msl, bett=opt("--bett", 250.0, float), rand=opt("--rand", 10.0, float))
    for te in teile: te.pop("mesh").export(os.path.join(aus, f"teil_{te['nr']}.stl"))
    tei["teile"] = teile; json.dump(tei, open(os.path.join(aus, "Teilung.json"), "w"), indent=1, ensure_ascii=False)
    if not all(te["ok"] for te in teile): tor["rot"].append(dict(bauteil="druckteile", grund="Teil nicht ein wasserdichter Koerper oder zu lang")); tor["status"] = "ROT"
    json.dump(tor, open(os.path.join(aus, "bruecke_tor.json"), "w"), indent=1, ensure_ascii=False, default=str)
    print("Tor:", tor["status"], "|", "; ".join(f"{r['bauteil']}: {r['grund'][:80]}" for r in tor["rot"]))
    print("Teilung:", tei["teile_n"], "Teile", [te["mass_mm"] for te in teile], "ok", [te["ok"] for te in teile])
    W = json.load(open(opt("--kameras", "", str))) if "--kameras" in sys.argv else None
    if W and "--fotos" in sys.argv:
        for f in opt("--fotos", "").split(","):
            if f in W["kameras"]: neben_bild(t, W["kameras"][f], os.path.join(W["bilddir"], f), os.path.join(aus, "neben_" + os.path.splitext(f)[0] + ".jpg"))
    schnitte_bild(gl, ml, lokal_param(P), msl, os.path.join(aus, "schnitte_m.jpg"), opt("--wolke", None))
    return 0 if tor["status"] == "GRUEN" else 3


if __name__ == "__main__":
    sys.exit(main())
