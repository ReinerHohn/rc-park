#!/usr/bin/env python3
"""p1s_print.py — Bambu P1S im LAN steuern: Status / Upload+Druckstart (ohne Cloud).

  python3 tools/p1s_print.py status
  python3 tools/p1s_print.py print <datei.gcode.3mf> [subtask_name]
"""
import sys, json, ssl, ftplib, time
import paho.mqtt.client as mqtt

IP = "192.168.178.125"; CODE = "1e027750"; SN = "01P00C651601962"


class _FTPI(ftplib.FTP_TLS):
    """Implicit-TLS FTPS (Bambu Port 990)."""
    @property
    def sock(self): return self._sock
    @sock.setter
    def sock(self, v):
        if v is not None and not isinstance(v, ssl.SSLSocket):
            v = self.context.wrap_socket(v)
        self._sock = v


def upload(path, remote):
    f = _FTPI(context=ssl._create_unverified_context())
    f.connect(IP, 990, timeout=40); f.login("bblp", CODE); f.prot_p()
    with open(path, "rb") as fp:
        f.storbinary("STOR " + remote, fp, blocksize=524288)
    sz = None
    try: sz = f.size(remote)
    except Exception: pass
    f.quit(); return sz


def _mqtt(on_msg=None):
    cl = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="claude-p1s")
    cl.username_pw_set("bblp", CODE)
    cl.tls_set(cert_reqs=ssl.CERT_NONE); cl.tls_insecure_set(True)
    if on_msg: cl.on_message = on_msg
    cl.connect(IP, 8883, 60); cl.subscribe(f"device/{SN}/report"); cl.loop_start()
    return cl


def status():
    got = {}
    def on_msg(c, u, m):
        try:
            d = json.loads(m.payload)
            if "print" in d: got.update(d["print"])
        except Exception: pass
    cl = _mqtt(on_msg)
    cl.publish(f"device/{SN}/request", json.dumps({"pushing": {"sequence_id": "0", "command": "pushall"}}))
    time.sleep(6); cl.loop_stop(); cl.disconnect()
    print("gcode_state:", got.get("gcode_state"))
    print("nozzle_diameter:", got.get("nozzle_diameter"))
    print("nozzle_temper:", got.get("nozzle_temper"), " bed_temper:", got.get("bed_temper"))
    print("mc_percent:", got.get("mc_percent"), " mc_remaining_time:", got.get("mc_remaining_time"))
    print("subtask_name:", got.get("subtask_name"))
    return got


def do_print(path, name):
    remote = name + ".3mf"
    print("Upload …"); sz = upload(path, remote); print("hochgeladen:", remote, sz, "bytes")
    acks = []
    def on_msg(c, u, m):
        try: acks.append(json.loads(m.payload))
        except Exception: pass
    cl = _mqtt(on_msg)
    # funktionierender Befehl (BRAUCHT Developer Mode am Drucker, sonst still ignoriert!)
    cmd = {"print": {"sequence_id": "1", "command": "project_file",
                     "param": "Metadata/plate_1.gcode", "subtask_name": name,
                     "url": f"file:///sdcard/{remote}", "bed_type": "textured_plate",
                     "timelapse": False, "bed_leveling": True, "flow_cali": False,
                     "vibration_cali": True, "layer_inspect": False, "use_ams": False}}
    cl.publish(f"device/{SN}/request", json.dumps(cmd))
    time.sleep(8); cl.loop_stop(); cl.disconnect()
    for a in acks[-5:]:
        p = a.get("print", {})
        if "gcode_state" in p or "result" in p or "reason" in p:
            print("ACK:", {k: p.get(k) for k in ("gcode_state", "result", "reason", "mc_percent")})


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "status":
        status()
    elif sys.argv[1] == "print":
        do_print(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "haut")
