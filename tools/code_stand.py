#!/usr/bin/env python3
"""code_stand.py <werkzeug.py> [...] - CODE-STAND fuer Zwischenstaende: Fingerabdruck der beteiligten Werkzeuge (Inhalt, nicht Zeit) samt ihrer Hilfsmodule aus tools/.

WARUM (22.11.2026, Nulllauf kette-schwabentor-null-1122c): die Stufe 'sfm' uebernahm die Zwischenstaende von 02:39 (seiten_modelle.json 'teil_a_allein', sparse/0), obwohl seit
05:40 der Rueckfall Foto-GPS (tools/seiten_gps_vereinen.py) in main war - die Stand-Dateien kannten nur die EINGABEN (Groesse + Zeit), nicht den Code. Der Fix lief nie.
REGEL: teure Rechenschritte (Merkmale, Paare, Mapper je Teil, dichte Wolke je Teil) haengen nur an ihren Eingaben; BILLIGE Folgeschritte (Vereinen, Einsetzen, Tore) tragen
zusaetzlich code_stand(<ihre Werkzeuge>) in ihrer Stand-Datei und laufen neu, sobald sich dieser Code aendert.
code_stand(*werkzeuge) -> 12 Hex-Zeichen (sha1 ueber Name + Inhalt jeder Datei); dateien(*werkzeuge) -> die eingerechneten Dateien. Eingerechnet werden die genannten Dateien und
REKURSIV alle Module, die sie aus tools/ importieren (import x / from x import y, auch innerhalb von Funktionen; Fremdbibliotheken nicht). Fehlende Datei -> Name mit 'fehlt'.
GRENZE: Aufrufe per Unterprozess (subprocess, LAUF) sieht die Importsuche nicht - solche Werkzeuge muss der Aufrufer selbst nennen. Kommentaraenderungen zaehlen mit (lieber
einmal zu oft neu als den Fix nicht ausfuehren). Nur Standardbibliothek (laeuft in jeder Umgebung)."""
import os, sys, ast, hashlib

T = os.path.dirname(os.path.abspath(__file__))


def _importe(pfad, wurzel):
    """Namen der Module aus <wurzel>, die die Datei importiert (alle Ebenen des Syntaxbaums)."""
    try: baum = ast.parse(open(pfad, encoding="utf-8", errors="replace").read())
    except (OSError, SyntaxError): return []
    n = set()
    for k in ast.walk(baum):
        if isinstance(k, ast.Import): n.update(a.name.split(".")[0] for a in k.names)
        elif isinstance(k, ast.ImportFrom) and k.module and not k.level: n.add(k.module.split(".")[0])
    return sorted(m for m in n if os.path.isfile(os.path.join(wurzel, m + ".py")))


def dateien(*werkzeuge, wurzel=T):
    """Genannte Werkzeuge (Name in <wurzel> oder Pfad) + rekursiv ihre Hilfsmodule aus <wurzel> -> sortierte Liste absoluter Pfade."""
    offen = [w if os.path.isabs(w) else os.path.join(wurzel, w) for w in werkzeuge]; fertig = set()
    while offen:
        p = os.path.abspath(offen.pop())
        if p in fertig: continue
        fertig.add(p)
        if os.path.isfile(p): offen += [os.path.join(wurzel, m + ".py") for m in _importe(p, wurzel)]
    return sorted(fertig)


def code_stand(*werkzeuge, wurzel=T):
    """Fingerabdruck (12 Hex-Zeichen) der Werkzeuge samt Hilfsmodulen; aendert sich, sobald sich eine dieser Dateien inhaltlich aendert."""
    h = hashlib.sha1()
    for p in dateien(*werkzeuge, wurzel=wurzel):
        h.update(os.path.basename(p).encode() + b"\0")
        try: h.update(hashlib.sha1(open(p, "rb").read()).digest())
        except OSError: h.update(b"fehlt")
    return h.hexdigest()[:12]


if __name__ == "__main__":
    if len(sys.argv) < 2: print(__doc__); sys.exit(2)
    for p in dateien(*sys.argv[1:]): print(" ", os.path.relpath(p, T))
    print("CODE-STAND", code_stand(*sys.argv[1:]))
