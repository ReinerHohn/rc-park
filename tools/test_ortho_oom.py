#!/usr/bin/env python3
"""test_ortho_oom.py - GPU-Speichermangel in fassade_ortho: Block halbieren statt CPU-Rueckfall (24.11.2026, Befund 1122x "OOM nach 294 Paaren").

Ohne Karte (reine Logik): mit_blockhalbierung halbiert nur bei Speichermangel, raeumt vorher auf, behaelt den kleinen Block, reicht andere Fehler und
Speichermangel unter der Mindestgroesse weiter; gpu_budget_mb liest RCPARK_GPU_MB. Der Ende-zu-Ende-Vergleich (RCPARK_TEST_OOM_AB, bitgleiche Bilder
GPU normal gegen GPU mit erzwungener Halbierung) steht in tools/schnelltest.sh beim Fassadenbild ober_tvdr f02.
  /media/oem/scan/venv-seg/bin/python -I tools/test_ortho_oom.py   -> rc 0 = alles gut
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fassade_ortho as FO


class OutOfMemoryError(RuntimeError): pass        # gleicher Name wie torch.OutOfMemoryError: ist_oom prueft den Typnamen


def main():
    fehler = []
    def pruef(ok, text): print(("OK   " if ok else "FEHL ") + text); ok or fehler.append(text)

    # 1) Halbieren bis es passt, Ergebnis = Summe in Bloecken (blockunabhaengig), Aufraeumen je Halbierung
    daten = list(range(100000)); aufr = []; z = dict(block=1500000)
    def rechnen(B):
        if B > 20000: raise OutOfMemoryError("CUDA out of memory. Tried to allocate 70.00 MiB")
        return sum(sum(daten[s:s + B]) for s in range(0, len(daten), B))
    r = FO.mit_blockhalbierung(rechnen, z, lambda: aufr.append(1), melde=lambda *a, **k: None)
    pruef(r == sum(daten), f"Ergebnis nach Halbierung gleich ({r})")
    pruef(z["block"] == 11718 and z["halbiert"] == 7 and len(aufr) == 7, f"Block 1500000 -> {z['block']} ({z.get('halbiert')}x halbiert, {len(aufr)}x aufgeraeumt)")
    r2 = FO.mit_blockhalbierung(rechnen, z, lambda: aufr.append(1), melde=lambda *a, **k: None)
    pruef(r2 == r and z["halbiert"] == 7, "kleiner Block bleibt fuer spaetere Aufrufe (keine neue Halbierung)")

    # 2) andere Fehler nicht abfangen
    z = dict(block=1500000)
    def kaputt(B): raise ValueError("kein Speicherfehler")
    try: FO.mit_blockhalbierung(kaputt, z, lambda: None, melde=lambda *a, **k: None); pruef(False, "ValueError weitergereicht")
    except ValueError: pruef(z["block"] == 1500000, "ValueError weitergereicht, Block unveraendert")

    # 3) Speichermangel auch bei kleinstem Block -> weiterreichen (dann CPU-Rest in fassade_ortho)
    z = dict(block=1500000)
    def immer(B): raise RuntimeError("CUDA error: out of memory")
    try: FO.mit_blockhalbierung(immer, z, lambda: None, melde=lambda *a, **k: None); pruef(False, "OOM unter Mindestblock weitergereicht")
    except RuntimeError: pruef(z["block"] >= FO.GPU_BLOCK_MIN and z["block"] // 2 < FO.GPU_BLOCK_MIN, f"OOM unter Mindestblock weitergereicht (Block {z['block']})")

    # 4) Budget aus der Job-Buchung
    pruef(FO.gpu_budget_mb({}) == 2600.0, "ohne Buchung 2600 MiB (alter Standard)")
    pruef(FO.gpu_budget_mb({"RCPARK_GPU_MB": "3500"}) == 3200.0, "RCPARK_GPU_MB 3500 -> 3200 MiB (minus Grundlast)")
    pruef(FO.gpu_budget_mb({"RCPARK_GPU_MB": "800"}) == 1000.0, "kleine Buchung -> mindestens 1000 MiB")
    pruef(FO.gpu_budget_mb({"RCPARK_GPU_MB": "0"}) == 2600.0, "Buchung 0 = keine Buchung")

    print(f"{'ALLES GUT' if not fehler else f'{len(fehler)} FEHLER'}"); return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
