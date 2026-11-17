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
    import shutil; ZIEL = A; nb_ = len(os.listdir(os.path.join(D, "images"))) if os.path.isdir(os.path.join(D, "images")) else 0; lokal = f"/media/oem/scan/rc-park_daten/{name}_netzarbeit"
    if not os.path.exists(os.path.join(A, "mesh.ply")) and (not os.path.realpath(A).startswith("/media/oem/scan/") or shutil.disk_usage(A).free / 1e9 < 0.03 * nb_ + 1.5) and shutil.disk_usage("/media/oem/scan").free / 1e9 >= 0.03 * nb_ + 1.5:
        A = lokal; os.makedirs(A, exist_ok=True); print(f"Arbeitsordner {A} (der Ordner neben der dichten Wolke liegt auf einer anderen/vollen Platte: {os.path.realpath(ZIEL)})")      # 17.11.2026: kaufhaus_gk/pipe ist eine Verknuepfung auf die externe Platte (4 GB frei) - dort brach InterfaceCOLMAP mit Schreibfehler ab
    elif os.path.exists(os.path.join(lokal, "mesh.ply")): A = lokal
    mesh = os.path.join(A, "mesh.ply"); scene = os.path.join(A, "scene.mvs"); fused = os.path.join(D, "fused.ply")
    if os.path.exists(mesh) and os.path.exists(fused) and os.path.getmtime(fused) > os.path.getmtime(mesh) and not a.neu:      # 17.11.2026: nach einer NEUEN dichten Wolke wurde das Netz der alten wiederverwendet - mit der neuen Ausrichtung
        print(f"Netz {mesh} ist AELTER als die dichte Wolke {fused} - wird neu gerechnet (vorher: altes Netz im neuen Rahmen = falsch liegende Reliefs, ohne Meldung)"); a.neu = True      # umgerechnet (anderer SfM-Rahmen)
    def raeumen():                                                    # 17.11.2026: die Tiefenkarten-Kopien (depth*.dmap, ~4-5 GB je Objekt) blieben nach Erfolg UND nach Fehlschlag liegen - am Kaufhaus 4,1 GB Rest auf einer Platte mit 7 GB frei
        import glob
        for f_ in glob.glob(os.path.join(A, "depth*.dmap")): os.remove(f_)
    if a.neu or not os.path.exists(mesh):
        frei = shutil.disk_usage(A if os.path.isdir(A) else os.path.dirname(A.rstrip("/"))).free / 1e9; nb = len(os.listdir(os.path.join(D, "images"))) if os.path.isdir(os.path.join(D, "images")) else 0
        if frei < 0.03 * nb + 0.5 + 1.0: print(f"ABBRUCH: {frei:.1f} GB frei auf der Datenplatte, die Netzstufe braucht voruebergehend ~{0.03 * nb + 0.5:.1f} GB (+ 1 GB Reserve; die Tiefenkarten-Kopien werden danach geloescht) - Platz schaffen"); return 3
        for cmd in ([os.path.join(BIN, "InterfaceCOLMAP"), "-w", A, "-i", D, "-o", scene, "--image-folder", os.path.join(D, "images")], [os.path.join(BIN, "ReconstructMesh"), "-w", A, "-i", scene, "-o", mesh]):
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode: print("FEHLER", os.path.basename(cmd[0]), (r.stdout + r.stderr)[-400:]); raeumen(); return 1
        raeumen()
    T = json.load(open(os.path.join(od, "messprotokoll", f"SFM-AUSRICHTUNG-{name}.json")))["transformation"]; s = T["s"]; R = Rot.from_rotvec(T["rvec"]).as_matrix(); t = np.array(T["t"])
    m = trimesh.load(mesh, process=False); V = ((np.asarray(m.vertices, np.float64) - t) / s) @ R; F = np.asarray(m.faces)
    drin = np.linalg.norm(V[:, :2], axis=1) < a.radius; F = F[drin[F].all(1)]; idx = np.unique(F); neu = np.full(len(V), -1); neu[idx] = np.arange(len(idx))
    aus = os.path.join(ZIEL, "mesh_modell_ausschnitt.npz")
    if len(F) < 100:                                                   # 17.11.2026: 0 Flaechen im Radius (Ausrichtung falsch/verschoben, Netz leer) wurden als leere Datei mit rc 0 geschrieben - die Fassadenkette rechnete darauf weiter
        print(f"ABBRUCH: nur {len(F)} Flaechen des Netzes ({len(V)} Ecken) liegen im Radius {a.radius:.0f} m um den Rahmenursprung - Ausrichtung/Netz pruefen; {aus} wird NICHT geschrieben"); return 4
    tmp = os.path.join(ZIEL, f"mesh_modell_ausschnitt.neu{os.getpid()}.npz"); np.savez(tmp, V=V[idx].astype(np.float32), F=neu[F].astype(np.int32)); os.replace(tmp, aus)      # erst fertig schreiben, dann ersetzen
    print(f"-> {aus}: {len(idx)} Ecken, {len(F)} Flaechen im Radius {a.radius:.0f} m (Netz gesamt {len(V)} Ecken)"); return 0


if __name__ == "__main__":
    sys.exit(main())
