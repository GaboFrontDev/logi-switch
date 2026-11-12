#!/usr/bin/env python3
"""
Logi Switch: ventana minimal para mandar el mouse a otro canal.

Corre el mismo agente que logi_follow.py (aprende el canal, escucha F18-F20 del
Keychron y los avisos por red), y agrega los tres canales para cambiar a mano.

  python logi_follow_ui.py        (en Windows sin consola: pythonw logi_follow_ui.py)

Clic en un numero = mandar el mouse a ese canal. Clic derecho = ponerle nombre.
Teclas 1/2/3 tambien. Arrastra para mover.
Esc o la x (aparece al pasar) = esconder la ventana; el agente sigue corriendo.
Volver a abrir la app muestra la ventana. Clic derecho en una zona vacia =
"Abrir al iniciar sesion" y "Salir".

  --hidden   arrancar sin mostrar la ventana (lo usa el inicio automatico)
"""

import os
import queue
import socket
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import simpledialog

import logi_follow as lf

# ---------------------------------------------------------------- tokens ----
# Personalidad: objeto sobrio, casi tipografico. Sin cajas ni bordes; la
# jerarquia sale solo del tono. Un acento calido, en un unico lugar.
WIN = sys.platform == "win32"
BG       = "#141312"   # negro calido
TEXT_ON  = "#f4f1ec"   # canal activo
TEXT_HOV = "#b9b4ad"   # hover
TEXT_OFF = "#57534e"   # canales inactivos
TEXT_DIM = "#45413c"   # sin mouse aqui
META     = "#7a756e"   # nombre del mouse
ACCENT   = "#d9a25f"   # punto bajo el canal activo
ALPHA    = 0.97

PAD = 20
COL_W = 72             # ancho de cada columna de canal
W = PAD * 2 + COL_W * 3
H = 132
NUM_Y = 72             # linea central de los numeros
S = 1.0                # escala de pantalla (se calcula en main); todo se dibuja en
                       # unidades base y luego se escala, para que se vea nitido


def font(families, size, weight="normal"):
    fams = set(tkfont.families())
    for f in families:
        if f in fams:
            return tkfont.Font(family=f, size=size, weight=weight)
    return tkfont.Font(size=size, weight=weight)


def win_frameless(root, show=True):
    """Sin barra de titulo, esquinas redondeadas, modo oscuro (Windows 11)."""
    # overrideredirect: tkinter sabe que no hay barra ni bordes. (Quitar el estilo
    # a mano hacia que tkinter "compensara" bordes inexistentes y la ventana se
    # ensanchaba cada vez que se arrastraba.)
    import ctypes
    root.overrideredirect(True)
    sx, sy = root.winfo_screenwidth(), root.winfo_screenheight()
    w, h = round(W * S), round(H * S)
    root.geometry("%dx%d+%d+%d" % (w, h, (sx - w) // 2, (sy - h) // 2))
    root.update_idletasks()
    user32, dwm = ctypes.windll.user32, ctypes.windll.dwmapi
    hwnd = user32.GetParent(root.winfo_id())

    # que aparezca en la barra de tareas (overrideredirect la esconde)
    user32.GetWindowLongW.restype = ctypes.c_long
    ex = user32.GetWindowLongW(hwnd, -20)
    user32.SetWindowLongW(hwnd, -20, (ex | 0x00040000) & ~0x00000080)  # +APPWINDOW, -TOOLWINDOW
    root.withdraw()
    if show:
        root.after(10, root.deiconify)

    for attr, v in ((20, 1), (33, 2)):           # modo oscuro, esquinas redondeadas
        val = ctypes.c_int(v)
        dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(val), ctypes.sizeof(val))
    return hwnd


# ---------------------------------------------------- inicio automatico ----
APP_ID = "io.github.logi-switch"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def launch_args():
    """Comando para volver a lanzar esta app (sin mostrar ventana)."""
    if getattr(sys, "frozen", False):                 # app empaquetada (PyInstaller)
        exe = sys.executable
        if sys.platform == "darwin" and ".app/" in exe:
            bundle = exe[: exe.index(".app/") + 4]
            return ["/usr/bin/open", "-a", bundle, "--args", "--hidden"]
        return [exe, "--hidden"]
    py = sys.executable
    if WIN and py.lower().endswith("python.exe"):
        py = py[:-10] + "pythonw.exe"                  # sin consola
    return [py, os.path.abspath(__file__), "--hidden"]


def _mac_plist():
    return os.path.expanduser("~/Library/LaunchAgents/%s.plist" % APP_ID)


def _linux_desktop():
    return os.path.expanduser("~/.config/autostart/logi-switch.desktop")


def autostart_enabled():
    try:
        if WIN:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
                winreg.QueryValueEx(k, "LogiSwitch")
            return True
        if sys.platform == "darwin":
            return os.path.exists(_mac_plist())
        return os.path.exists(_linux_desktop())
    except OSError:
        return False


def set_autostart(on):
    args = launch_args()
    if WIN:
        import subprocess
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if on:
                winreg.SetValueEx(k, "LogiSwitch", 0, winreg.REG_SZ, subprocess.list2cmdline(args))
            else:
                try:
                    winreg.DeleteValue(k, "LogiSwitch")
                except FileNotFoundError:
                    pass
    elif sys.platform == "darwin":
        import plistlib
        path = _mac_plist()
        if on:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                plistlib.dump({"Label": APP_ID, "ProgramArguments": args, "RunAtLoad": True}, f)
        elif os.path.exists(path):
            os.remove(path)
    else:
        import shlex
        path = _linux_desktop()
        if on:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write("[Desktop Entry]\nType=Application\nName=Logi Switch\nExec=%s\n"
                        "X-GNOME-Autostart-enabled=true\n" % " ".join(shlex.quote(a) for a in args))
        elif os.path.exists(path):
            os.remove(path)
    lf.log.info("abrir al iniciar sesion: %s", "si" if on else "no")


# ------------------------------------------------------- instancia unica ----
INSTANCE_PORT = 47812   # solo en 127.0.0.1


def claim_instance():
    """Devuelve el socket si somos la primera instancia, o None si ya hay otra."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if WIN:
        s.setsockopt(socket.SOL_SOCKET, getattr(socket, "SO_EXCLUSIVEADDRUSE", -5), 1)
    try:
        s.bind(("127.0.0.1", INSTANCE_PORT))
        s.listen(4)
        return s
    except OSError:
        s.close()
        return None


def ask_running_instance_to_show():
    try:
        with socket.create_connection(("127.0.0.1", INSTANCE_PORT), timeout=1) as c:
            c.sendall(b"show")
    except OSError:
        pass


class App:
    def __init__(self, root, agent):
        self.root, self.agent = root, agent
        self.state = agent.state()
        self.hover = None
        self.inside = False
        self.sending = None
        self.pressed = None
        self.drag = None
        self.hwnd = None
        self.q = queue.Queue()

        light = ("Segoe UI Variable Display Light", "Segoe UI Light", "SF Pro Display",
                 "Helvetica Neue", "Inter", "DejaVu Sans")
        text = ("Segoe UI Variable Text", "Segoe UI", "SF Pro Text", "Helvetica Neue", "Inter")
        self.f_num  = font(light, 30)
        self.f_meta = font(text, 9)
        self.f_name = font(text, 8)
        self.f_x    = font(text, 11)

        root.title("Logi Switch")
        root.configure(bg=BG)
        root.resizable(False, False)
        root.attributes("-alpha", ALPHA)
        self.cv = tk.Canvas(root, width=round(W * S), height=round(H * S), bg=BG, highlightthickness=0)
        self.cv.pack()

        cv = self.cv
        cv.bind("<Enter>", lambda e: self.set_inside(True))
        cv.bind("<Leave>", lambda e: (self.set_inside(False), self.set_hover(None)))
        cv.bind("<Motion>", lambda e: self.set_hover(self.hit(e.x, e.y)))
        cv.bind("<ButtonPress-1>", self.on_press)
        cv.bind("<B1-Motion>", self.on_drag)
        cv.bind("<ButtonRelease-1>", self.on_release)
        cv.bind("<Button-3>", self.on_rename)
        cv.bind("<Button-2>", self.on_rename)
        for n in (1, 2, 3):
            root.bind(str(n), lambda e, n=n: self.switch(n))
        root.bind("<Escape>", lambda e: self.hide())
        root.protocol("WM_DELETE_WINDOW", self.hide)          # boton cerrar (macOS/Linux)
        if sys.platform == "darwin":                          # clic en el Dock la vuelve a mostrar
            root.createcommand("::tk::mac::ReopenApplication", self.show)

        self.draw()
        root.after(100, self.pump)

    # ------------------------------------------------------------ estado --
    def push_state(self, st):            # desde el hilo del agente
        self.q.put(st)

    def pump(self):
        changed = False
        while not self.q.empty():
            item = self.q.get()
            if item == "show":
                self.show()
                continue
            self.state = item
            changed = True
        if changed:
            if not self.state["here"]:
                self.sending = None
            self.draw()
        self.root.after(100, self.pump)

    # --------------------------------------------------------- geometria --
    def col_x(self, n):
        return PAD + (n - 0.5) * COL_W

    def hit(self, x, y):
        x, y = x / S, y / S
        if self.inside and W - PAD - 14 <= x <= W - PAD + 6 and PAD - 10 <= y <= PAD + 10:
            return "close"
        if NUM_Y - 30 <= y <= NUM_Y + 36:
            for n in range(1, self.state["count"] + 1):
                if abs(x - self.col_x(n)) <= COL_W / 2 - 6:
                    return n
        return None

    # ------------------------------------------------------------ dibujo --
    def draw(self):
        cv, st = self.cv, self.state
        cv.delete("all")
        here, cur = st["here"], st["channel"]

        # arriba: nombre del mouse, o el estado si no esta aqui / se esta enviando
        name = (st["name"] or "MX Master").replace("_", " ")
        if self.sending:
            meta = "%s  →  %d" % (name, self.sending)
        elif here:
            meta = name
        else:
            meta = "%s  ·  en otra máquina" % name
        cv.create_text(PAD, PAD, anchor="w", text=meta, fill=META, font=self.f_meta)

        if self.inside:
            cv.create_text(W - PAD - 4, PAD - 1, text="×",
                           fill=TEXT_HOV if self.hover == "close" else TEXT_OFF, font=self.f_x)

        # los tres canales
        names = st["names"]
        target = self.sending or (cur if here else None)
        for n in range(1, st["count"] + 1):
            x = self.col_x(n)
            if n == target:
                color = TEXT_ON
            elif not here:
                color = TEXT_DIM
            elif self.hover == n:
                color = TEXT_HOV
            else:
                color = TEXT_OFF
            cv.create_text(x, NUM_Y, text=str(n), fill=color, font=self.f_num)
            if n == target:
                cv.create_oval(x - 2.5, NUM_Y + 27, x + 2.5, NUM_Y + 32, fill=ACCENT, outline="")
            label = names.get(str(n))
            if label:
                cv.create_text(x, NUM_Y + 44, text=label[:12],
                               fill=META if n == target else TEXT_OFF, font=self.f_name)
        if S != 1.0:
            cv.scale("all", 0, 0, S, S)

    # ---------------------------------------------------------- eventos --
    def set_inside(self, v):
        if v != self.inside:
            self.inside = v
            self.draw()

    def set_hover(self, h):
        if h != self.hover:
            self.hover = h
            clickable = h == "close" or (isinstance(h, int) and self.state["here"]
                                         and h != self.state["channel"])
            self.cv.configure(cursor="hand2" if clickable else "")
            self.draw()

    def on_press(self, e):
        self.pressed = self.hit(e.x, e.y)
        self.drag = None
        if self.pressed is None:
            if self.hwnd:
                # que Windows mueva la ventana (fluido, como una ventana normal).
                # PostMessage, no SendMessage: SendMessage bloquea dentro de ctypes y
                # tkinter llamaria a Python sin el GIL -> el proceso truena.
                import ctypes
                ctypes.windll.user32.ReleaseCapture()
                ctypes.windll.user32.PostMessageW(self.hwnd, 0x0112, 0xF012, 0)  # WM_SYSCOMMAND, SC_MOVE|HTCAPTION
                return
            self.drag = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y())

    def on_drag(self, e):
        if self.drag:
            self.root.geometry("+%d+%d" % (e.x_root - self.drag[0], e.y_root - self.drag[1]))

    def on_release(self, e):
        if self.drag:
            self.drag = None
            return
        h = self.hit(e.x, e.y)
        if h is None or h != self.pressed:
            return
        if h == "close":
            self.hide()
        else:
            self.switch(h)

    def switch(self, n):
        st = self.state
        if not st["here"] or n == st["channel"] or n > st["count"] or self.sending:
            return
        self.sending = n
        self.draw()

        def go():
            if not self.agent.switch_to(n):
                self.sending = None
                self.q.put(self.agent.state())
        threading.Thread(target=go, daemon=True).start()
        self.root.after(4000, self.clear_sending)   # si el mouse no se fue, volver a normal

    def clear_sending(self):
        if self.sending:
            self.sending = None
            self.draw()

    # ------------------------------------------------- mostrar / ocultar --
    def hide(self):
        self.inside = False
        self.root.withdraw()
        lf.log.info("ventana escondida; el agente sigue corriendo")

    def show(self):
        lf.log.info("mostrar ventana")
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(200, lambda: self.root.attributes("-topmost", False))
        try:
            self.root.focus_force()
        except tk.TclError:
            pass

    def listen_for_show(self, sock):
        def loop():
            while True:
                try:
                    c, _ = sock.accept()
                    with c:
                        if c.recv(16).startswith(b"show"):
                            self.q.put("show")
                except OSError:
                    return
        threading.Thread(target=loop, daemon=True).start()

    def menu(self, e):
        m = tk.Menu(self.root, tearoff=0)
        self.auto_var = tk.BooleanVar(value=autostart_enabled())
        m.add_checkbutton(label="Abrir al iniciar sesión", variable=self.auto_var,
                          command=lambda: set_autostart(self.auto_var.get()))
        m.add_separator()
        m.add_command(label="Salir", command=self.root.destroy)
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def on_rename(self, e):
        n = self.hit(e.x, e.y)
        if not isinstance(n, int):
            self.menu(e)
            return
        cur = self.state["names"].get(str(n), "")
        name = simpledialog.askstring("Nombre", "Nombre para el canal %d:" % n,
                                      initialvalue=cur, parent=self.root)
        if name is not None:
            self.agent.set_name(n, name.strip())


def main():
    argv = sys.argv[1:]
    hidden = "--hidden" in argv
    argv = [a for a in argv if a != "--hidden"]
    args = lf.build_parser().parse_args(argv)

    inst = claim_instance()
    if inst is None:                    # ya hay una corriendo: que se muestre y salir
        if not hidden:
            ask_running_instance_to_show()
        return
    try:
        import pynput  # noqa: F401
        args.keys = True        # escuchar F18-F20 del Keychron si se puede
    except ImportError:
        args.keys = False

    lf.setup_logging()

    global S
    if WIN:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)   # coordenadas reales, sin borrosidad
        except Exception:
            pass
    root = tk.Tk()
    S = root.winfo_fpixels("1i") / 96.0
    agent = lf.Agent(args)
    app = App(root, agent)
    app.listen_for_show(inst)
    agent.on_state = app.push_state
    threading.Thread(target=agent.run, daemon=True).start()
    if WIN:
        try:
            app.hwnd = win_frameless(root, show=not hidden)
        except Exception as e:
            lf.log.warning("ventana sin barra no disponible: %s", e)
    if hidden:
        root.withdraw()
    root.mainloop()


if __name__ == "__main__":
    main()
