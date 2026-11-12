# Logi Switch

Cambia el canal Easy-Switch de un mouse Logitech (probado con MX Master 4) **sin Logi Options+**,
y hace que el mouse **siga al teclado** cuando el teclado cambia de computadora.

- **Ventana minimal** con los tres canales: clic en uno y el mouse se va ahí.
- **El mouse sigue al teclado:**
  - **Keychron K2 HE** con el firmware de `keychron-k2he-follow/`: `Fn+1/2/3` avisa a la PC antes
    de cambiar y el mouse se va al mismo canal al instante, sin red.
  - **Cualquier teclado Bluetooth** (por defecto HHKB Hybrid): cuando el teclado se conecta a una
    máquina, esa máquina avisa por la red local y la que tiene el mouse lo manda.

Habla directo con el mouse por el protocolo HID++ 2.0 de Logitech (función `0x1814 Change Host`).

## Descargar

En [Releases](../../releases) hay builds para **macOS (Apple Silicon)** y **Windows**, generados
por GitHub Actions.

- **macOS:** descomprime y mueve `Logi Switch.app` a Aplicaciones. No está firmada: la primera vez
  ábrela con **clic derecho → Abrir**. Da permiso en Ajustes del Sistema → Privacidad y seguridad →
  **Monitoreo de entrada** (para hablar con el mouse) y **Accesibilidad** (para escuchar F18–F20 del
  Keychron).
- **Windows:** `Logi Switch.exe`. SmartScreen puede avisar: *Más información → Ejecutar de todas
  formas*. Permite el firewall en redes **privadas** (puerto UDP 47811).

Conecta el mouse **una vez** a cada máquina con la app abierta para que aprenda su canal (se guarda
en `~/.logi_follow.json`).

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
| `--interval 1` | macOS/Linux: cada cuánto revisa dispositivos. En Windows usa avisos del sistema |

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

- Probado en Windows 11. En macOS y Linux el código está, pero falta probarlo.
- Cualquier equipo de tu red puede mandar un aviso y mover el mouse; no hay autenticación.
