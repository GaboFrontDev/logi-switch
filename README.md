# Logi Switch

Cambia el canal Easy-Switch de un mouse Logitech (probado con MX Master 4) **sin Logi Options+**,
y hace que el mouse **siga al teclado** cuando el teclado cambia de computadora.

- **Ventana minimal** con los tres canales: clic en uno y el mouse se va ahí. Con el Keychron
  K2 HE con firmware follow, **el teclado también se va** (la app se lo pide parpadeando
  Bloq Despl en Windows o Bloq Mayús en macOS: 4/6/8 cambios = host 1/2/3).
- **El mouse sigue al teclado:**
  - **Keychron K2 HE** con el firmware de `keychron-k2he-follow/`: `Fn+1/2/3` avisa a la PC antes
    de cambiar y el mouse se va al mismo canal al instante, sin red.
  - **Cualquier teclado Bluetooth** (por defecto HHKB Hybrid): cuando el teclado se conecta a una
    máquina, esa máquina avisa por la red local y la que tiene el mouse lo manda.

Habla directo con el mouse por el protocolo HID++ 2.0 de Logitech (función `0x1814 Change Host`).

## Instalar en macOS

Instala **y actualiza** con un solo comando en la Terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/GaboFrontDev/logi-switch/main/mac/install.sh | bash
```

El script ([`mac/install.sh`](mac/install.sh)):

1. **Solo la primera vez:** crea un certificado de firma llamado **"Logi Switch Local"** en tu
   llavero. macOS te pide tu contraseña para confiar en él (solo para firmar código).
2. Descarga la última versión de [Releases](../../releases) (Apple Silicon).
3. Cierra la app si está abierta y la reemplaza en `/Applications`.
4. Le quita la cuarentena (no sale el aviso de "no se puede verificar").
5. La firma con tu certificado y la abre.

**¿Por qué firmarla?** macOS guarda los permisos según la firma de la app. Sin firma, cada versión
nueva cuenta como otra app y hay que volver a dar los permisos. Firmada siempre con el mismo
certificado, los conserva.

### Permisos (primera vez)

En Ajustes del Sistema → Privacidad y seguridad, activa Logi Switch en:

- **Monitoreo de entrada:** para hablar con el mouse.
- **Accesibilidad:** para escuchar F18–F20 del Keychron y cambiar Bloq Mayús.

Luego ciérrala (clic derecho → **Salir**) y ábrela de nuevo.

Si venías de una versión sin firmar y los permisos "no se aplican", bórralos y dalos otra vez:

```bash
tccutil reset ListenEvent io.github.logi-switch
tccutil reset Accessibility io.github.logi-switch
```

### A mano

Descarga `LogiSwitch-macos-arm64.zip` de [Releases](../../releases), descomprime y mueve
`Logi Switch.app` a Aplicaciones. La primera vez ábrela con **clic derecho → Abrir**. Con este
método los permisos se pierden en cada actualización.

## Instalar en Windows

Descarga `LogiSwitch-windows-x64.zip` de [Releases](../../releases) y abre `Logi Switch.exe`.
SmartScreen puede avisar: *Más información → Ejecutar de todas formas*. Permite el firewall en
redes **privadas** (puerto UDP 47811).

## Primer uso

Conecta el mouse **una vez** a cada máquina con la app abierta para que aprenda su canal (se guarda
en `~/.logi_follow.json`). Activa **Abrir al iniciar sesión** (clic derecho en una zona vacía de
la ventana) en cada máquina: el mouse solo sigue al teclado si la app está corriendo.

## La ventana

- Clic en un número (o teclas `1`/`2`/`3`): manda el mouse a ese canal.
- Clic derecho en un número: ponerle nombre ("Laptop", "Mac"…).
- Si el mouse está en otra máquina, los números se apagan: desde aquí ya no se le puede hablar.
- Arrastra para mover. `Esc` o la `×` (aparece al pasar el mouse) **esconden** la ventana: la app
  sigue corriendo y el mouse sigue al teclado. Vuelve a abrir la app (o clic en el Dock en macOS)
  para mostrarla.
- Clic derecho en una zona vacía: **Abrir al iniciar sesión** (arranca escondida) y **Salir**.

> El mouse solo sigue al teclado si la app está corriendo en la máquina donde está el teclado.
> Activa "Abrir al iniciar sesión" en cada máquina.

## Desde el código

```
python3 -m pip install hidapi pynput
python3 logi_follow_ui.py        # ventana + agente
python3 logi_follow.py --info    # ver mouse, teclado y canales
python3 logi_follow.py --switch 2
python3 logi_follow.py --keys    # agente sin ventana
```

| Opción | Para qué |
|---|---|
| `--switch N` | Cambiar el mouse al canal N y salir |
| `--keys` | Escuchar F18/F19/F20 (Keychron con firmware follow) |
| `--kb-map 1:2,...` | Host del teclado → canal del mouse, si los emparejaste en distinto orden |
| `--peer IP` | Mandar el aviso directo a una IP si el broadcast no llega (repetible) |
| `--group nombre` | Separar grupos de máquinas (igual en todas) |
| `--kb-vid/--kb-pid` | Otro teclado Bluetooth como "líder" (hex) |
| `--mouse-pid` | Elegir el mouse si tienes varios (hex) |
| `--interval 1` | Linux: cada cuánto revisa dispositivos. En macOS es solo red de seguridad; Windows y macOS usan avisos del sistema |

### Linux

Permiso para hablar con el mouse y el teclado por Bluetooth, en `/etc/udev/rules.d/70-logi-follow.rules`:

```
SUBSYSTEM=="hidraw", KERNELS=="0005:046D:*", TAG+="uaccess"
SUBSYSTEM=="hidraw", KERNELS=="0005:04FE:*", TAG+="uaccess"
```

Luego `sudo udevadm control --reload && sudo udevadm trigger` y reconecta los dispositivos.

## Otros archivos

- `logi-switch.cs`: versión mínima en C# para Windows (solo cambiar de canal), compilable con el
  `csc.exe` que trae Windows.
- `keychron-k2he-follow/`: firmware modificado del Keychron K2 HE (ANSI). Ver su README.

## Limitaciones

- Probado en Windows 11 y macOS (Apple Silicon) con MX Master 4, Keychron K2 HE y HHKB Hybrid.
  Linux: el código está, pero falta probarlo.
- El HHKB no se puede mover desde la app (firmware cerrado): con él el cambio siempre empieza en
  el teclado (`Fn+Ctrl+número`) y el mouse lo sigue por red, en cuanto el sistema ve llegar al
  teclado (Windows y macOS avisan al instante).
- Cualquier equipo de tu red puede mandar un aviso y mover el mouse; no hay autenticación.
