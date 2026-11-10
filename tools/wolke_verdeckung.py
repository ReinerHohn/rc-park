#!/usr/bin/env python3
"""wolke_verdeckung.py - FOTOWOLKEN-VERDECKUNG fuer die Sichtbarkeitspruefung (teil_fotoform, L-KR26, Nutzer 10.11. abends).

Warum: teil_fotoform rastert jedes Teil und vergleicht mit der Tiefe des GANZEN MODELLS. Fehlt im Modell ein Verdecker (Laubendecke, Baum, Geruest,
Nachbarbau), gilt ein Teil als sichtbar, obwohl es im Foto verdeckt ist -> Staffelgiebel Ost wurde an Fotos benotet, die UNTER der Laube aufs Gewoelbe sehen.
Hier: die Fotowolke (im Kamerarahmen) wird je Foto per GPU-Z-Puffer in die Kamera projiziert (Zellen-Minimum mit Stuetzung); ein Teilpixel ist
VERDECKT, wenn die Wolkentiefe dort deutlich kleiner ist als die Teiltiefe. Wo keine (gestuetzte) Wolke ist: wie bisher (nur Modelltiefe).

Duenne Wolke (SfM sieht glatten weissen Putz/Gewoelbe kaum: dort nur die Rippen): die Frontzellen werden je Teil per Schliessen (Dilatation/Erosion
auf dem Zellraster, GPU max_pool) zusammengezogen, damit Luecken ZWISCHEN verdeckenden Wolkenpunkten (Gewoelbekappen zwischen den Rippen) mitzaehlen.
POSITIVBEWEIS schlaegt Schliessen: Zellen, in denen die Wolke in Teiltiefe (+-Schwelle) liegt, werden nie als verdeckt gefuellt.
Rauschschutz: (1) Zelle gilt nur mit >= nmin Wolkenpunkten innerhalb `schicht` m hinter dem Zellenminimum (Einzelpunkte werden entfernt, Minimum neu);
(2) Verdeckung erst bei Tiefenunterschied > max(abs_m, rel x Teiltiefe).
GRENZE (ehrlich): glatte Verdecker ohne jeden Wolkenpunkt, weit weg von Rippen/Kanten, bleiben unsichtbar (Quellen-Blindheit der Fotowolke).
ANNAHME: Wolke und Kameras im selben Rahmen (kam_lot2 / j_voll_lot2; bei K-Dateien ohne 'rahmen_verschiebung' wird die Verdeckung nicht benutzt).
"""
import numpy as np, torch

METRIK = "v2_wolkenverdeckung"      # in die Ausgabe-JSON (Cache-Schluessel!); ohne Wolkenverdeckung: "v1"
METRIK_AUS = "v1"


class Verdecker:
    def __init__(self, P, dev="cuda"):
        self.dev = dev; self.P = torch.as_tensor(np.ascontiguousarray(np.asarray(P, np.float32)[:, :3]), device=dev)

    def zkarte(self, R, t, f, cx, cy, W, H, zelle=12, nmin=2, schicht=0.6, runden=2):
        """Zellraster (ch,cw) torch(GPU) float32: gestuetzte Wolken-Frontsichttiefe je Zelle (inf = keine Wolke). Z-Puffer je Zelle (zelle x zelle Pixel)."""
        dev = self.dev; Rg = torch.as_tensor(np.asarray(R, np.float32), device=dev); tg = torch.as_tensor(np.asarray(t, np.float32).ravel(), device=dev)
        X = self.P @ Rg.T + tg; z = X[:, 2]
        u = torch.floor(f * X[:, 0] / z + cx).long(); v = torch.floor(f * X[:, 1] / z + cy).long()
        ok = (z > 1) & (u >= 0) & (u < W) & (v >= 0) & (v < H)
        zz = z[ok]; cw, ch = (W + zelle - 1) // zelle, (H + zelle - 1) // zelle
        cell = (v[ok] // zelle) * cw + (u[ok] // zelle); del X, z, u, v, ok
        akt = torch.ones(len(zz), dtype=torch.bool, device=dev)
        for r_ in range(runden + 1):                   # letzte Runde: nur noch Minimum + Stuetzung bestimmen
            zmin = torch.full((cw * ch,), float("inf"), device=dev)
            zmin.scatter_reduce_(0, cell[akt], zz[akt], reduce="amin")
            vorn = akt & (zz <= zmin[cell] + schicht)
            cnt = torch.zeros(cw * ch, device=dev).index_add_(0, cell[vorn], torch.ones(int(vorn.sum()), device=dev))
            if r_ < runden: akt = akt & ~(vorn & (cnt[cell] < nmin))   # duenn gestuetzte Frontpunkte (Schweb-/Einzelpunkte) verwerfen, Minimum neu
        zmin = torch.where(cnt >= nmin, zmin, torch.full_like(zmin, float("inf")))
        return zmin.reshape(ch, cw)

    @staticmethod
    def _dil(m, k):   # m bool (h,w) torch -> Dilatation mit Quadrat Radius k (Zellen)
        return torch.nn.functional.max_pool2d(m[None, None].float(), 2 * k + 1, 1, k)[0, 0] > 0

    @classmethod
    def verdeckt(cls, zk, dp, zelle=12, abs_m=0.5, rel=0.05, schliess=10, beweis=2):
        """Pixelmaske (numpy bool, H x W): Teilpixel hinter gestuetzter Wolke. zk = zkarte (Zellraster), dp = Teiltiefe je Pixel (numpy, nan ausserhalb)."""
        dev = zk.device; H, W = dp.shape; ch, cw = zk.shape
        dpc = torch.as_tensor(dp, device=dev)[zelle // 2::zelle, zelle // 2::zelle][:ch, :cw]       # Teiltiefe in Zellmitte
        dpc = torch.nn.functional.pad(dpc, (0, cw - dpc.shape[1], 0, ch - dpc.shape[0]), value=float("nan"))
        tol = torch.clamp(rel * dpc, min=abs_m); fin = torch.isfinite(zk) & torch.isfinite(dpc)
        front = fin & (zk < dpc - tol)
        pos = fin & (torch.abs(zk - dpc) <= tol)                                                       # Wolke in Teiltiefe = Sichtbarkeitsbeweis
        if schliess > 0 and front.any():
            closed = ~cls._dil(~cls._dil(front, schliess), schliess)                                 # Schliessen = Dilatation, dann Erosion
            front = front | (closed & ~cls._dil(pos, beweis))                                          # Luecken zwischen Frontzellen fuellen, ausser bei Positivbeweis
        full = front.repeat_interleave(zelle, 0).repeat_interleave(zelle, 1)[:H, :W].cpu().numpy()
        return full & np.isfinite(dp)
