"""Viewer-Klick -> Beobachtung in der Masstabelle (Regel 2, Lehre L48/L48b: Fund per GEOMETRIE dem Teil zuordnen, nicht raten).
Eingabe: der JSON-Text aus dem Viewer ("Alle kopieren"), als Datei oder per stdin ('-').
Aufruf: beobachtung_aus_viewer.py <objekt> <datei|-> [--schreiben] [--kein_formtest]
Ohne --schreiben nur Vorschau. Je Eintrag: teil (STL-Name 'familie__name' -> 'familie:name'), merkmal = Befundtext,
weltpunkt_m/foto/blick aus dem Klick, wer 'Nutzer (Viewer-Klick)', pruef_stichworte aus dem Befundtext, formfamilie_test true
(tools/test_formfamilie_nutzerfunde.py liest die Faelle von dort). Doppelte (gleiches Teil + gleicher Text) werden uebersprungen."""
import sys, json, os, re, datetime
if len(sys.argv) < 3: sys.exit(__doc__)
obj, quelle = sys.argv[1], sys.argv[2]
roh = sys.stdin.read() if quelle == "-" else open(quelle).read()
J = json.loads(roh); B = J["beobachtungen"] if isinstance(J, dict) else J
if isinstance(J, dict) and J.get("objekt") and J["objekt"] != obj: sys.exit(f"Viewer-Daten gehoeren zu {J['objekt']}, nicht zu {obj}")
pfad = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "modelle", obj, "masstabelle.json")
M = json.load(open(pfad)); offen = M.setdefault("beobachtungen_offen", [])
STOP = set("der die das ein eine einer eines und oder ist sind im in am an auf ueber unter mit ohne von vom zu zum zur nicht kein keine viel viele sehr "
           "modell foto wirklichkeit eigentlich irgendwie komisch komische auch noch immer hier dort dieser diese dieses sein seine wird werden".split())
def stichworte(t):
    t = t.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    w = [x for x in re.findall(r"[a-z]{4,}", t) if x not in STOP]; return list(dict.fromkeys(w))[:6]
neu = []
for b in B:
    teil = b.get("teil"); txt = (b.get("beobachtung") or "").strip()
    if not teil: print("ohne Teil (Klick traf keine Teilflaeche) - uebersprungen:", txt); continue
    if not txt: print("ohne Befundtext - uebersprungen:", teil); continue
    t = teil.replace("__", ":", 1)
    if any(o.get("teil") == t and o.get("merkmal") == txt for o in offen): print("schon vorhanden:", t, txt); continue
    sw = stichworte(txt)
    e = {"teil": t, "merkmal": txt,
         "text": f"Nutzer per Viewer-Klick ({b.get('zeit', '')[:16]}): Punkt {b.get('weltpunkt_m')} m im Netzrahmen, Blick yaw/pit {b.get('blick')}, passendes Foto {b.get('foto')}. Teil per Geometrie (naechste Teilflaeche) zugeordnet.",
         "naechster_schritt": "Stufe 0 (VORLAGE_BAUTEIL_RUNDE): Form in >=3 Fotos beschreiben, Zuordnung zum Teil am Foto bestaetigen, dann messen.",
         "datum": (b.get("zeit") or datetime.date.today().isoformat())[:10], "wer": "Nutzer (Viewer-Klick)",
         "weltpunkt_m": b.get("weltpunkt_m"), "foto": b.get("foto"), "blick": b.get("blick"),
         "pruef_stichworte": sw, "formfamilie_test": "--kein_formtest" not in sys.argv}
    if not sw: e["formfamilie_test"] = False; print("WARNUNG keine Stichworte (Text zu kurz) -> formfamilie_test false:", t)
    neu.append(e); print("NEU", t, "|", txt, "| Stichworte", sw)
if "--schreiben" in sys.argv and neu:
    offen.extend(neu); open(pfad, "w").write(json.dumps(M, ensure_ascii=False, indent=1) + "\n"); print(len(neu), "Beobachtung(en) eingetragen in", os.path.normpath(pfad))
elif neu: print(len(neu), "neu - Vorschau, mit --schreiben eintragen")
