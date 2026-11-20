#!/usr/bin/env python3
"""baum_erzeugen.py - Wissensbaum fuer KI-Suche (Nutzer 20.11.2026: "Informationen baumartig, damit der Kontext nicht vollballert").
Erzeugt (nie von Hand pflegen, nach neuen Dateien erneut laufen lassen):
  modelle/INDEX.md            Wurzel der Dokumente: Aeste nach Thema, je Datei Groesse + erste Zeile; grosse Dateien -> Inhaltsverzeichnis
  modelle/inhalt/<name>.md    Ueberschriften grosser Dokumente (>= 20 kB) mit Zeilennummern -> gezielt per Read offset/limit lesen
  modelle/archiv/INDEX.md     Archiv (alte Staende, Plaene, Rundenlogbuecher)
  tools/INDEX.md              Wurzel der Werkzeuge: Themen mit Anzahl -> tools/index/<thema>.md (je Werkzeug Umgebung + Docstring-Zeile)
Aufruf: python3 tools/baum_erzeugen.py"""
import ast, os, re, warnings
warnings.simplefilter("ignore", SyntaxWarning)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); M = os.path.join(ROOT, "modelle"); T = os.path.join(ROOT, "tools")
GROSS = 20_000

DOK_AESTE = [  # (Ast, Regex auf Dateiname) - erste passende Regel gewinnt
    ("Regeln, Methode, Vorlagen", r"^(REGELN|METHODE|VORLAGE|REZEPT|LIZENZ|KI_AUFRAEUMEN)"),
    ("Ziel, Stand, Aufgaben", r"^(ZIEL|STAND|AUFGABEN|UEBERGABE)"),
    ("SfM, Mapper, Lage", r"(MAPPER|SFM|GLOBAL|COLMAP|LAGE|AUSRICHT|GPS|SEITEN)"),
    ("Fassaden, Bauteile, Kanten", r"(FASSADE|BAUTEIL|KANTE|RIPPEN|FENSTER|RELIEF|ERKER|HELM|DACH)"),
    ("Druck, Bemalung", r"(DRUCK|BAUSATZ|MAL|FARBE)"),
    ("Versuche, Sackgassen", r"^(NICHTS_GEBRACHT|VERSUCH)"),
    ("Recherchen", r"^RECHERCHE"),
    ("Logbuecher", r"^LOG"),
]
WZ_THEMEN = [  # Werkzeug-Themen nach Dateiname
    ("test", r"^test_"),
    ("kette_einstieg", r"^(gesamtkette|bauen_abnehmen|start3d|nullstart|pipeline_objekt|bauwerk_pipeline|auto_bauwerk|schnelltest|regression|job_start|0-3d)"),
    ("alt_objekte_frueher", r"(hirschsprung|linach|hofgut|hoellental|ravenna|muenster|oberkirch|gewichtsstaumauer|gothic|miniland|eggcrate|laser_|grbl|google3d|drone|mapillary|dust3r|gs_kaufhaus|s8_|nubia|hypso|osm|flatpack|fabrik|rcpark_deals)"),
    ("sfm_mapper", r"(sfm|mapper|colmap|glomap|flexglue|merkmal|paare|bildsuche|zerlegen|konsens|registr|kamera)"),
    ("wolke_dicht", r"(wolke|dicht|fusion|patchmatch|tiefe|depth|punkt)"),
    ("lage_ausrichtung", r"(lod2|dgm|dom1|gps|lage|ausricht|rahmen|grundriss|lot|seiten_vereinen|geo)"),
    ("fassade_relief", r"(fassade|wand|relief|stein|putz|fenster|ortho|quader|laube|bogen)"),
    ("kanten_linien", r"(kante|sweep|linie|rippe|feature|limap)"),
    ("foto_mass", r"(foto|bild|mass|zaehl|commons|netz|video|clip|hochblick)"),
    ("bauteil_generator", r"(bauteil|kreis|baukasten|gen|dach|helm|erker|giebel|gaube|figur|form)"),
    ("druck_stl", r"(druck|stl|slice|bambu|prusa|p1s|bausatz|teil)"),
    ("pruefung_abnahme", r"(pruef|tor|regression|abnahme|audit|realitaet|diff|vergleich|beleg|schnelltest)"),
    ("betrieb_job_gpu", r"(job|gpu|platz|umgebung|wache|start|auslager|umzug|hpwmi|git|index|baum|leistung|luefter|cpu|backup|aufraeumen|json|hardcode|pfade|links|installieren)"),
    ("ansicht_html_render", r"(html|view|render|glb|ansicht|ansehen|overlay|szene|scene|thumbnail)"),
    ("bewertung_beweis", r"(bewert|juror|wettbewerb|voting|beweis|check|abdeckung|proportion|qualitaet|kandidat|optimierung|param)"),
    ("geometrie_flaechen", r"(ebenen|flaeche|objekte_|koerper|element|fit|plane|segment|schnitz|kontur|huelle|innenw|freiraum|restfeld|footprint)"),
]


def erste_zeile(p):
    for l in open(p, errors="replace"):
        l = l.strip().lstrip("#").strip()
        if l: return l[:150]
    return ""


def inhalt(p, name):
    zeilen = []; alle = open(p, errors="replace").read().splitlines()
    n_ueb = sum(bool(re.match(r"^#{1,4} ", l)) for l in alle); duenn = os.path.getsize(p) / max(n_ueb, 1) > 5000   # wenig Ueberschriften: Eintragszeilen mit aufnehmen
    for i, l in enumerate(alle, 1):
        if re.match(r"^#{1,4} ", l): zeilen.append(f"- Z.{i}: {l.rstrip()[:140]}")
        elif duenn and re.match(r"^(- |\d+\. )?(\*\*|BS\d+|V\d+|L\d+|20\d\d-\d\d-\d\d|\d{1,2}\.\d{1,2}\.)", l): zeilen.append(f"  - Z.{i}: {l.strip()[:110]}")
    os.makedirs(os.path.join(M, "inhalt"), exist_ok=True)
    open(os.path.join(M, "inhalt", name), "w").write(f"# Inhalt von modelle/{name} (erzeugt; lesen mit Read offset=Zeile)\n" + "\n".join(zeilen or ["(keine Ueberschriften - per grep suchen)"]) + "\n")
    return len(zeilen)


def dokumente():
    aeste = {a: [] for a, _ in DOK_AESTE}; aeste["Sonstiges"] = []
    for f in sorted(os.listdir(M)):
        p = os.path.join(M, f)
        if not (f.endswith(".md") and os.path.isfile(p)) or f == "INDEX.md": continue
        kb = os.path.getsize(p) // 1024; zeile = f"- `modelle/{f}` ({kb} kB) {erste_zeile(p)}"
        if os.path.getsize(p) >= GROSS: n = inhalt(p, f); zeile += f" -> Inhalt `modelle/inhalt/{f}` ({n} Abschnitte)"
        ast_ = next((a for a, r in DOK_AESTE if re.search(r, f, re.I)), "Sonstiges"); aeste[ast_].append(zeile)
    obj = []
    for d in sorted(os.listdir(M)):
        oj = os.path.join(M, d, "objekt.json")
        if os.path.isfile(oj): obj.append(f"`{d}`")
    out = ["# Dokumentbaum (erzeugt von tools/baum_erzeugen.py - nicht von Hand pflegen)",
           "Suche: erst Ast waehlen, dann bei grossen Dateien das Inhaltsverzeichnis (modelle/inhalt/) und nur den Abschnitt lesen (Read offset/limit) oder `grep -n`.",
           "Werkzeuge: tools/INDEX.md. Archiv (alte Staende/Plaene): modelle/archiv/INDEX.md."]
    for a, z in aeste.items():
        if z: out += ["", f"## {a}"] + z
    out += ["", "## Objekte (modelle/<objekt>/: objekt.json, masstabelle.json, MASSNACHWEIS.md, audit/)", ", ".join(obj)]
    open(os.path.join(M, "INDEX.md"), "w").write("\n".join(out) + "\n")
    A = os.path.join(M, "archiv")
    if os.path.isdir(A):
        az = [f"- `modelle/archiv/{f}` ({os.path.getsize(os.path.join(A, f)) // 1024} kB) {erste_zeile(os.path.join(A, f))}" for f in sorted(os.listdir(A)) if f.endswith(".md") and f != "INDEX.md"]
        open(os.path.join(A, "INDEX.md"), "w").write("# Archiv (erzeugt; abgeloeste Staende, Plaene, Rundenlogbuecher, alte Recherchen - nur bei Bedarf)\n" + "\n".join(az) + "\n")
    return sum(map(len, aeste.values()))


def umgebung(src):
    if re.search(r"^\s*(import|from)\s+pycolmap", src, re.M): return "col"
    if re.search(r"^\s*(import|from)\s+(torch|cv2|kornia|lightglue)", src, re.M): return "seg"
    if re.search(r"^\s*(import|from)\s+(trimesh|manifold3d|shapely)", src, re.M): return "gen"
    return "-"


def werkzeuge():
    th = {t: [] for t, _ in WZ_THEMEN}; th["sonstige"] = []
    for f in sorted(os.listdir(T)):
        p = os.path.join(T, f)
        if f.endswith(".py"):
            src = open(p, errors="replace").read()
            try: d = ast.get_docstring(ast.parse(src)) or ""
            except SyntaxError: d = ""
            z = f"- `tools/{f}` [{umgebung(src)}] {' '.join(d.split(chr(10) * 2)[0].split())[:180] or '(kein Docstring)'}"
        elif f.endswith(".sh"):
            k = [l[1:].strip() for l in open(p, errors="replace").read().splitlines()[1:5] if l.startswith("#")]
            z = f"- `tools/{f}` [sh] {' '.join(k)[:180] or '(kein Kopfkommentar)'}"
        else: continue
        th[next((t for t, r in WZ_THEMEN if re.search(r, f, re.I)), "sonstige")].append(z)
    os.makedirs(os.path.join(T, "index"), exist_ok=True)
    wurzel = ["# Werkzeugbaum (erzeugt von tools/baum_erzeugen.py - nicht von Hand pflegen)",
              "Umgebung: col = /media/oem/scan/venv-colmap (pycolmap), seg = /media/oem/scan/venv-seg (torch/CUDA), gen = ~/.venvs/rcpark (trimesh), - = beliebig.",
              "Suche: Thema waehlen und nur diese Datei lesen, oder `grep -ih <stichwort> tools/index/*.md`. Einstieg der Kette: tools/gesamtkette.py, ./0-3d-modell.sh.", ""]
    for t, z in th.items():
        open(os.path.join(T, "index", f"{t}.md"), "w").write(f"# Werkzeuge: {t} ({len(z)})\n" + "\n".join(z) + "\n")
        wurzel.append(f"- {t} ({len(z)}) -> `tools/index/{t}.md`")
    open(os.path.join(T, "INDEX.md"), "w").write("\n".join(wurzel) + "\n")
    return sum(map(len, th.values()))


if __name__ == "__main__":
    print(f"BAUM: {dokumente()} Dokumente, {werkzeuge()} Werkzeuge")
