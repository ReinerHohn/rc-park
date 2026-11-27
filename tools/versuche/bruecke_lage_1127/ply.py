import numpy as np
def lies(p, max_n=None):
    f=open(p,'rb'); h=b''
    while not h.endswith(b'end_header\n'): h+=f.readline()
    n=int([l for l in h.split(b'\n') if l.startswith(b'element vertex')][0].split()[-1])
    dt=np.dtype([('x','<f4'),('y','<f4'),('z','<f4'),('nx','<f4'),('ny','<f4'),('nz','<f4'),('r','u1'),('g','u1'),('b','u1')])
    a=np.fromfile(f,dtype=dt,count=n)
    return np.stack([a['x'],a['y'],a['z']],1).astype(np.float64), np.stack([a['r'],a['g'],a['b']],1)
