#!/usr/bin/env python3
"""test_loch_gewaende.py - fester synthetischer Test fuer den Befund 'Oeffnungen und Fenster' aus Kettenlauf 1122o (23.11.2026), < 20 s, nur CPU.

Je Fall des Befunds ein Teil (audit/neben_detail_*.jpg des Laufs 1122o):
  1 fenster_f03    vergittertes Rechteckfenster in breitem Sandsteingewaende, Wandbild oben ANGESCHNITTEN (keine Fotozellen), Erkennerzone = ganzes Gewaende
                   -> Loch = Fenster (oben aus dem kleinen Erkennerkasten), Gewaende-Umriss, Laibung aus der Tiefe je Zelle (Sweep 0,30), Gewaende-Hoehe aus dem Sweep.
  2 fenster_f03_2  schmaler Schlitz in einem Sandsteinfeld, Eintrag war ein 1,40 m breites RUNDBOGEN-Fenster (Form des Farbfelds) -> Loch 0,16 m, Rechteck.
  3 oeffnung f04   geschlossene Tuer (dunkles Tuerblatt) in Sandsteinportal mit beschatteter Laibung; oeffnungen_aussen 'tuer' flach, oeffnungen_auto verworfen
                   -> Tuer kommt als Eintrag dazu, Loch = Tuerblatt (Schattenlaibung NICHT im Loch); Bau: ein Koerper 0,6 m VOR der Ebene (Turm) deckt die Tuer
                   zu -> loch_gewaende_spaet schneidet sie auf der echten Oberflaeche.
  4 oeffnung f03   Zone ueber einem Bereich OHNE Wandflaeche (Fassadenpolygon dort ausgespart = Rundbau davor) -> wand_anteil < 0,6, Koerper vor der Wand;
                   nicht gebaute Erkennungen (gebaut=false) sind keine Bauteile (befundliste.bauteil_zonen -> neben_details).
"""
import sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pfade import temp_ordner
import loch_gewaende as LG

U0, U1, Z0, Z1, C = -4.0, 4.0, 0.0, 8.0, 0.01
F = 0
WAND, SAND, DUNKEL, TUER, SCHATTEN, STAB = (200, 205, 212), (95, 108, 165), (25, 25, 30), (70, 60, 30), (40, 52, 88), (150, 150, 150)


def pruef(ok, text):
    global F
    print(("  ok     " if ok else "  FEHLER ") + text)
    if not ok: F += 1


def nahe(a, b, tol): return a is not None and abs(a - b) <= tol


def bild():
    rng = np.random.default_rng(3); H, W = int((Z1 - Z0) / C), int((U1 - U0) / C)
    im = np.zeros((H, W, 3), np.float64) + np.array(WAND) + rng.normal(0, 3.0, (H, W, 1))
    uu = U0 + C * (np.arange(W) + 0.5); zz = Z1 - C * (np.arange(H) + 0.5); UU, ZZ = np.meshgrid(uu, zz)
    def feld(u0, u1, z0, z1, farbe): im[(UU >= u0) & (UU <= u1) & (ZZ >= z0) & (ZZ <= z1)] = farbe
    # 1: Gewaende mit Eckquader-Verzahnung, vergittertes Fenster, darueber kein Foto
    feld(-3.4, -1.6, 4.0, 6.6, SAND); feld(-3.6, -3.4, 4.3, 4.6, SAND); feld(-1.6, -1.4, 5.2, 5.5, SAND)
    feld(-2.9, -2.1, 4.4, 6.4, DUNKEL)
    for z in np.arange(4.55, 6.4, 0.15): feld(-2.9, -2.1, z, z + 0.03, STAB)
    im[(ZZ > 6.0) & (UU < 0.0)] = 0
    # 2: Schlitz im Sandsteinfeld
    feld(0.0, 1.3, 2.0, 3.6, SAND); feld(0.58, 0.74, 2.3, 3.2, DUNKEL)
    # 3: Tuer im Portal, linke Laibung beschattet (dunkel, aber Sandstein-Farbton)
    feld(2.0, 3.6, 0.0, 2.6, SAND); feld(2.3, 3.3, 0.0, 2.2, TUER); feld(2.2, 2.3, 0.0, 2.2, SCHATTEN)
    return np.clip(im, 0, 255).astype(np.uint8)


def main():
    import cv2
    d = temp_ordner("test_loch_"); fo = os.path.join(d, "fassade"); ff = os.path.join(d, "fassade_fein"); au = os.path.join(d, "audit")
    for p in (fo, ff, au): os.makedirs(p)
    rast = dict(u0=U0, z1=Z1, zelle=C, nu=int((U1 - U0) / C), nz=int((Z1 - Z0) / C))
    poly = [[[U0, Z0], [U1, Z0], [U1, Z1], [U0, Z1]]]
    fas = dict(fassaden=[dict(id="f00", o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, 1.0], u=[U0, U1], z=[Z0, Z1], polys_uz=poly, raster=rast)])
    json.dump(fas, open(os.path.join(ff, "fassaden.json"), "w")); json.dump(fas, open(os.path.join(fo, "fassaden.json"), "w"))
    cv2.imwrite(os.path.join(ff, "ortho_f00_fein.png"), bild())
    json.dump(dict(fassaden={"f00": dict(elemente=[dict(klasse="fenster", u0=-2.92, u1=-2.08, z0=4.38, z1=6.42, stimmen=3),
                                                    dict(klasse="fenster", u0=-3.5, u1=-1.5, z0=3.9, z1=6.7, stimmen=3)])}), open(os.path.join(fo, "elemente.json"), "w"))
    # Tiefe je Zelle (Sweep, 4 cm, w positiv = vor der Wand): Wand 0, Gewaende +0,05, Loecher -0,30
    c4 = 0.04; H4, W4 = int((Z1 - Z0) / c4), int((U1 - U0) / c4); uu = U0 + c4 * (np.arange(W4) + 0.5); zz = Z1 - c4 * (np.arange(H4) + 0.5); UU, ZZ = np.meshgrid(uu, zz)
    w = np.zeros((H4, W4)); box = lambda u0, u1, z0, z1: (UU >= u0) & (UU <= u1) & (ZZ >= z0) & (ZZ <= z1)
    w[box(-3.4, -1.6, 4.0, 6.6) | box(0.0, 1.3, 2.0, 3.6) | box(2.0, 3.6, 0.0, 2.6)] = 0.05; w[box(-2.9, -2.1, 4.4, 6.4) | box(0.58, 0.74, 2.3, 3.2) | box(2.3, 3.3, 0.0, 2.2)] = -0.30
    np.savez(os.path.join(fo, "tiefe_f00.npz"), w=w, gut=np.ones_like(w, bool), sicher=np.ones_like(w), u0=U0, z1=Z1, zelle=c4)
    fa = os.path.join(au, "fenster_auto.json")
    json.dump({"f00": dict(o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, 1.0], fenster=[
        dict(u0=-3.5, u1=-1.5, z0=3.9, z1=6.7, teiler=[], kaempfer=None, scheiben=2, stimmen_min=3, sprossen=[]),
        dict(u0=-0.05, u1=1.35, z0=1.95, z1=3.65, teiler=[], kaempfer=None, scheiben=1, stimmen_min=5, sprossen=[], bogen=dict(form="rund", kaempfer=2.95, scheitel=3.65), tiefe=0.12,
             tiefe_quelle="ANNAHME 0.12 m")])}, open(fa, "w"))
    oa = os.path.join(au, "oeffnungen_aussen.json"); ob = os.path.join(au, "oeffnungen_auto.json")
    json.dump({"f00": dict(o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, 1.0], oeffnungen=[dict(klasse="tuer", zone=[1.95, 3.65, -0.02, 2.65], tiefe=-1.3, flach=True)])}, open(oa, "w"))
    json.dump({"f00": dict(o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, 1.0], oeffnungen=[dict(art="bogen", kasten=[1.95, 3.65, 0.0, 2.6], stimmen=4, gebaut=False, grund="kein Durchblick")])}, open(ob, "w"))

    rc = LG.main([fa, fo, ff, "--oeffnungen", oa, "--oeffnungen_auto", ob])
    pruef(rc == 0, f"loch_gewaende rc {rc} (0 = Loecher vermessen)")
    J = json.load(open(fa))["f00"]["fenster"]; pruef(os.path.exists(fa[:-5] + "_vor_loch.json"), "Eingang als fenster_auto_vor_loch.json gesichert")
    e1 = next((e for e in J if e.get("loch") and e["u0"] < -1.0), None); e2 = next((e for e in J if e.get("loch") and -0.5 < e["u0"] < 1.0), None)
    e3 = next((e for e in J if e.get("art") == "tuer"), None)
    # Fall 1
    pruef(e1 is not None, "Fall 1: Fenster im Gewaende vermessen")
    if e1:
        pruef(nahe(e1["u0"], -2.9, 0.04) and nahe(e1["u1"], -2.1, 0.04), f"Fall 1: Loch u {e1['u0']:.2f}..{e1['u1']:.2f} (soll -2,90..-2,10, nicht die Zone -3,50..-1,50)")
        pruef(nahe(e1["z0"], 4.4, 0.04), f"Fall 1: Loch-Unterkante {e1['z0']:.2f} (soll 4,40)")
        pruef(nahe(e1["z1"], 6.42, 0.03) and "oben" in (e1["loch"].get("angeschnitten") or []), f"Fall 1: oben angeschnitten -> Oberkante aus dem kleinen Erkennerkasten {e1['z1']:.2f} (6,42)")
        pruef(nahe(e1.get("tiefe"), 0.30, 0.05) and "Sweep" in e1.get("tiefe_quelle", ""), f"Fall 1: Laibung aus der Tiefe je Zelle {e1.get('tiefe')} ({e1.get('tiefe_quelle', '')[:40]})")
        G = e1.get("gewaende") or {}
        pruef(len(G.get("umriss") or []) >= 4 and nahe(G.get("flaeche_m2"), 1.8 * 1.96 - 0.8 * 1.56 + 0.12, 0.3), f"Fall 1: Gewaende-Umriss {len(G.get('umriss') or [])} Ecken, {G.get('flaeche_m2')} m2 (soll ~2,4: sichtbarer Teil unter der Fotokante 6,0 ohne Loch)")
        pruef(nahe(G.get("hoehe"), 0.05, 0.02) and "Sweep" in G.get("hoehe_quelle", ""), f"Fall 1: Gewaende-Hoehe aus dem Sweep {G.get('hoehe')} (0,05)")
        pruef(e1.get("scheiben") == 1 and (e1.get("bogen") or {}).get("form") == "gerade", "Fall 1: ein Loch, Rechteck (nicht 2 Scheiben des Sammelkastens)")
    # Fall 2
    pruef(e2 is not None, "Fall 2: Schlitz vermessen")
    if e2:
        pruef(nahe(e2["u1"] - e2["u0"], 0.16, 0.04) and nahe(e2["z1"] - e2["z0"], 0.90, 0.05), f"Fall 2: Loch {e2['u1'] - e2['u0']:.2f} x {e2['z1'] - e2['z0']:.2f} m (soll 0,16 x 0,90, nicht 1,40 x 1,70)")
        pruef((e2.get("bogen") or {}).get("form") == "gerade" and (e2.get("form_vorher") or {}).get("form") == "rund", f"Fall 2: Rundbogen des Farbfelds verworfen -> Rechteck ({e2.get('bogen')})")
        pruef(bool(e2.get("gewaende")), "Fall 2: Sandsteinfeld als Gewaende")
    # Fall 3
    pruef(e3 is not None, "Fall 3: geschlossene Tuer aus oeffnungen_aussen als Eintrag")
    if e3:
        pruef(nahe(e3["u0"], 2.3, 0.04) and nahe(e3["u1"], 3.3, 0.04), f"Fall 3: Tuerzone auf das Tuerblatt begrenzt u {e3['u0']:.2f}..{e3['u1']:.2f} (2,30..3,30; Schattenlaibung 2,20 nicht im Loch)")
        pruef(nahe(e3["z1"], 2.2, 0.04), f"Fall 3: Tueroberkante {e3['z1']:.2f} (2,20)")
        pruef(bool(e3.get("gewaende")), "Fall 3: Portal als Gewaende")
    # Guard: kein dunkles Loch -> unveraendert
    bgr = bild(); R = LG.Raster(U0, Z1, C, *bgr.shape[:2]); g = LG.loch_messen(bgr, R, [1.5, 2.0, 4.0, 5.0])
    pruef("fehler" in g, f"Guard: Putzflaeche ohne Loch -> kein Loch ({g.get('fehler')})")

    # Bau: Gewaende-Relief + Loch; Koerper 0,6 m vor der Tuer (Turm) -> loch_gewaende_spaet schneidet auf der echten Oberflaeche
    from bauteile import fenster_aus_json, loch_gewaende_spaet, _oberflaeche_w, Wand
    from manifold3d import Manifold as M
    k = M.cube((8.0, 3.0, 8.0)).translate((-4.0, -3.0, 0.0)); k1, bel = fenster_aus_json(k, fa)
    k1 = k1 + M.cube((2.5, 0.65, 3.0)).translate((1.6, -0.05, 0.0))
    W = Wand((0.0, 0.0), (1.0, 0.0), aussen=(0.0, 1.0))
    vor = _oberflaeche_w(k1, W, [(2.8, 1.0)])[0]; pruef(nahe(vor, 0.6, 0.01), f"Bau: Turmkoerper deckt die Tuer zu (Oberflaeche {vor})")
    k2, bel2 = loch_gewaende_spaet(k1, fa)
    s = _oberflaeche_w(k2, W, [(2.8, 1.0), (-2.5, 5.0), (-3.3, 4.2), (-1.0, 5.0), (0.66, 2.7), (2.1, 1.0)])
    pruef(nahe(s[0], 0.6 - 0.30, 0.03), f"Bau: Tuer auf der Turmoberflaeche geschnitten (w {s[0]}, soll 0,30 = 0,60 - Laibung)")
    pruef(nahe(s[1], -0.30, 0.03), f"Bau: Fenster 1 Laibung (w {s[1]}, soll -0,30)")
    dm = float(os.environ.get("MINMM", "0.8")) * float(os.environ.get("SCALE", "87")) / 1000.0
    pruef(nahe(s[2], dm, 0.01), f"Bau: Gewaende 1 als Relief vor der Wand (w {s[2]}, soll Druckmindestmass {dm:.3f})")
    pruef(nahe(s[3], 0.0, 0.005), f"Bau: Wand neben dem Gewaende unveraendert (w {s[3]})")
    pruef(nahe(s[4], -0.30, 0.03), f"Bau: Schlitz geschnitten (w {s[4]})")
    pruef(nahe(s[5], 0.6 + dm, 0.02), f"Bau: Portal-Relief auf der Turmoberflaeche (w {s[5]}, soll {0.6 + dm:.3f})")
    pruef(len(k2.decompose()) == 1, f"Bau: ein Koerper ({len(k2.decompose())} Teile)")
    pruef(any("echten Oberflaeche" in b.get("element", "") for b in bel2), "Bau: Beleg der Nacharbeit")

    # Fall 4: Rundbau vor der Wand ist keine Oeffnung; nicht gebaute Erkennungen sind keine Bauteile
    from oeffnungen_bogen import wand_anteil, WAND_ANTEIL_MIN
    Fr = dict(polys_uz=[[[-1.6, 0.0], [6.1, 0.0], [6.1, 36.0], [-1.6, 36.0]], [[-4.5, 12.0], [-1.6, 12.0], [-1.6, 36.0], [-4.5, 36.0]]])
    a_turm = wand_anteil(Fr, [-4.74, -1.16, 0.89, 17.2]); a_fen = wand_anteil(Fr, [0.0, 1.2, 17.2, 18.8])
    pruef(a_turm is not None and a_turm < WAND_ANTEIL_MIN, f"Fall 4: Zone ueber dem Rundbau nur {a_turm and round(a_turm, 2)} in der Wandflaeche -> keine Oeffnung")
    pruef(nahe(a_fen, 1.0, 0.02), f"Fall 4: Fenster mitten in der Wand {a_fen} in der Wandflaeche")
    pruef(wand_anteil(dict(polys_uz=json.dumps(Fr["polys_uz"])), [-4.74, -1.16, 0.89, 17.2]) == a_turm and wand_anteil({}, [0, 1, 0, 1]) is None, "Fall 4: Polygon als Text gelesen; ohne Polygon kein Urteil")
    import befundliste as BL
    json.dump({"f03": dict(oeffnungen=[dict(art="bogen", kasten=[-4.74, -1.16, 0.89, 17.2], gebaut=False), dict(art="bogen", kasten=[0.0, 2.0, 0.0, 3.0], gebaut=True)])},
              open(os.path.join(au, "oeffnungen_auto.json"), "w"))
    zn = [z for z in BL.bauteil_zonen(au) if z["name"].startswith("oeffnungen")]
    pruef(len(zn) == 1 and zn[0]["u0"] == 0.0, f"Fall 4: nur die GEBAUTE Oeffnung ist Bauteil (neben_details/befundliste): {[(z['name'], z['u0']) for z in zn]}")
    print(f"test_loch_gewaende: {F} Fehler"); return 1 if F else 0


if __name__ == "__main__": sys.exit(main())
