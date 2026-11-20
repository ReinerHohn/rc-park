#!/usr/bin/env python3
"""test_grauzone_tor.py - BEWEIS des Grauzonen-Tors (Spec modelle/archiv/SPEC_GRAUZONE_TOR.md).

Der Grauzonen-Pruefer ist der Formfund-Pruefer OHNE Befundtext und ohne Absicht (`formfund_pruefen --ohne_befund`): nur Teilname und Dreierbilder.
Bestanden = verbessert true, erfunden false, sicher hoch (strenger als das Formfund-Tor).

Stufen (getrennt aufrufbar):
  fallen    12 synthetische Fallen (4 Arten x 3) + bekannte Faelle (a091923 r2, a044705 r4 negativ; a095328, a104922 positiv)
  rueckblick  verworfene Runden in der Grauzone (Liste aus --liste JSON: [{lauf, runde, teil?, f1_vorher, f1_nachher}]), siehe Kopf von rueckblick()
Bilder GPU-seriell in diesem Prozess, Pruefer bis zu 3 parallel (Threads, claude -p).
Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_grauzone_tor.py fallen [--nur_bilder] [--nur a,b]
Arbeitsdaten: /media/oem/scan/rc-park_tmp/grauzone/
"""
import sys, os, json, argparse, time, numpy as np, trimesh
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import formfund_pruefen as FFP
# Test gegen den COMMITTETEN Prompt: die (uncommittete) Lage-Klausel des Koordinators wird entfernt (Hinweis 11.11.)
FFP.PROMPT = "\n".join(l for l in FFP.PROMPT.split("\n") if not l.startswith("Bei NEUEN oder verschobenen Teilen"))

KREIS = "/media/oem/scan/rc-park_kreis/%s"
ARBEIT = "/media/oem/scan/rc-park_tmp/grauzone"
SK = 0.087   # m je STL-Einheit (H0-mm)
BASIS_LAUF = "20261111_125136a125135"; BASIS = "teile_r1_nachher"

# --- synthetische Aenderungen an EINEM Teil des Basisstands ------------------------------------------------------------------------
def _achsen(m):
    c2 = m.vertices[:, :2].mean(0); v = m.vertices[:, :2] - c2
    ax = np.linalg.eigh(np.cov(v.T) + 1e-9 * np.eye(2))[1][:, 1]; return c2, ax, np.array([-ax[1], ax[0]])

def mod_kasten(m, groesse_m):
    """erfundener Kasten (Seite groesse_m, Hoehe groesse_m) auf der Oberkante in Teilmitte, 0,1 m eingesenkt."""
    c2, ax, nrm = _achsen(m); b = trimesh.creation.box(extents=[groesse_m / SK] * 3)
    b.apply_translation([c2[0], c2[1], float(m.bounds[1, 2]) + groesse_m / SK / 2 - 0.1 / SK]); return trimesh.util.concatenate([m, b])

def mod_schiebung(m, dm, winkel_grad):
    a = np.radians(winkel_grad); m = m.copy(); m.apply_translation([np.cos(a) * dm / SK, np.sin(a) * dm / SK, 0]); return m

def mod_skala(m, f):
    m = m.copy(); c = m.bounds.mean(0); fuss = np.array([c[0], c[1], m.bounds[0, 2]]); m.vertices = (m.vertices - fuss) * f + fuss; return m

# Fallen: Kennung -> (Art, Teil, Parameter) bzw. ("umkehr", Quelle) fuer falsche Formfamilie (bekannter Gewinn rueckwaerts: richtig -> falsch)
FALLEN = {
    "kasten1": ("kasten", "staffelgiebel__west", 0.5), "kasten2": ("kasten", "erker_polygon__0", 0.4), "kasten3": ("kasten", "gaubenreihe__oben", 0.3),
    "schieb1": ("schieb", "helm_geschweift__o", (0.3, 0)), "schieb2": ("schieb", "erker_polygon__1", (0.3, 90)), "schieb3": ("schieb", "bruestung__balkon", (0.3, 30)),
    "familie1": ("umkehr", "a125135"), "familie2": ("umkehr", "a095328"), "familie3": ("umkehr", "a104922"),
    "skala4": ("skala", "fensterreihe__og", 0.8), "skala2": ("skala", "gaubenreihe__unten", 1.2), "skala3": ("skala", "erker_polygon__0", 1.2),
}
# Bekannte Faelle: Kennung -> (Lauf, vorher, nachher, Soll, Hinweis)
BEKANNT = {
    "a091923": ("20261111_091923a091923", "teile_r2_vorher", "teile_r2_nachher", "negativ", "Tor rund statt spitz"),
    "a044705": ("20261111_044705a044705", "teile_r4_vorher_form", "teile_r4_nachher", "negativ", "erfundene Facetten (Gesims)"),
    "a095328": ("20261111_095328a095328", "teile_r1_vorher", "teile_r1_nachher", "positiv", "Gewoelbe Rippen"),
    "a104922": ("20261111_104922a104922", "teile_r1_vorher", "teile_r1_nachher", "positiv", "Gewoelbe Rippen (Alternativlauf)"),
}
UMKEHR = {"a125135": ("20261111_125136a125135", "teile_r1_vorher_form", "teile_r1_nachher"), "a095328": BEKANNT["a095328"][:3], "a104922": BEKANNT["a104922"][:3]}


def stand_kopie(basis_dir, aus_dir, teil, m_neu):
    os.makedirs(aus_dir, exist_ok=True)
    for n in os.listdir(basis_dir):
        d = os.path.join(aus_dir, n)
        if os.path.lexists(d): os.remove(d)
        os.symlink(os.path.join(basis_dir, n), d)
    os.remove(os.path.join(aus_dir, teil + ".stl")); m_neu.export(os.path.join(aus_dir, teil + ".stl")); return aus_dir


LISTE_RB = "/media/oem/scan/rc-park_tmp/grauzone/rueckblick_liste.json"   # Rueckblick-Satz (siehe liste_rueckblick)


def liste_rueckblick():
    """Verworfene Runden (angenommen == false) mit Foto-F1-Gewinn in [-0,005; +0,02), Teile-Ordner vorher/nachher vorhanden. Kennung rb_<lauf>_r<N>."""
    return {f"rb_{o['lauf']}_r{o['runde']}": o for o in json.load(open(LISTE_RB)) if o["vorher"] and o["nachher"]}


def fall_dirs(objekt, k, wurzel):
    """-> (vorher, nachher, soll, hinweis)"""
    if k.startswith("rb_"):
        o = liste_rueckblick()[k]; L = KREIS % objekt + "/" + o["lauf"]
        return L + "/" + o["vorher"], L + f"/teile_r{o['runde']}_nachher", "rueckblick", f"{o['teil']} dF1 {o['dF1']} dH {o['dH']} dK {o['dK']}"
    if k in BEKANNT:
        lauf, vo, na, soll, hw = BEKANNT[k]; L = KREIS % objekt + "/" + lauf; return L + "/" + vo, L + "/" + na, soll, hw
    art, a1, a2 = (FALLEN[k] + (None,))[:3]
    if art == "umkehr":
        lauf, vo, na = UMKEHR[a1]; L = KREIS % objekt + "/" + lauf
        return L + "/" + na, L + "/" + vo, "negativ", f"Falle Familie: Umkehr von {a1} (richtig -> falsch)"
    b = KREIS % objekt + "/" + BASIS_LAUF + "/" + BASIS; m = trimesh.load(os.path.join(b, a1 + ".stl"), force="mesh")
    m2 = mod_kasten(m, a2) if art == "kasten" else mod_schiebung(m, *a2) if art == "schieb" else mod_skala(m, a2)
    nach = stand_kopie(b, os.path.join(wurzel, "stand_" + k), a1, m2)
    return b, nach, "negativ", f"Falle {art} {a1} {a2}"


def bilder_fall(objekt, k, wurzel, n_fotos=3):
    vo, na, soll, hw = fall_dirs(objekt, k, wurzel); arb = os.path.join(wurzel, k); os.makedirs(arb, exist_ok=True)
    teile = [FALLEN[k][1]] if k in FALLEN and FALLEN[k][0] != "umkehr" else None
    e = FFP.pruefen(objekt, vo, na, "", teile, None, None, arb, None, n_fotos, True, ohne_befund=True)
    e["_arb"] = arb; e["_soll"] = soll; e["_hinweis"] = hw; return e


def pruefe_fall(objekt, e, modell="opus", timeout=900):
    name = objekt
    if not e.get("paare"): e.update({"status": "ungeprueft", "grund": "keine Bilder"}); e["urteil"] = "ungeprueft"; return e
    r = FFP.pruefer(name, e["teile"], "", e["paare"], e["_arb"], modell, timeout, ohne_befund=True, logname="pruefer_grauzone.log"); e.update(r)
    e["urteil"] = grau_urteil(e); json.dump({k: v for k, v in e.items()}, open(os.path.join(e["_arb"], "erg_grau.json"), "w"), ensure_ascii=False, indent=1); return e


def grau_urteil(erg):
    """Grauzonen-Tor: besteht nur bei verbessert, nicht erfunden, sicher == hoch."""
    if erg.get("status") != "ok": return "ungeprueft"
    if erg.get("erfunden") is True: return "erfunden"
    if erg.get("verbessert") is True and erg.get("sicher") == "hoch": return "besteht"
    if erg.get("verbessert") is True: return "unsicher"
    return "nicht_verbessert"


def lauf(objekt, kennungen, nur_bilder, modell, wurzel=ARBEIT, par=3):
    os.makedirs(wurzel, exist_ok=True); t0 = time.time(); erg = {}
    for k in kennungen:    # Bilder GPU-seriell
        try: erg[k] = bilder_fall(objekt, k, wurzel); print(f"== Bilder {k}: {len(erg[k].get('paare') or {})} Dreierbilder", flush=True)
        except Exception as ex: print(f"== Bilder {k} FEHLER {ex!r}", flush=True); erg[k] = {"status": "ungeprueft", "grund": repr(ex), "urteil": "ungeprueft", "_soll": "negativ", "_hinweis": "", "_arb": os.path.join(wurzel, k), "paare": {}}
    t_b = time.time() - t0
    if not nur_bilder:
        with ThreadPoolExecutor(par) as ex:
            futs = {k: ex.submit(pruefe_fall, objekt, e, modell) for k, e in erg.items() if e.get("paare")}
            for k, f in futs.items(): f.result(); print(f"== Urteil {k}: {erg[k]['urteil']} sicher {erg[k].get('sicher')}", flush=True)
    return erg, t_b, time.time() - t0


def aus_bildern(ergebnis_json, objekt, modell, par=3, nur=None):
    """Pruefer-Phase auf bereits erzeugten Dreierbildern (Ergebnis einer --nur_bilder-Stufe); Bildpfade -> paare, Teilname aus dem Dateinamen."""
    tab = json.load(open(ergebnis_json))["tab"]; erg = {}; t0 = time.time()
    for r in tab:
        k = r["fall"]
        if nur and k not in nur: continue
        paare = {}; teile = []
        for p in r["bilder"]:
            b = os.path.basename(p)[:-4]; tn, rest = b.split("_Kontur_") if "_Kontur_" in b else (b.rsplit("_", 1)[0], None)
            nr = rest if rest else b.rsplit("_", 1)[1]
            paare[f"{tn} {'Kontur ' if rest else ''}{nr}"] = p
            if tn not in teile: teile.append(tn)
        erg[k] = {"paare": paare, "teile": teile, "_arb": os.path.dirname(os.path.dirname(r["bilder"][0])), "_soll": r["soll"], "_hinweis": r["hinweis"]}
    with ThreadPoolExecutor(par) as ex:
        futs = {k: ex.submit(pruefe_fall, objekt, e, modell) for k, e in erg.items()}
        for k, f in futs.items(): f.result(); print(f"== Urteil {k}: {erg[k]['urteil']} sicher {erg[k].get('sicher')}", flush=True)
    return erg, 0.0, time.time() - t0


def tabelle(erg):
    zeilen = []
    for k, e in erg.items():
        soll = e["_soll"]; u = e.get("urteil"); ok = None if u is None or soll == "rueckblick" else ((u == "besteht") if soll == "positiv" else (u != "besteht"))
        zeilen.append({"fall": k, "soll": soll, "urteil": u, "sicher": e.get("sicher"), "ok": ok, "hinweis": e.get("_hinweis"), "begruendung": (e.get("begruendung") or e.get("grund") or "")[:400],
                       "bilder": list((e.get("paare") or {}).values())})
    return zeilen


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("stufe", choices=["fallen", "bekannt", "alle", "rueckblick"], nargs="?", default="alle"); ap.add_argument("--objekt", default="kaufhaus_grob3")
    ap.add_argument("--nur", help="Kennungen Komma"); ap.add_argument("--nur_bilder", action="store_true"); ap.add_argument("--modell", default="opus"); ap.add_argument("--bilder_aus", help="ergebnis.json einer --nur_bilder-Stufe: nur Pruefer-Phase"); ap.add_argument("--aus", default=os.path.join(ARBEIT, "ergebnis.json"))
    a = ap.parse_args()
    ks = list(FALLEN) if a.stufe == "fallen" else list(BEKANNT) if a.stufe == "bekannt" else list(liste_rueckblick()) if a.stufe == "rueckblick" else list(FALLEN) + list(BEKANNT)
    if a.nur: ks = a.nur.split(",")
    if a.bilder_aus: erg, t_b, t_g = aus_bildern(a.bilder_aus, a.objekt, a.modell, nur=a.nur.split(",") if a.nur else None)
    else:
        import gpu_slot; gpu_slot.belegen("test_grauzone_tor"); erg, t_b, t_g = lauf(a.objekt, ks, a.nur_bilder, a.modell)
    tab = tabelle(erg); print("\nFall | Soll | Urteil | sicher | ok | Hinweis")
    for r in tab: print(" | ".join(str(r[x]) for x in ("fall", "soll", "urteil", "sicher", "ok", "hinweis")))
    fa = [r for r in tab if r["fall"] in FALLEN]; fehl = [r for r in fa if r["urteil"] == "besteht"]
    print(f"Fehlannahmen auf Fallen: {len(fehl)} von {len(fa)}; Bilder {t_b:.0f} s, gesamt {t_g:.0f} s")
    os.makedirs(os.path.dirname(a.aus), exist_ok=True); json.dump({"tab": tab, "sek_bilder": t_b, "sek_gesamt": t_g}, open(a.aus, "w"), ensure_ascii=False, indent=1)
    sys.exit(0 if a.nur_bilder or all(r["ok"] for r in tab if r["ok"] is not None) else 1)


if __name__ == "__main__":
    main()
