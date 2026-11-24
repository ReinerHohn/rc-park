#!/usr/bin/env python3
"""Synthetischer Test der projektunabhaengigen Wissenswerkzeuge (wissen_suchen, luecken, wiederfinden) in einem Wegwerf-Projekt.
Aufruf: python3 -I test_wissen.py  (rc 0 = OK). Kein Netz, kein Schreiben ausser im Temp-Ordner."""
import io
import json
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
import luecken as L  # noqa: E402
import wiederfinden as WF  # noqa: E402
import wissen_suchen as WS  # noqa: E402


def schreibe(p, t):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(t, encoding="utf-8")


def lauf(fn, argv):
    b = io.StringIO()
    with redirect_stdout(b):
        rc = fn(argv)
    return rc, b.getvalue()


def main():
    with tempfile.TemporaryDirectory() as t:
        w = Path(t)
        schreibe(w / "PROJEKT.md", "# Wurzel\n- Ast [api](Doku/projekt/api.md)\n")
        schreibe(w / "Doku" / "projekt" / "api.md", "# API\n## Versucht\n- 02.11. · Anmeldung per Token-Cache → ✗ · Ablauf nach 1 h [REGISTER A1]\n")
        schreibe(w / "Doku" / "REGISTER.md", "# Register\n## A1 Token-Cache (02.11.)\nx\n## A2 Sitzungsdauer verlaengert (03.11.)\ny\n## A2 doppelt\nz\n")
        schreibe(w / "Doku" / "archiv" / "ALT_BERICHT.md", "# Alter Bericht\nAnmeldung brach nach einer Stunde ab\n")
        schreibe(w / "scripts" / "token_cache.py", '"""token_cache.py - Anmelde-Token zwischenspeichern, Ablauf pruefen."""\n')
        schreibe(w / ".claude" / "wissen_synonyme.json", json.dumps({"gruppen": [["Anmeldung", "Login", "Token"]]}))
        schreibe(w / ".claude" / "doku-pflege.json", json.dumps({"wissen": {
            "luecken": [{"name": "REGISTER", "glob": "Doku/REGISTER.md", "art": "abschnitt", "kopf": "^## (.*)", "id": "^([A-Z][0-9]+)\\b"},
                        {"name": "archiv", "glob": "Doku/archiv/*.md", "art": "datei"}], "memory": False}}))
        schreibe(w / ".claude" / "wissen_wiederfinden.json", json.dumps({"mindest_recall": 1.0, "faelle": [
            {"name": "Login laeuft ab", "suche": ["Login", "laeuft", "nach", "Stunde", "ab"], "erwartet": "api\\.md|token_cache|ALT_BERICHT"}]}))
        g = ["git", "-C", str(w), "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run(g + ["init", "-q"], check=True)
        subprocess.run(g + ["add", "-A"], check=True)
        subprocess.run(g + ["commit", "-qm", "basis"], check=True)   # nicht eingecheckte Dateien sind keine Quelle
        schreibe(w / "Doku" / "archiv" / "FREMD.md", "# fremde Arbeitsdatei, nie eingecheckt\n")
        # Suche: Synonym Login -> Anmeldung, Rangliste zuerst, Werkzeug aus scripts/
        rc, aus = lauf(WS.main, ["Login", "--wurzel", str(w), "--memory", "aus", "--ohne-git"])
        assert rc == 0 and "== TOP" in aus and "Doku/projekt/api.md" in aus and "scripts/token_cache.py" in aus, aus
        assert aus.index("== TOP") < aus.index("== Wissensbaum"), aus
        # Luecken: A1 im Baum, A2 + A2#2 fehlen, Archivdatei fehlt; Doppel-ID gemeldet
        rc, aus = lauf(L.main, ["--wurzel", str(w), "--memory", "aus"])
        assert rc == 1 and "REGISTER: 3 Eintraege, 1 im Baum, 2 fehlend, 1 doppelte IDs" in aus and "archiv: 1 Eintraege, 0 im Baum" in aus, aus
        schreibe(w / "Doku" / "projekt" / "api.md", "# API\n## Versucht\n- 02.11. · Token-Cache ✗ [REGISTER A1]\n- 03.11. · [REGISTER A2, A2#2]"
                 " · Bericht archiv/ALT_BERICHT\n")
        rc, aus = lauf(L.main, ["--wurzel", str(w), "--memory", "aus"])
        assert rc == 0 and "OK: 0 Luecken" in aus, aus
        # Nachweis: Recall@5
        rc, aus = lauf(WF.main, ["--wurzel", str(w)])
        assert rc == 0 and "RECALL@5 = 1/1" in aus, aus
    print("OK test_wissen (doku-pflege)")


if __name__ == "__main__":
    main()
