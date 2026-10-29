#!/usr/bin/env python3
"""test_quellen_hart.py — ADVERSARIALE Tests, die BEWEISEN WOLLEN, dass eine Quelle vergessen oder
ein ✅ gefälscht wurde. Jeder Test ist ein Angriff. Rot = Beweis, dass geschlampt wurde.

Lauf:  python3 tests/test_quellen_hart.py            (standalone, Exit 1 bei Fehlschlag)
       pytest tests/test_quellen_hart.py             (auch pytest-kompatibel)

Deckt ab (Hofgut Sternen):
  1  Register erschöpfend & konsistent (Tool-REGISTER == QUELLEN_REGISTER.md)
  2  KEINE Repo-Quelle liegt ungenutzt herum  (der Gotcha, der DOM1/DGM1 fing)
  3  Kein ✅ ohne echtes Artefakt  (fängt LAZ/glas-Fehlalarm)
  4  Gate BLOCKIERT wirklich (Exit!=0 solange offen)
  5  nDOM-First quercheckt LOD2-First (Laser bestätigt amtliches Massing)
  6  Footprint ist der ECHTE LOD2-Grundriss (≥8 Teile, ~47×43 m) — nicht die geratene Box
  7  Farben GEMESSEN (OG dunkel, nicht weiß geraten)
  8  JAGD: irgendein Geo-File der Kachel, das KEIN Register-Muster kennt = vergessener Quellentyp
"""
import glob, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
NAME = "hofgut_sternen"
MD = f"modelle/{NAME}"
sys.path.insert(0, "tools")
import quellen_inventar as QI


def _rows():
    """EXAKT der Tool-Klassifikator (kein Drift) → {key: {used,hits,status,na_reason}}."""
    _, rows = QI.inventory(NAME)
    return {r["key"]: r for r in rows}


def test_1_register_konsistent():
    """Jeder Typ im Tool muss im Master-Register-MD stehen und umgekehrt."""
    tool_keys = {k for k, *_ in QI.REGISTER}
    md = open("modelle/QUELLEN_REGISTER.md").read()
    for k in tool_keys:
        assert f"**{k}**" in md, f"Typ {k} im Tool, aber NICHT in QUELLEN_REGISTER.md dokumentiert"
    # umgekehrt: alle **FETT**-Typen der Tabelle müssen im Tool sein
    doc_keys = set(re.findall(r"\|\s*\d+\s*\|\s*\*\*([A-Z0-9_]+)\*\*", md))
    for k in doc_keys:
        assert k in tool_keys, f"Typ {k} im Register-MD, aber NICHT im Tool-REGISTER (würde nie geprüft!)"


def test_2_keine_repo_quelle_ungenutzt():
    """AGGRO: Hat ein Quellentyp Dateien im Repo (Kachel), MUSS er genutzt sein. Sonst vergessen."""
    schuldig = [k for k, v in _rows().items() if v["hits"] and not v["used"]]
    assert not schuldig, f"Quelle(n) liegen UNGENUTZT im Repo: {schuldig} — merge-pflichtig!"


def test_2b_na_darf_keine_echten_daten_verstecken():
    """GEMEIN: Eine als n/a markierte Quelle darf KEINE Repo-Dateien dieser Kachel haben — sonst
    drückt der Entwickler vorhandene Daten feige als 'n/a' weg, statt sie zu nutzen."""
    r = _rows()
    gemogelt = [k for k, v in r.items() if v["status"] == "NA" and v["hits"]]
    assert not gemogelt, f"n/a trotz vorhandener Repo-Daten (Daten da, aber weggedrückt!): {gemogelt}"


def test_2c_jede_na_hat_begruendung():
    """Kein stilles n/a: jede n/a-Quelle braucht eine nicht-triviale Begründung (>20 Zeichen)."""
    schwach = [k for k, v in _rows().items() if v["status"] == "NA" and len(v["na_reason"]) < 20]
    assert not schwach, f"n/a ohne echte Begründung: {schwach}"


def test_2d_kein_limbo():
    """Jeder der 16 Typen MUSS entschieden sein: genutzt oder begründet n/a — nichts offen gelassen
    werden, OHNE dass es als OFFEN (rot) sichtbar ist. Spiegelt den Gate-Zustand hart."""
    r = _rows()
    offen = [k for k, v in r.items() if v["status"] in ("REPO_UNUSED", "UPSTREAM")]
    # offen ist erlaubt, MUSS aber mit rotem Gate (Exit!=0) einhergehen — siehe test_4.
    # Hier nur: kein Typ fehlt ganz.
    assert len(r) == len(QI.REGISTER), "Klassifikator liefert nicht alle Register-Typen"


def test_2e_kein_file_doppelt_gezaehlt():
    """Kein Repo-File darf unter ZWEI Quellentypen auftauchen (Doppelzählung → Phantom-Quelle)."""
    r = _rows(); seen = {}
    for k, v in r.items():
        for f in v["hits"]:
            seen.setdefault(f, []).append(k)
    doppelt = {f: ks for f, ks in seen.items() if len(ks) > 1}
    assert not doppelt, f"Dateien doppelt klassifiziert: {doppelt}"


def test_3_kein_gefaelschtes_haekchen():
    """Kein ✅ ohne echtes abgeleitetes Artefakt (fängt LAZ/glas-Fehlalarm)."""
    r = _rows()
    if r["LAZ_ALS"]["used"]:
        assert glob.glob(f"{MD}/*.laz") or glob.glob(f"{MD}/*.las") or os.path.exists(f"{MD}/punktwolke.json"), \
            "LAZ_ALS als genutzt markiert, aber KEINE Punktwolke/Artefakt da = Fake-Haken"
    if r["DOM1"]["used"]:
        assert os.path.exists(f"{MD}/dom_roof.json") or os.path.exists(f"{MD}/ndom.json"), \
            "DOM1 ✅ aber kein dom_roof/ndom-Artefakt"
    if r["DGM1"]["used"]:
        assert os.path.exists(f"{MD}/terrain.json") or os.path.exists(f"{MD}/ndom.json"), \
            "DGM1 ✅ aber kein terrain/ndom-Artefakt"


def test_4_gate_blockiert_bei_offenen():
    """INVARIANTE: Gate-Exit != 0 GENAU DANN, wenn offene Quellen existieren. Nicht per String,
    sondern gegen den Klassifikator — sonst kann die Ausgabe driften und das Gate heimlich zahnlos werden."""
    offen = [r for r in _rows().values() if r["status"] in ("REPO_UNUSED", "UPSTREAM")]
    rc = subprocess.run(["python3", "tools/quellen_inventar.py", "--name", NAME],
                        capture_output=True, text=True, timeout=60).returncode
    assert (rc != 0) == (len(offen) > 0), \
        f"Gate-Exit {rc} passt NICHT zu {len(offen)} offenen Quellen (zahnlos oder Fehlalarm)"


def test_5_ndom_quercheck_lod2():
    """Laser-First (nDOM) muss amtlichen LOD2-First bestätigen — sonst ist ein Merge faul."""
    assert os.path.exists(f"{MD}/ndom.json"), "nDOM nicht gerechnet (DOM1−DGM1 vergessen)"
    nd = json.load(open(f"{MD}/ndom.json"))
    assert nd["quercheck_first"] == "PASS", f"nDOM↔LOD2 First FLAG: {nd}"
    assert abs(nd["first_ueber_boden_m"] - nd["lod2_first_max_m"]) < 2.5


def test_6_footprint_ist_lod2_nicht_box():
    """Der Grundriss MUSS der echte LOD2-Komplex sein (≥8 Teile, ~47×43), nicht die alte 40×13-Box."""
    fp = json.load(open(f"{MD}/footprint.json"))
    teile = fp["teile"]
    assert len(teile) >= 8, f"nur {len(teile)} Teile — LOD2-Grundriss nicht voll genutzt"
    import numpy as np
    allp = np.vstack([np.array(t["ring_xy_m"]) for t in teile])
    w = allp[:, 0].max() - allp[:, 0].min(); d = allp[:, 1].max() - allp[:, 1].min()
    assert w > 40 and d > 38, f"Grundriss-Ausdehnung {w:.0f}x{d:.0f} — nicht der 47x43-Komplex (Box-Verdacht!)"


def test_7_farben_gemessen_nicht_weiss():
    """OG-Farbe muss aus dem Foto gemessen & DUNKEL sein (nicht die geratene weiße Wand)."""
    assert os.path.exists(f"{MD}/farben.json"), "farben.json fehlt — Farben nicht aus Foto gemessen"
    f = json.load(open(f"{MD}/farben.json"))
    og = f["og_lauben"]
    assert max(og) < 160, f"OG-Holz {og} zu hell — riecht nach geratener weißer Wand"


def test_8_jagd_nach_vergessenem_quellentyp():
    """ULTIMATIV: Finde IRGENDEIN Geo-File der Kachel, das KEIN Register-Muster trifft = vergessener Typ."""
    E, N, *_ = json.load(open(f"{MD}/footprint.json"))["origin_utm"]
    e, n = int(E) // 1000, int(N) // 1000
    tnums = {f"{e+de}_{n+dn}" for de in (-2, -1, 0, 1) for dn in (-2, -1, 0, 1)}
    geoexts = (".tif", ".xyz", ".gml", ".las", ".laz", ".jp2", ".asc", ".copc")
    allpats = re.compile("|".join(p for _, _, _, pats, _, _ in QI.REGISTER for p in pats), re.I)
    forgotten = []
    for f in glob.glob("daten/**", recursive=True):
        if not os.path.isfile(f):
            continue
        b = os.path.basename(f)
        if b.lower().endswith(geoexts) and any(t in f for t in tnums):
            if not allpats.search(b):
                forgotten.append(f)
    assert not forgotten, f"VERGESSENER Quellentyp (kein Register-Muster): {forgotten[:5]}"


# ---- standalone runner (ohne pytest) ----
if __name__ == "__main__":
    tests = sorted(k for k in globals() if k.startswith("test_"))
    fails = 0
    for t in tests:
        try:
            globals()[t]()
            print(f"  PASS  {t}")
        except AssertionError as e:
            fails += 1; print(f"  FAIL  {t}\n          └─ {e}")
        except Exception as e:
            fails += 1; print(f"  ERROR {t}\n          └─ {type(e).__name__}: {e}")
    print(f"\n{len(tests)-fails}/{len(tests)} Tests bestanden.")
    sys.exit(1 if fails else 0)
