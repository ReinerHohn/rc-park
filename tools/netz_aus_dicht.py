#!/usr/bin/env python3
"""netz_aus_dicht.py <objekt.json> <dicht-ordner> [--aus ORDNER] [--radius 60] - OpenMVS-Netz aus dem COLMAP-Dichtordner, im MODELLRAHMEN ausgeschnitten.

Am 15.11.2026 von Hand gelaufen (Schwabentor), jetzt Kettenschritt: InterfaceCOLMAP + ReconstructMesh (Standardeinstellung - laut Versuchsregister BR schlaegt
sie RefineMesh, Poisson, TSDF, 3DGS/2DGS; CPU, ~1 + 2 min bei 387 Bildern), dann X_m = R^T (X - t) / s mit messprotokoll/SFM-AUSRICHTUNG-<objekt>.json und
Ausschnitt im Radius um den Rahmenursprung -> <aus>/mesh_modell_ausschnitt.npz (V float32, F int32) fuer tools/fassaden_kette.py / relief_einsatz.py.
Vorhandenes mesh.ply wird wiederverwendet (--neu erzwingt Neulauf). Braucht ~5 GB auf der Datenplatte (scene.mvs + Tiefenkarten-Kopie); nach dem Lauf duerfen scene*.mvs/*.dmap geloescht werden.
"""
import sys, os, json, argparse, subprocess, numpy as np
BIN = "/media/oem/scan/openmvs-build/bin/bin/OpenMVS"


def main():
    import trimesh
    from scipy.spatial.transform import Rotation as Rot
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("dicht"); ap.add_argument("--aus"); ap.add_argument("--radius", type=float, default=60.0); ap.add_argument("--neu", action="store_true"); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); name = os.path.basename(od); D = os.path.abspath(a.dicht); A = os.path.abspath(a.aus or os.path.join(os.path.dirname(D), "openmvs")); os.makedirs(A, exist_ok=True)
    if not A.startswith("/media/oem/scan/"): print("ABBRUCH: Ausgabeordner muss auf der Datenplatte /media/oem/scan liegen (InterfaceCOLMAP schreibt ~5 GB; 15.11.2026 lief ein Test so die Root-Platte voll)"); return 1
    mesh = os.path.join(A, "mesh.ply"); scene = os.path.join(A, "scene.mvs")
    if a.neu or not os.path.exists(mesh):
        for cmd in ([os.path.join(BIN, "InterfaceCOLMAP"), "-w", A, "-i", D, "-o", scene, "--image-folder", os.path.join(D, "images")], [os.path.join(BIN, "ReconstructMesh"), "-w", A, "-i", scene, "-o", mesh]):
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode: print("FEHLER", os.path.basename(cmd[0]), (r.stdout + r.stderr)[-400:]); return 1
    T = json.load(open(os.path.join(od, "messprotokoll", f"SFM-AUSRICHTUNG-{name}.json")))["transformation"]; s = T["s"]; R = Rot.from_rotvec(T["rvec"]).as_matrix(); t = np.array(T["t"])
    m = trimesh.load(mesh, process=False); V = ((np.asarray(m.vertices, np.float64) - t) / s) @ R; F = np.asarray(m.faces)
    drin = np.linalg.norm(V[:, :2], axis=1) < a.radius; F = F[drin[F].all(1)]; idx = np.unique(F); neu = np.full(len(V), -1); neu[idx] = np.arange(len(idx))
    aus = os.path.join(A, "mesh_modell_ausschnitt.npz"); np.savez(aus, V=V[idx].astype(np.float32), F=neu[F].astype(np.int32))
    print(f"-> {aus}: {len(idx)} Ecken, {len(F)} Flaechen im Radius {a.radius:.0f} m (Netz gesamt {len(V)} Ecken)"); return 0


if __name__ == "__main__":
    sys.exit(main())
