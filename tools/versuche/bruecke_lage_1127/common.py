import pycolmap, numpy as np, json, sys
sys.path.insert(0,'/media/oem/scan/rc-park_tmp/lage_bruecke/tools')
from scipy.spatial.transform import Rotation as Ro
D='/media/oem/rcdaten/rc-park_daten_neu/zusatz_20261126_voll/lg'
A=json.load(open('/home/oem/git/rc-park/modelle/schwabentor-1122/messprotokoll/SFM-AUSRICHTUNG-schwabentor-1122.json'))['transformation']
sA=A['s']; RA=Ro.from_rotvec(A['rvec']).as_matrix(); tA=np.array(A['t'])
def sfm2m(X): return (np.asarray(X)-tA)@RA/sA      # X_modell = R^T (X_sfm-t)/s
ZUP_SFM=RA[:,2]   # Modell-z in SfM
def lade():
    HH=pycolmap.Reconstruction(D+'/sparse_handy/0'); T=pycolmap.Reconstruction(D+'/teilmodell/0'); return HH,T
def zentren(M): return {i.name:np.array(i.projection_center()) for i in M.images.values() if i.has_pose}
def rots(M): return {i.name:np.array(i.cam_from_world().rotation.matrix()) for i in M.images.values() if i.has_pose}
