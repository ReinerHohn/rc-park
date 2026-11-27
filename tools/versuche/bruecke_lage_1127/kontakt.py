import cv2, numpy as np, sys, os, json
B='/media/oem/rcdaten/rc-park_daten_neu/zusatz_20261126_voll/lg/bilder'
names=sys.argv[2].split(',') if len(sys.argv)>2 else None
if names is None:
    al=sorted(os.listdir(B)); names=al[::max(1,len(al)//60)][:60]
th=[]
for n in names:
    im=cv2.imread(os.path.join(B,n)); h,w=im.shape[:2]; s=240/w; im=cv2.resize(im,(240,int(h*s)))
    im=cv2.resize(im,(240,180)) ; cv2.putText(im,n[9:21],(3,15),0,.45,(0,255,255),1); th.append(im)
while len(th)%10: th.append(np.zeros_like(th[0]))
rows=[np.hstack(th[i:i+10]) for i in range(0,len(th),10)]; cv2.imwrite(sys.argv[1],np.vstack(rows),[cv2.IMWRITE_JPEG_QUALITY,80])
