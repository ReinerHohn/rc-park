#!/usr/bin/env python3
"""lg_zwischenspeicher.py - Zwischenspeicher fuer ALIKED-Merkmale und Grob-LightGlue-Paarwerte des Nachholens (tools/zusatzfotos_lightglue.py paare), 23.11.2026.

Anlass (Kette 1122q, Schritt paare 50 min): ALIKED fuer 1014 Bilder 412 s + Grob-LightGlue fuer ALLE 438.900 Kandidatenpaare ~2450 s - und jeder Folgelauf
rechnete alles neu, obwohl sich die Kandidaten kaum aendern (ein neuer Download aendert roh/ -> die Schritt-Kette rechnet ab 'vorbereiten' alles).
Schluessel = INHALTS-Hash des Bildes (sha1 der Datei, nicht der Name) + Parameter-Kennung (Modellstand LightGlue-Commit, torch-Version, Extraktor-/Matcher-Konfiguration,
max_kp, resize, grob, Mischpraezision). Andere Parameter -> andere Kennung -> neu gerechnet; gleiche Bilder + gleiche Parameter -> gespeicherter Wert.
Ablage: <ordner>/aliked_<kennung>/<hash>.npz (Zahlen unveraendert, float32 wie gerechnet: kein Qualitaetsverlust) und <ordner>/grob.sqlite (Tabelle grob: schluessel, n).
Platz: ~2,1 MB je Bild bei 4096 Merkmalen (1014 Bilder ~2,2 GB); aufraeumen() loescht Merkmale von Bildern, die im aktuellen Lauf nicht vorkamen, und
Grob-Werte anderer Kennungen - der Speicher waechst also nicht ueber einen Lauf hinaus.
Nur numpy + sqlite3 (CPU-Test: tools/test_nachhol_tempo.py).
"""
import os, json, glob, hashlib, sqlite3
import numpy as np


def inhalt_hash(pfad):
    """sha1 des Dateiinhalts (40 Hex-Zeichen)."""
    h = hashlib.sha1()
    with open(pfad, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def kennung(**teile):
    """Parameter-Kennung (16 Hex-Zeichen) aus beliebigen JSON-faehigen Teilen; nicht JSON-faehiges wird als Text genommen."""
    return hashlib.sha1(json.dumps(teile, sort_keys=True, default=str).encode()).hexdigest()[:16]


def modellstand():
    """Stand der Bibliotheken fuer die Kennung: LightGlue-Commit (direct_url.json der Installation) bzw. Version, torch-Version."""
    import importlib.metadata as md
    out = {}
    for paket in ("lightglue", "torch"):
        try:
            d = md.distribution(paket); out[paket] = d.version
            du = d.read_text("direct_url.json")
            if du: out[paket + "_commit"] = json.loads(du).get("vcs_info", {}).get("commit_id")
        except Exception: out[paket] = None
    return out


class Speicher:
    def __init__(self, ordner, merkmal_kennung, grob_kennung, merkmale=True):
        self.ordner = ordner; os.makedirs(ordner, exist_ok=True); self.mk = merkmal_kennung; self.gk = grob_kennung; self.mit_merkmalen = merkmale
        self.md = os.path.join(ordner, "aliked_" + merkmal_kennung)
        if merkmale: os.makedirs(self.md, exist_ok=True)
        self.con = sqlite3.connect(os.path.join(ordner, "grob.sqlite"), timeout=60)
        self.con.execute("create table if not exists grob (schluessel text primary key, n integer not null)"); self.con.commit()
        self.stat = dict(merkmale_gespeichert=0, merkmale_gerechnet=0, grob_gespeichert=0, grob_gerechnet=0)

    # --- ALIKED-Merkmale je Bild ---
    def merkmale_holen(self, h):
        """dict {name: np.ndarray} oder None (nicht da / beschaedigt -> neu rechnen)."""
        if not self.mit_merkmalen: return None
        p = os.path.join(self.md, h + ".npz")
        if not os.path.exists(p): return None
        try:
            with np.load(p, allow_pickle=False) as z: d = {k: z[k] for k in z.files}
        except Exception: return None
        self.stat["merkmale_gespeichert"] += 1; return d

    def merkmale_ablegen(self, h, d):
        """d {name: np.ndarray}; atomar (tmp + replace), damit ein Abbruch keine halbe Datei hinterlaesst."""
        self.stat["merkmale_gerechnet"] += 1
        if not self.mit_merkmalen: return
        p = os.path.join(self.md, h + ".npz"); t = p + f".{os.getpid()}.tmp.npz"
        np.savez(t, **{k: np.asarray(v) for k, v in d.items()}); os.replace(t, p)

    # --- Grob-LightGlue-Paarwerte (Anzahl Matches mit --grob Merkmalen) ---
    def _s(self, hx, hy): return f"{self.gk}|{hx}|{hy}"

    def grob_holen_alle(self, paare_h):
        """paare_h [(hx, hy)] (Reihenfolge wie gerechnet: image0 = hx) -> {(hx, hy): n} fuer alle gespeicherten."""
        out = {}; sl = [self._s(a, b) for a, b in paare_h]; rueck = dict(zip(sl, paare_h))
        for i in range(0, len(sl), 900):
            teil = sl[i:i + 900]
            for s, n in self.con.execute(f"select schluessel, n from grob where schluessel in ({','.join('?' * len(teil))})", teil): out[rueck[s]] = int(n)
        return out

    def grob_ablegen(self, werte):
        """werte [(hx, hy, n)]."""
        if not werte: return
        self.con.executemany("insert or replace into grob (schluessel, n) values (?, ?)", [(self._s(a, b), int(n)) for a, b, n in werte]); self.con.commit()

    def aufraeumen(self, behalten_h):
        """Merkmale von Bildern ausserhalb <behalten_h> und Ordner anderer Merkmal-Kennungen loeschen; Grob-Werte anderer Kennung oder mit einem Bild ausserhalb <behalten_h> loeschen."""
        bh = set(behalten_h); weg_m = 0
        for d in glob.glob(os.path.join(self.ordner, "aliked_*")):
            for f in glob.glob(os.path.join(d, "*.npz")):
                if d != self.md or os.path.basename(f)[:-4] not in bh: os.remove(f); weg_m += 1
            if d != self.md:
                try: os.rmdir(d)
                except OSError: pass
        weg = [s for (s,) in self.con.execute("select schluessel from grob") if not (s.startswith(self.gk + "|") and all(t in bh for t in s.split("|")[1:]))]
        for i in range(0, len(weg), 900): self.con.execute(f"delete from grob where schluessel in ({','.join('?' * len(weg[i:i + 900]))})", weg[i:i + 900])
        self.con.commit()
        return dict(geloescht_merkmale=weg_m, geloescht_grob=len(weg))

    def schliessen(self): self.con.close()
