#!/usr/bin/env python3
"""wissen_bedeutung.py - Bedeutungssuche (Satz-Embedding) fuer tools/wissen_suchen.py: findet Zeilen auch OHNE gemeinsames Wort.

Anlass 24.11.2026: Die Wortsuche fand 12/12 Verlustfaelle nur dank je Fall gelernter Synonyme; der nie abgestimmte Kontrollsatz blieb
4/8 = vorher. Kuenftige Faelle haben noch kein Synonym. Hier wird jede Wissenszeile (mit Dateititel und Ueberschrift als Kontext) und
jeder Werkzeugkopf als Vektor abgelegt; die Anfrage wird eingebettet, Kosinus-Naehe gibt eine zweite Rangliste, die wissen_suchen.py
per Rangfusion (RRF) mit der Wortsuche verbindet.
Modell: intfloat/multilingual-e5-small (MIT, 118 M Parameter, 384 Dim., mehrsprachig; Lizenz geprueft HF-API 24.11.2026). Laeuft NUR
auf CPU (CUDA_VISIBLE_DEVICES leer, nice 19, 4 Threads), damit eine laufende GPU-Kette ungestoert bleibt.
Index: je Projektordner eine Datei unter dem Index-Ordner (Konfig .claude/doku-pflege.json "wissen.bedeutung.index"), je Quelldatei
nach (mtime, Groesse) zwischengespeichert - nur geaenderte Dateien werden neu eingebettet.
Verwandt/Vorlaeufer: tools/wissen_suchen.py (Wortsuche, ruft dies per Unterprozess auf), tools/werkzeug_aehnlich.py (TF-IDF ueber
Werkzeugkoepfe), tools/wissen_wiederfinden.py (Nachweis Recall@5).

Aufruf (meist nur ueber wissen_suchen.py):
  <python mit torch+transformers> -I tools/wissen_bedeutung.py --wurzel DIR --anfrage "TEXT" [--top 300] [--memory DIR]
  ... --bauen            Index vollstaendig (neu) aufbauen, Ausgabe Fortschritt
Ausgabe (Anfrage): JSON-Liste [{"name", "nr", "gruppe", "wert", "text"}] auf stdout. rc 0 ok, rc 3 Index zu alt (zu viele geaenderte
Zeilen fuer eine Anfrage -> erst --bauen), rc 2 Fehler (Paket/Modell fehlt).
"""
import argparse
import hashlib
import json
import os
import pickle
import re
import sys
import time
from pathlib import Path

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
import wissen_suchen as ws  # noqa: E402

# projektunabhaengig: Modellordner/Index kommen aus .claude/doku-pflege.json "wissen.bedeutung" (rc-park: /media/oem/scan/rc-park_tmp/wissen_index)
STANDARD = {"modell": str(Path.home() / ".cache" / "wissen_bedeutung" / "multilingual-e5-small"),
            "index": str(Path.home() / ".cache" / "wissen_bedeutung"), "max_neu_anfrage": 4000, "max_token": 160}
VERSION = 3          # Aenderung der Einheiten/Kontexte -> alter Index wird verworfen
UEBER_RX = re.compile(r"^\s{0,3}(#{1,6})\s+(.*)")
TRENN_RX = re.compile(r"^\s*\|?\s*:?-{3,}")


def einstellungen(wurzel):
    k = ws.konfig(wurzel)
    e = dict(STANDARD)
    e.update(k.get("bedeutung", {}) or {})
    return e


def einheiten_md(text, titel, fragen=None):
    """[(nr, roh, einzubettender Text)]: jede inhaltliche Zeile mit Kontext 'Dateititel > Ueberschrift: Zeile'."""
    aus, kopf = [], {}
    for nr, z in enumerate(text.split("\n"), 1):
        m = UEBER_RX.match(z)
        if m:
            tiefe = len(m.group(1))
            kopf = {t: v for t, v in kopf.items() if t < tiefe}
            kopf[tiefe] = m.group(2).strip()
        s = z.strip()
        if len(s) < 12 or TRENN_RX.match(s) or len(re.findall(r"[A-Za-zÄÖÜäöüß]{3,}", s)) < 2:
            continue
        kette = [kopf[t] for t in sorted(kopf) if kopf[t] != s.lstrip("# ").strip()][-2:]
        ctx = " > ".join([titel] + kette) if titel not in kette else " > ".join(kette)
        s = re.sub(r"\s*\|\s*", " | ", s)
        aus.append((nr, z, f"{ctx}: {s}"[:900]))
        for fr in (fragen or {}).get(ws.zeilen_hash(z), []):
            aus.append((nr, z, f"{ctx}: {fr}"[:400]))          # Alltagsfrage zur Zeile (doc2query) als eigene Einheit
    return aus


def einheiten_werkzeug(p):
    kopf = ws.werkzeug_kopf(p)
    if not kopf:
        return []
    text = " ".join(z.strip().lstrip("#").strip() for _, z in kopf)
    return [(kopf[0][0], kopf[0][1], f"Werkzeug {p.stem.replace('_', ' ')}: {text}"[:1200])]


def fragen_sig(wurzel, name, kfg):
    q = Path(wurzel) / kfg.get("fragen_ordner", "Doku/projekt/.fragen") / (name.replace("/", "__") + ".jsonl")
    try:
        st = q.stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def alle_dateien(wurzel, memory, kfg):
    """[(gruppe, name, pfad, art)] wie wissen_suchen.suchen (gleiche Namen 'datei' bzw. 'memory/x.md')."""
    aus = []
    for g, ps in ws.quellen(wurzel, memory, kfg).items():
        for p in ps:
            name = "memory/" + p.name if g == "Memory" else str(p.relative_to(wurzel))
            aus.append((g, name, p, "md"))
    for p in ws.werkzeug_dateien(wurzel, kfg):
        aus.append(("Werkzeuge (Kopf)", str(p.relative_to(wurzel)), p, "py"))
    return aus


class Einbetter:
    def __init__(self, modell, max_token, pooling="mittel"):
        import torch
        from transformers import AutoModel, AutoTokenizer
        torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "4")))
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(modell)
        self.m = AutoModel.from_pretrained(modell).eval()
        self.max_token = max_token
        self.pooling = pooling

    def __call__(self, texte, prefix, stapel=64):
        import numpy as np
        torch = self.torch
        aus = []
        # nach Laenge sortiert stapeln (weniger Auffuellung), danach zurueck in die Reihenfolge
        reihe = sorted(range(len(texte)), key=lambda i: len(texte[i]))
        vek = [None] * len(texte)
        with torch.inference_mode():
            for a in range(0, len(reihe), stapel):
                idx = reihe[a:a + stapel]
                b = self.tok([prefix + texte[i] for i in idx], padding=True, truncation=True, max_length=self.max_token,
                             return_tensors="pt")
                h = self.m(**b).last_hidden_state
                if self.pooling == "cls":
                    e = h[:, 0]
                else:
                    mask = b["attention_mask"].unsqueeze(-1).to(h.dtype)
                    e = (h * mask).sum(1) / mask.sum(1).clamp(min=1)
                e = torch.nn.functional.normalize(e, dim=-1)
                for j, i in enumerate(idx):
                    vek[i] = e[j].numpy().astype(np.float16)
        aus = np.stack(vek) if vek else np.zeros((0, 384), dtype=np.float16)
        return aus


def modell_art(e):
    """(pooling, prefix_anfrage, prefix_passage) je Modellfamilie; Konfig 'pooling'/'prefix_anfrage'/'prefix_passage' ueberschreibt."""
    n = Path(e["modell"]).name.lower()
    std = ("cls", "", "") if "bge" in n else ("mittel", "query: ", "passage: ") if "e5" in n else ("mittel", "", "")
    return e.get("pooling", std[0]), e.get("prefix_anfrage", std[1]), e.get("prefix_passage", std[2])


def neuer_einbetter(e):
    return Einbetter(e["modell"], int(e.get("max_token", 160)), modell_art(e)[0])


def index_pfad(e, wurzel):
    h = hashlib.sha1(str(Path(wurzel).resolve()).encode()).hexdigest()[:12]
    return Path(e["index"]) / f"index_{Path(wurzel).resolve().name}_{h}_{Path(e['modell']).name}.pkl"


def lade_index(pfad, modell):  # noqa: C901
    try:
        with open(pfad, "rb") as f:
            d = pickle.load(f)
        if d.get("version") == VERSION and d.get("modell") == str(modell):
            return d
    except (OSError, ValueError, EOFError, pickle.UnpicklingError, AttributeError):
        pass
    return {"version": VERSION, "modell": str(modell), "dateien": {}}


def speichere_index(pfad, d):
    pfad.parent.mkdir(parents=True, exist_ok=True)
    tmp = pfad.with_suffix(f".tmp{os.getpid()}")
    with open(tmp, "wb") as f:
        pickle.dump(d, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, pfad)


def aktualisieren(wurzel, memory, e, max_neu=None, laut=False, einbetter=None):
    """Index auf Stand bringen. Gibt (index, einbetter) zurueck; None, wenn mehr als max_neu Einheiten neu waeren."""
    kfg = ws.konfig(wurzel)
    pfad = index_pfad(e, wurzel)
    d = lade_index(pfad, e["modell"])
    dateien = alle_dateien(Path(wurzel), memory, kfg)
    offen = []
    for g, name, p, art in dateien:
        try:
            st = p.stat()
        except OSError:
            continue
        fs = fragen_sig(wurzel, name, kfg) if art == "md" else None
        sig = (st.st_mtime_ns, st.st_size) if fs is None else (st.st_mtime_ns, st.st_size, fs)
        alt = d["dateien"].get(str(p.resolve()))
        if alt and alt["sig"] == sig and alt["name"] == name and alt["gruppe"] == g:
            continue
        offen.append((g, name, p, art, sig))
    lebend = {str(p.resolve()) for _, _, p, _ in dateien}
    weg = [k for k in d["dateien"] if k not in lebend]
    for k in weg:
        del d["dateien"][k]
    if not offen:
        if weg:
            speichere_index(pfad, d)
        return d, einbetter
    neu = []
    for g, name, p, art, sig in offen:
        try:
            if art == "md":
                text = p.read_text(encoding="utf-8", errors="replace")
                m = re.search(r"^\s{0,3}#\s+(.+)$", text, re.M)
                titel = (m.group(1).strip() if m else p.stem.replace("_", " "))[:120]
                eh = einheiten_md(text, titel, ws.alltagsfragen(wurzel, name, kfg) if g != "Memory" else None)
            else:
                eh = einheiten_werkzeug(p)
        except OSError:
            continue
        neu.append((g, name, p, sig, eh))
    n_neu = sum(len(x[4]) for x in neu)
    if max_neu is not None and n_neu > max_neu:
        return None, einbetter
    if einbetter is None:
        einbetter = neuer_einbetter(e)
    t0 = time.time()
    fertig = 0
    for g, name, p, sig, eh in neu:
        vek = einbetter([x[2] for x in eh], modell_art(e)[2]) if eh else None
        d["dateien"][str(p.resolve())] = {"sig": sig, "name": name, "gruppe": g, "nr": [x[0] for x in eh],
                                          "roh": [x[1] for x in eh], "vek": vek}
        fertig += len(eh)
        if laut:
            print(f"  {fertig}/{n_neu} Einheiten, {time.time() - t0:.0f} s - {name}", file=sys.stderr)
        if laut and fertig and fertig % 2000 < len(eh):
            speichere_index(pfad, d)                 # Zwischenstand
    speichere_index(pfad, d)
    return d, einbetter


def anfrage(wurzel, text, memory=None, top=300, e=None):
    import numpy as np
    e = e or einstellungen(wurzel)
    d, emb = aktualisieren(wurzel, memory, e, max_neu=int(e.get("max_neu_anfrage", 4000)))
    if d is None:
        return None
    if emb is None:
        emb = neuer_einbetter(e)
    q = emb([text], modell_art(e)[1])[0].astype(np.float32)
    zeilen, mats = [], []
    for k, x in d["dateien"].items():
        if x["vek"] is None or not len(x["nr"]):
            continue
        if x["gruppe"] == "Memory" and memory is None:
            continue
        mats.append(x["vek"])
        zeilen += [(x["name"], nr, x["gruppe"], roh) for nr, roh in zip(x["nr"], x["roh"])]
    if not mats:
        return []
    M = np.concatenate(mats).astype(np.float32)
    s = M @ q
    best = np.argsort(-s)[:top]
    return [{"name": zeilen[i][0], "nr": zeilen[i][1], "gruppe": zeilen[i][2], "wert": round(float(s[i]), 4),
             "text": zeilen[i][3]} for i in best]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--wurzel", default=None)
    ap.add_argument("--anfrage", default=None)
    ap.add_argument("--top", type=int, default=300)
    ap.add_argument("--memory", default=None)
    ap.add_argument("--bauen", action="store_true")
    a = ap.parse_args(argv)
    try:
        os.nice(19)
    except OSError:
        pass
    w = Path(a.wurzel) if a.wurzel else ws.standard_wurzel()
    mem = Path(a.memory) if a.memory else None
    e = einstellungen(w)
    try:
        if a.bauen:
            d, _ = aktualisieren(w, mem, e, laut=True)
            n = sum(len(x["nr"]) for x in d["dateien"].values())
            print(f"Index {index_pfad(e, w)}: {len(d['dateien'])} Dateien, {n} Einheiten")
            return 0
        if not a.anfrage:
            print("FEHLER: --anfrage oder --bauen", file=sys.stderr)
            return 2
        r = anfrage(w, a.anfrage, mem, a.top, e)
    except (ImportError, OSError, ValueError, RuntimeError) as ex:
        print(f"FEHLER Bedeutungssuche: {type(ex).__name__}: {ex}", file=sys.stderr)
        return 2
    if r is None:
        print("Index zu alt fuer eine Anfrage - erst: --bauen", file=sys.stderr)
        return 3
    json.dump(r, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
