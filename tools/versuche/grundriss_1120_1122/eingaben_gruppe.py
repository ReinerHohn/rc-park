import os
def gruppe(n):
    if n.startswith("eigen__vf_") or n.startswith("eigen__IMG_") or n.startswith("eigen__"):
        if "__vf_" in n: return "eigen_video"
        if "IMG_2026" in n: return "eigen_IMG_2026"
        return "eigen_sonst"
    if n.startswith("video_frames_"): return "video:" + n.split("__")[0][len("video_frames_"):]
    if n.startswith("netz_"): return n.split("__")[0]
    return n.split("__")[0]

