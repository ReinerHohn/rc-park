#!/usr/bin/env python3
"""test_handy_masken_gross.py - 22.11.2026 Nulllauf schwabentor-1122: grosse Bilder (27 MPx) liessen handy_masken bei jeder Breite CUDA-OOM laufen,
weil 150 Klassen-Logits auf VOLLE Bildgroesse hochgerechnet wurden. Prueft (CPU, Attrappe statt Segformer): Ausgabe hat volle Bildgroesse,
die hochgerechnete Logitkarte bleibt <= ~3 MPx, Klassen bleiben an der richtigen Stelle."""
import os, sys, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import torch, handy_masken as HM
groessen = []
_orig = torch.nn.functional.interpolate
def _spy(x, size=None, **kw):
    groessen.append(tuple(size)); return _orig(x, size=size, **kw)
torch.nn.functional.interpolate = _spy
class Attrappe:
    def __call__(self, pixel_values):
        n, _, h, w = pixel_values.shape; lg = torch.zeros(n, 150, h // 4, w // 4)
        lg[:, 3] = 1.0; lg[:, 12, :, : (w // 4) // 2] = 5.0   # linke Haelfte 'person'
        return type("O", (), {"logits": lg})()
fehler = 0
H, W = 5973, 4480
im = np.zeros((H, W, 3), np.uint8)
seg = HM.segmentiere(Attrappe(), np.zeros(3, np.float32), np.ones(3, np.float32), [im], 512, "cpu", False)[0]
if seg.shape != (H, W): print("FEHLER Form", seg.shape); fehler += 1
if max(a * b for a, b in groessen) > 3.2e6: print("FEHLER Logits auf", groessen, "hochgerechnet"); fehler += 1
if not (seg[:, : W // 2 - 50] == 12).all() or not (seg[:, W // 2 + 50:] == 3).all(): print("FEHLER Klassenlage"); fehler += 1
print("OK test_handy_masken_gross" if not fehler else f"{fehler} FEHLER"); sys.exit(1 if fehler else 0)
