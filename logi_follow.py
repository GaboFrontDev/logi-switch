#!/usr/bin/env python3
"""
logi_follow: el mouse Logitech sigue al teclado entre maquinas.

Corre en cada maquina. Cuando un teclado (por defecto HHKB Hybrid) se CONECTA a
esta maquina, avisa por la red local "el teclado esta conmigo, mi canal de mouse
es N". La maquina que tiene el mouse en ese momento le manda el comando HID++
Change Host (0x1814) para que salte al canal N.

Cada maquina aprende sola su canal: cuando el mouse se conecta aqui, le pregunta
en que canal esta y lo guarda en ~/.logi_follow.json.

Uso:
  python logi_follow.py            # modo agente (dejarlo corriendo)
  python logi_follow.py --info     # muestra teclado, mouse y canales
  python logi_follow.py --switch 2 # cambia el mouse al canal 2 a mano

Requiere:  pip install hidapi
"""

import argparse
import glob
import json
import logging
import os
import re
import socket
import sys
import threading
import time
import uuid

if sys.platform.startswith("linux"):
    try:
        import hidraw as hid   # backend hidraw: necesario para dispositivos Bluetooth
    except ImportError:
        import hid
else:
    import hid

LOGI_VID = 0x046D
FEAT_ROOT = 0x00
FEAT_CHANGE_HOST = 0x1814
SWID = 0x0A
REPORT_LONG = 0x11
DEV_DIRECT = 0xFF  # indice de dispositivo para conexion directa (Bluetooth)

PORT = 47811
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".logi_follow.json")

log = logging.getLogger("logi_follow")


# ------------------------------------------------- lista rapida de HID ------
# hid.enumerate() abre cada dispositivo y pide sus strings (en Windows ~300 ms
# con dispositivos Bluetooth). Para revisar varias veces por segundo solo
# necesitamos ruta + VID + PID, que se obtienen sin abrir nada.

_VIDPID = re.compile(r"vid[_&]([0-9a-f]+)[_&]pid[_&]([0-9a-f]{4})", re.I)


def _list_windows():
    import ctypes
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [("d1", ctypes.c_uint32), ("d2", ctypes.c_uint16),
                    ("d3", ctypes.c_uint16), ("d4", ctypes.c_ubyte * 8)]

    class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("guid", GUID),
                    ("flags", wintypes.DWORD), ("reserved", ctypes.c_void_p)]

    hidlib = ctypes.WinDLL("hid")
    setup = ctypes.WinDLL("setupapi")
    setup.SetupDiGetClassDevsW.restype = ctypes.c_void_p
    setup.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), ctypes.c_wchar_p, ctypes.c_void_p, wintypes.DWORD]
    setup.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID),
                                                  wintypes.DWORD, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
    setup.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
                                                       ctypes.c_void_p, wintypes.DWORD,
                                                       ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    setup.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]

    g = GUID()
    hidlib.HidD_GetHidGuid(ctypes.byref(g))
    hset = setup.SetupDiGetClassDevsW(ctypes.byref(g), None, None, 0x12)  # PRESENT|DEVICEINTERFACE
    out = []
    try:
        i = 0
        while True:
            d = SP_DEVICE_INTERFACE_DATA()
            d.cbSize = ctypes.sizeof(d)
            if not setup.SetupDiEnumDeviceInterfaces(hset, None, ctypes.byref(g), i, ctypes.byref(d)):
                break
            i += 1
            req = wintypes.DWORD()
            setup.SetupDiGetDeviceInterfaceDetailW(hset, ctypes.byref(d), None, 0, ctypes.byref(req), None)
            buf = ctypes.create_string_buffer(req.value)
            ctypes.c_uint32.from_buffer(buf).value = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
            if not setup.SetupDiGetDeviceInterfaceDetailW(hset, ctypes.byref(d), buf, req, None, None):
                continue
            path = ctypes.wstring_at(ctypes.addressof(buf) + 4)
            m = _VIDPID.search(path)
            if m:
                out.append({"path": path.encode(), "vendor_id": int(m.group(1)[-4:], 16),
                            "product_id": int(m.group(2), 16), "usage_page": 0})
    finally:
        setup.SetupDiDestroyDeviceInfoList(hset)
    return out


def _list_linux():
    out = []
    for node in glob.glob("/sys/class/hidraw/hidraw*"):
        try:
            with open(os.path.join(node, "device", "uevent")) as f:
                for line in f:
                    if line.startswith("HID_ID="):
                        _, vid, pid = line.strip().split("=")[1].split(":")
                        out.append({"path": ("/dev/" + os.path.basename(node)).encode(),
                                    "vendor_id": int(vid, 16) & 0xFFFF,
                                    "product_id": int(pid, 16) & 0xFFFF, "usage_page": 0})
        except OSError:
            pass
    return out


def list_hid():
    if sys.platform == "win32":
        return _list_windows()
    if sys.platform.startswith("linux"):
        return _list_linux()
    return hid.enumerate()   # macOS: IOKit no abre los dispositivos, ya es rapido


# ---------------------------------------------------------------- HID++ -----

class HidppError(Exception):
    pass


class Hidpp:
    """Una coleccion HID++ abierta (reportes largos de 20 bytes)."""

    def __init__(self, path):
        self.dev = hid.device()
        self.dev.open_path(path)
        self.path = path

    def close(self):
        try:
            self.dev.close()
        except Exception:
            pass

    def _send(self, feat, func, args=()):
        msg = [REPORT_LONG, DEV_DIRECT, feat, (func << 4) | SWID] + list(args)
        msg += [0] * (20 - len(msg))
        if self.dev.write(msg) < 0:
            raise HidppError("write fallo")
        return msg

    def request(self, feat, func, args=(), timeout=0.6):
        msg = self._send(feat, func, args)
        deadline = time.monotonic() + timeout
        while True:
            left = int((deadline - time.monotonic()) * 1000)
            if left <= 0:
                return None
            r = self.dev.read(64, left)
            if not r or len(r) < 6:
                continue
            if r[2] == 0xFF and r[3] == feat:            # error HID++ 2.0
                raise HidppError("HID++ error 0x%02X" % r[5])
            if r[2] == feat and r[3] == msg[3]:
                return r

    def feature_index(self, feature_id):
        r = self.request(FEAT_ROOT, 0, (feature_id >> 8, feature_id & 0xFF))
        return r[4] if r else None   # None = no contesto; 0 = no tiene esa funcion

    def host_info(self, idx):
        """(numero de canales, canal actual 1-based)"""
        r = self.request(idx, 0)
        if not r:
            raise HidppError("sin respuesta a getHostInfo")
        return r[4], r[5] + 1

    def set_host(self, idx, channel):
        self._send(idx, 1, (channel - 1,))  # el mouse se va; no hay respuesta


def hidpp_candidates(devices):
    """Colecciones vendor-defined de Logitech donde puede hablar HID++."""
    out = []
    for d in devices:
        if d["vendor_id"] != LOGI_VID:
            continue
        up = d.get("usage_page", 0)
        # Windows/macOS reportan usage_page; en Linux (hidraw viejo) puede ser 0
        if up >= 0xFF00 or up == 0:
            out.append(d)
    return out


class Mouse:
    """Encuentra el mouse con Change Host y recuerda su ruta/feature index."""

    def __init__(self, pid_filter=None, known_pid=None):
        self.pid_filter = pid_filter
        self.known_pid = known_pid   # PID del mouse ya encontrado antes (config)
        self.pid = None
        self.path = None
        self.idx = None
        self.bad_paths = set()   # colecciones que no son HID++ / no tienen Change Host
        self.retry_at = {}       # fallas pasajeras: no volver a tocarlas hasta esta hora

    def present_in(self, devices):
        paths = {d["path"] for d in devices}
        if self.path is not None and self.path not in paths:
            log.info("mouse desconectado de esta maquina")
            self.path = self.idx = None
        self.bad_paths &= paths
        self.retry_at = {p: t for p, t in self.retry_at.items() if p in paths}
        return self.path is not None

    def probe(self, devices):
        """Busca el mouse entre las colecciones nuevas. Devuelve True si lo encontro."""
        for d in hidpp_candidates(devices):
            if self.pid_filter and d["product_id"] != self.pid_filter:
                continue
            if d["path"] in self.bad_paths or time.monotonic() < self.retry_at.get(d["path"], 0):
                continue
            pid = d["product_id"]
            # Mouse ya conocido o dispositivo Bluetooth de Logitech (PID 0xBxxx): si falla
            # es casi seguro que se esta conectando -> reintentar pronto, nunca descartar.
            # Lo demas (p. ej. interfaces USB del G502): descartar al primer fallo, para no
            # tocarlo seguido (eso hacia tartamudear la PC).
            likely = pid == self.known_pid or 0xB000 <= pid <= 0xBFFF

            def failed():
                if likely:
                    self.retry_at[d["path"]] = time.monotonic() + 2
                else:
                    self.bad_paths.add(d["path"])

            try:
                h = Hidpp(d["path"])
            except Exception:
                failed()
                continue
            try:
                idx = h.feature_index(FEAT_CHANGE_HOST)
                if idx is None:          # no contesto (puede estar conectandose)
                    failed()
                    continue
                if idx:
                    self.path, self.idx, self.pid = d["path"], idx, pid
                    name = d.get("product_string")
                    if not name:   # la lista rapida no trae el nombre: pedirselo al dispositivo
                        try:
                            name = h.dev.get_product_string()
                        except Exception:
                            name = None
                    self.name = (name or "PID %04X" % d["product_id"]).strip()
                    return True
                self.bad_paths.add(d["path"])   # contesto, pero no tiene Change Host
            except Exception:
                failed()
            finally:
                h.close()
        return False

    def host_info(self):
        h = Hidpp(self.path)
        try:
            return h.host_info(self.idx)
        finally:
            h.close()

    def switch(self, channel):
        h = Hidpp(self.path)
        try:
            h.set_host(self.idx, channel)
        finally:
            h.close()


def keyboard_present(devices, vid, pid):
    return any(d["vendor_id"] == vid and (pid is None or d["product_id"] == pid)
               for d in devices)


# ------------------------------------------------------------- config -------

def load_config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg):
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONFIG_PATH)


# ------------------------------------------------------------ red -----------

def broadcast_targets(peers):
    targets = {"255.255.255.255"}
    try:
        for ip in {a[4][0] for a in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)}:
            if not ip.startswith("127."):
                targets.add(ip.rsplit(".", 1)[0] + ".255")   # asume /24
    except Exception:
        pass
    targets.update(peers)
    return targets


class Net:
    def __init__(self, machine_id, group, peers, on_claim):
        self.machine_id = machine_id
        self.group = group
        self.peers = peers
        self.on_claim = on_claim
        self.seq = int(time.time() * 1000)
        self.seen = {}
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.bind(("", PORT))
        threading.Thread(target=self._listen, daemon=True).start()

    def claim(self, channel):
        self.seq += 1
        msg = json.dumps({"v": 1, "group": self.group, "id": self.machine_id,
                          "host": socket.gethostname(), "seq": self.seq,
                          "channel": channel}).encode()
        targets = broadcast_targets(self.peers)

        def send():
            # UDP no garantiza entrega: mandarlo 3 veces; el receptor ignora duplicados
            for delay in (0, 0.05, 0.15):
                time.sleep(delay)
                for t in targets:
                    try:
                        self.sock.sendto(msg, (t, PORT))
                    except OSError:
                        pass
        threading.Thread(target=send, daemon=True).start()

    def _listen(self):
        while True:
            try:
                data, addr = self.sock.recvfrom(2048)
                m = json.loads(data)
            except Exception:
                continue
            if m.get("v") != 1 or m.get("group") != self.group or m.get("id") == self.machine_id:
                continue
            key = (m["id"], m["seq"])
            if key in self.seen:
                continue
            self.seen[key] = time.monotonic()
            if len(self.seen) > 200:
                self.seen = dict(list(self.seen.items())[-100:])
            log.info("aviso de %s (%s): teclado alla, canal %s", m.get("host"), addr[0], m.get("channel"))
            self.on_claim(int(m["channel"]))


# ------------------------------------------- aviso por tecla (Keychron) -----
# Con el firmware modificado del Keychron, Fn+1/2/3 manda F18/F19/F20 a la PC
# actual justo antes de cambiar de host. No hace falta red: aqui mismo sabemos
# a que canal se va el teclado.

def start_key_listener(kb_map, on_target_channel):
    try:
        from pynput import keyboard
    except ImportError:
        log.error("--keys necesita pynput:  python -m pip install pynput")
        raise SystemExit(1)

    keys = {}
    for host, name in ((1, "f18"), (2, "f19"), (3, "f20")):
        k = getattr(keyboard.Key, name, None)
        if k is not None:
            keys[k] = host
    vks = {0x81: 1, 0x82: 2, 0x83: 3}   # VK_F18..VK_F20 en Windows, por si Key no los define

    def on_press(key):
        host = keys.get(key)
        if host is None:
            host = vks.get(getattr(key, "vk", None)) if sys.platform == "win32" else None
        if host is None:
            return
        channel = kb_map.get(host, host)
        log.info("teclado se va al host %d -> mouse al canal %d", host, channel)
        on_target_channel(channel)

    try:
        listener = keyboard.Listener(on_press=on_press, daemon=True)
        listener.start()
    except Exception as e:
        log.error("no pude escuchar el teclado: %s", e)
        return
    log.info("escuchando F18/F19/F20 del teclado (mapa host->canal: %s)",
             {h: kb_map.get(h, h) for h in (1, 2, 3)})
    if sys.platform == "darwin":
        listener.wait()
        if not getattr(listener, "IS_TRUSTED", True):
            log.error("macOS NO le dio permiso a la app para oir el teclado: activala en Ajustes > "
                      "Privacidad y seguridad > Accesibilidad y Monitoreo de entrada, y reinicia la app")


# ------------------------------------- pedirle al teclado que cambie de host -----
# Por Bluetooth lo unico que la PC le manda al teclado es el estado de las luces.
# El firmware follow del Keychron cuenta cambios rapidos de Bloq Despl / Bloq Mayus:
# 4 = host 1, 6 = host 2, 8 = host 3. Siempre un numero par: la luz queda igual.

LED_STEP = 0.08   # segundos entre cambios (el firmware acepta hasta 0.25)


def _toggles_for(host):
    return 2 * (host + 1)


def _blink_windows(n):
    import ctypes
    VK_SCROLL, KEYUP = 0x91, 0x0002
    user32 = ctypes.windll.user32
    for _ in range(n):
        user32.keybd_event(VK_SCROLL, 0x46, 0, 0)
        user32.keybd_event(VK_SCROLL, 0x46, KEYUP, 0)
        time.sleep(LED_STEP)


def _blink_mac(n):
    # macOS ignora Bloq Despl: se usa Bloq Mayus via IOKit (IOHIDSetModifierLockState)
    import ctypes
    import ctypes.util
    iokit = ctypes.cdll.LoadLibrary(ctypes.util.find_library("IOKit"))
    libc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("System"))
    iokit.IOServiceMatching.restype = ctypes.c_void_p
    iokit.IOServiceGetMatchingService.restype = ctypes.c_uint
    iokit.IOServiceGetMatchingService.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    service = iokit.IOServiceGetMatchingService(0, iokit.IOServiceMatching(b"IOHIDSystem"))
    if not service:
        raise OSError("IOHIDSystem no encontrado")
    task = ctypes.c_uint.in_dll(libc, "mach_task_self_").value
    conn = ctypes.c_uint()
    if iokit.IOServiceOpen(service, task, 1, ctypes.byref(conn)) != 0:   # kIOHIDParamConnectType
        raise OSError("IOServiceOpen fallo")
    try:
        state = ctypes.c_bool()
        iokit.IOHIDGetModifierLockState(conn, 1, ctypes.byref(state))    # kIOHIDCapsLockState
        cur = state.value
        for _ in range(n):
            cur = not cur
            iokit.IOHIDSetModifierLockState(conn, 1, cur)
            time.sleep(LED_STEP)
    finally:
        iokit.IOServiceClose(conn)


def send_keyboard_host(host):
    """Pide al teclado (firmware follow) que se vaya al host 1-3. True si se mando."""
    if host not in (1, 2, 3):
        return False
    n = _toggles_for(host)
    try:
        if sys.platform == "win32":
            _blink_windows(n)
        elif sys.platform == "darwin":
            _blink_mac(n)
        else:
            log.info("pedir cambio al teclado aun no esta hecho en Linux")
            return False
        log.info("teclado -> host %d (%d cambios de luz)", host, n)
        return True
    except Exception as e:
        log.warning("no pude mandar el cambio al teclado: %s", e)
        return False


def parse_kb_map(s):
    """'1:2,2:1,3:3' -> {1: 2, 2: 1, 3: 3} (host del teclado -> canal del mouse)"""
    out = {}
    for part in s.split(","):
        if part.strip():
            a, b = part.split(":")
            out[int(a)] = int(b)
    return out


# ------------------------------------------------------------ agente --------

class Agent:
    """Detecta el mouse/teclado, aprende el canal de esta maquina y reacciona
    a los avisos (red o teclas F18-F20). La UI lo usa por dentro."""

    def __init__(self, args, on_state=None):
        self.args = args
        self.on_state = on_state or (lambda state: None)
        self.cfg = load_config()
        self.cfg.setdefault("machine_id", uuid.uuid4().hex)
        save_config(self.cfg)
        self.mouse = Mouse(args.mouse_pid, known_pid=self.cfg.get("mouse_pid"))
        self.count = None
        self.lock = threading.Lock()
        self._last_state = None

        self.net = Net(self.cfg["machine_id"], args.group, args.peer, self.on_claim)
        if args.keys:
            start_key_listener(args.kb_map, self.on_claim)
        log.info("escuchando en UDP %d; teclado %04X:%s; canal de mouse guardado: %s",
                 PORT, args.kb_vid, "%04X" % args.kb_pid if args.kb_pid else "*",
                 self.cfg.get("mouse_channel", "desconocido"))

    def state(self):
        here = self.mouse.path is not None
        return {"here": here, "channel": self.cfg.get("mouse_channel"),
                "count": self.count or 3, "name": getattr(self.mouse, "name", None),
                "names": self.cfg.get("names", {})}

    def _publish(self):
        st = self.state()
        if st != self._last_state:
            self._last_state = st
            self.on_state(st)

    def set_name(self, channel, name):
        self.cfg.setdefault("names", {})[str(channel)] = name
        save_config(self.cfg)
        self._publish()

    def switch_to(self, channel):
        """Manda el mouse al canal. Devuelve True si se envio."""
        with self.lock:
            if self.mouse.path is None:
                log.info("no muevo el mouse al canal %d: no esta conectado a esta maquina", channel)
                return False
            if channel == self.cfg.get("mouse_channel"):
                log.info("no muevo el mouse: ya esta en el canal %d", channel)
                return False
            try:
                self.mouse.switch(channel)
                log.info("mouse -> canal %d", channel)
                return True
            except Exception as e:
                log.warning("no pude cambiar el mouse: %s", e)
                return False

    def switch_both(self, channel):
        """Desde la app: manda el teclado (Keychron con firmware follow) y luego el mouse."""
        inverse = {c: h for h, c in self.args.kb_map.items()}
        host = inverse.get(channel, channel)
        if send_keyboard_host(host):
            time.sleep(0.15)   # que el teclado empiece a irse antes que el mouse
        return self.switch_to(channel)

    def on_claim(self, channel):
        self.switch_to(channel)

    def run(self):
        args, cfg, mouse = self.args, self.cfg, self.mouse
        self.watcher = DeviceWatcher(max(args.interval, 1.0))
        kb_was = None
        while True:
            try:
                devices = list_hid()
            except Exception as e:
                log.warning("enumerate fallo: %s", e)
                time.sleep(1)
                continue

            # --- mouse: detectar y aprender el canal de esta maquina
            with self.lock:
                if not mouse.present_in(devices) and mouse.probe(devices):
                    try:
                        self.count, cur = mouse.host_info()
                        if cfg.get("mouse_channel") != cur or cfg.get("mouse_pid") != mouse.pid:
                            cfg["mouse_channel"] = cur
                            cfg["mouse_pid"] = mouse.known_pid = mouse.pid
                            save_config(cfg)
                        log.info("mouse %s conectado aqui: canal %d de %d", mouse.name, cur, self.count)
                    except Exception as e:
                        log.warning("no pude leer el canal del mouse: %s", e)
                        mouse.path = None
            self._publish()
            if kb_was is None:   # primera revision: dejar constancia de lo que se ve
                logi = [d for d in devices if d["vendor_id"] == LOGI_VID]
                log.info("dispositivos HID: %d (Logitech: %d); mouse con Change Host aqui: %s",
                         len(devices), len(logi), "si" if mouse.path else "no")

            # --- teclado: avisar cuando llega
            kb = keyboard_present(devices, args.kb_vid, args.kb_pid)
            if kb_was is not None and kb and not kb_was:
                ch = cfg.get("mouse_channel")
                if ch:
                    log.info("teclado llego aqui -> pido el mouse al canal %d", ch)
                    self.net.claim(ch)
                else:
                    log.warning("teclado llego, pero no se mi canal de mouse: conecta el mouse "
                                "a esta maquina una vez para que lo aprenda")
            elif kb_was and not kb:
                log.info("teclado se fue de esta maquina")
            kb_was = kb

            # esperar al siguiente cambio de dispositivos (sin sondear en Windows)
            timeout = 60.0
            if mouse.retry_at:
                timeout = max(0.2, min(mouse.retry_at.values()) - time.monotonic())
            self.watcher.wait(timeout)


class DeviceWatcher:
    """Avisa cuando se conecta/desconecta un dispositivo HID.

    En Windows usa WM_DEVICECHANGE: revisar la lista de dispositivos varias veces
    por segundo bloquea el administrador de dispositivos y hace tartamudear toda la
    PC. En otros sistemas cae a revisar cada `interval` segundos.
    """

    def __init__(self, interval):
        self.interval = interval
        self.event = threading.Event()
        self.native = False
        if sys.platform == "win32":
            ready = threading.Event()
            threading.Thread(target=self._win_loop, args=(ready,), daemon=True).start()
            ready.wait(2)

    def wait(self, timeout):
        if not self.native:
            time.sleep(min(timeout, self.interval))
            return
        if self.event.wait(timeout):
            # los dispositivos Bluetooth aparecen por partes: juntar los avisos de
            # la proxima medio segundo en una sola revision
            time.sleep(0.5)
            self.event.clear()

    def _win_loop(self, ready):
        import ctypes
        from ctypes import wintypes
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32

        WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
                                     wintypes.WPARAM, wintypes.LPARAM)

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                        ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                        ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                        ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]

        class GUID(ctypes.Structure):
            _fields_ = [("d1", ctypes.c_uint32), ("d2", ctypes.c_uint16),
                        ("d3", ctypes.c_uint16), ("d4", ctypes.c_ubyte * 8)]

        class DEV_BROADCAST_DEVICEINTERFACE_W(ctypes.Structure):
            _fields_ = [("dbcc_size", wintypes.DWORD), ("dbcc_devicetype", wintypes.DWORD),
                        ("dbcc_reserved", wintypes.DWORD), ("dbcc_classguid", GUID),
                        ("dbcc_name", ctypes.c_wchar * 1)]

        user32.DefWindowProcW.restype = ctypes.c_ssize_t
        user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.CreateWindowExW.restype = wintypes.HWND
        user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                           ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                           wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
        user32.RegisterDeviceNotificationW.restype = wintypes.HANDLE
        user32.RegisterDeviceNotificationW.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE

        def proc(hwnd, msg, wparam, lparam):
            if msg == 0x0219 and wparam in (0x8000, 0x8004):   # DBT_DEVICEARRIVAL / REMOVECOMPLETE
                self.event.set()
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._proc = WNDPROC(proc)   # mantener la referencia viva
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW(lpfnWndProc=self._proc, hInstance=hinst, lpszClassName="logi_follow_watcher")
        user32.RegisterClassW(ctypes.byref(wc))
        hwnd = user32.CreateWindowExW(0, "logi_follow_watcher", None, 0, 0, 0, 0, 0,
                                      wintypes.HWND(-3), None, hinst, None)   # HWND_MESSAGE
        g = GUID()
        ctypes.windll.hid.HidD_GetHidGuid(ctypes.byref(g))
        flt = DEV_BROADCAST_DEVICEINTERFACE_W(dbcc_size=ctypes.sizeof(DEV_BROADCAST_DEVICEINTERFACE_W),
                                              dbcc_devicetype=5, dbcc_classguid=g)   # DBT_DEVTYP_DEVICEINTERFACE
        if hwnd and user32.RegisterDeviceNotificationW(hwnd, ctypes.byref(flt), 0):
            self.native = True
        ready.set()
        if not self.native:
            log.warning("sin avisos de dispositivos; revisando cada %.1f s", self.interval)
            return

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))


def run_agent(args):
    Agent(args).run()


LOG_PATH = os.path.join(os.path.expanduser("~"), ".logi_follow.log")


def setup_logging():
    """Siempre a ~/.logi_follow.log (en la .app de macOS no hay consola visible);
    tambien a la consola si hay una."""
    import platform
    from logging.handlers import RotatingFileHandler
    fmt = logging.Formatter("%(asctime)s %(message)s", datefmt="%m-%d %H:%M:%S")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    try:
        fh = RotatingFileHandler(LOG_PATH, maxBytes=512 * 1024, backupCount=1, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError:
        pass
    if sys.stderr is not None:
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        root.addHandler(sh)
    log.info("---- inicio: %s %s, python %s", platform.system(), platform.release(), platform.python_version())


def hexint(s):
    return int(s, 16)


def build_parser():
    p = argparse.ArgumentParser(description="El mouse Logitech sigue al teclado entre maquinas.")
    p.add_argument("--info", action="store_true", help="mostrar dispositivos y salir")
    p.add_argument("--switch", type=int, metavar="N", help="cambiar el mouse al canal N y salir")
    p.add_argument("--kb-vid", type=hexint, default=0x04FE, help="VID del teclado (hex, default 04FE = PFU/HHKB)")
    p.add_argument("--kb-pid", type=hexint, default=0x0021, help="PID del teclado (hex, default 0021 = HHKB Hybrid)")
    p.add_argument("--mouse-pid", type=hexint, default=None, help="PID del mouse (hex), por si tienes varios")
    p.add_argument("--group", default="logi-follow", help="nombre de grupo; igual en todas las maquinas")
    p.add_argument("--peer", action="append", default=[], help="IP de otra maquina (si el broadcast no llega)")
    p.add_argument("--interval", type=float, default=1.0,
                   help="segundos entre revisiones en macOS/Linux (default 1). En Windows no se sondea: "
                        "se usan los avisos de conexion/desconexion del sistema")
    p.add_argument("--keys", action="store_true",
                   help="escuchar F18/F19/F20 (Keychron con firmware logi_follow) y mover el mouse al instante")
    p.add_argument("--kb-map", type=parse_kb_map, default={},
                   help="host del teclado -> canal del mouse, ej. 1:2,2:1,3:3 (default: iguales)")
    return p


# --------------------------------------------------------------- CLI --------

def main():
    args = build_parser().parse_args()

    setup_logging()

    if args.info or args.switch:
        devices = hid.enumerate()
        print("teclado presente:", keyboard_present(devices, args.kb_vid, args.kb_pid))
        m = Mouse(args.mouse_pid)
        if not m.probe(devices):
            print("mouse con Change Host: no encontrado")
            return 2
        count, cur = m.host_info()
        print("mouse: %s  canales: %d  actual: %d" % (m.name, count, cur))
        print("config:", CONFIG_PATH, load_config())
        if args.switch:
            if not 1 <= args.switch <= count:
                print("canal invalido")
                return 1
            m.switch(args.switch)
            print("cambiando al canal", args.switch)
        return 0

    run_agent(args)


if __name__ == "__main__":
    raise SystemExit(main())
