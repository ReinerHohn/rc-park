import pycolmap, os, time
S=os.path.dirname(os.path.abspath(__file__))
bilder=S+"/bilder"; db=S+"/db.db"; aus=S+"/sparse"
os.makedirs(aus, exist_ok=True)
if os.path.exists(db): os.remove(db)
t0=time.time()
pycolmap.extract_features(db, bilder, camera_mode=pycolmap.CameraMode.PER_IMAGE)
print(f"Merkmale {time.time()-t0:.0f} s", flush=True)
t0=time.time(); pycolmap.match_exhaustive(db); print(f"Zuordnung {time.time()-t0:.0f} s", flush=True)
t0=time.time(); karten=pycolmap.incremental_mapping(db, bilder, aus)
print(f"Aufbau {time.time()-t0:.0f} s, {len(karten)} Teilmodell(e)", flush=True)
for i,k in karten.items():
    print(f"  Modell {i}: {k.num_reg_images()} von 37 Fotos registriert, {k.num_points3D()} Punkte", flush=True)
