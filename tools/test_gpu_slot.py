# Probe gpu_slot: RCPARK_GPU_SLOT_DIR=/tmp/x RCPARK_GPU_SLOTS=2 RCPARK_GPU_FREI_MIB=0; 4x parallel starten -> hoechstens 2 gleichzeitig "laeuft"
import sys, time, os; sys.path.insert(0, "tools"); import gpu_slot
gpu_slot.belegen("probe"); n = len([f for f in os.listdir(gpu_slot.DIR) if f.endswith(".slot")]); print(f"{time.strftime('%T')} pid {os.getpid()} laeuft, belegt {n}", flush=True); time.sleep(4)
