# Firmware K2 HE (ANSI) con aviso de cambio de host

Basado en el keymap `via` oficial de Keychron (rama `hall_effect_playground`,
`keyboards/keychron/k2_he/ansi_rgb`). Las teclas y capas quedan **idénticas**. Solo cambia
lo que pasa con `Fn+1/2/3` en modo **Bluetooth**:

1. El teclado manda `F18`, `F19` o `F20` (host 1, 2 o 3) a la PC actual.
2. Espera ~120 ms a que ese aviso salga por Bluetooth.
3. Hace el cambio de host normal de Keychron. Mantener la tecla para emparejar sigue igual.

En la PC, `logi_follow.py --keys` ve esa tecla y manda el MX Master al mismo canal.

**Cambio pedido desde la PC:** por Bluetooth lo único que la PC le manda al teclado es el
estado de las luces. Si Bloq Despl o Bloq Mayús cambian **4, 6 u 8 veces** seguidas (cada cambio
a menos de 700 ms del anterior), el teclado se va al **host 1, 2 o 3**. Siempre es un número
par, así que la luz queda como estaba. La app Logi Switch lo usa al dar clic en un canal.

> El cambio de host solo existe en modo **Bluetooth** (3 hosts). En 2.4 GHz hay un solo host,
> el Keychron Link.

## Archivos

| Archivo | Qué es |
|---|---|
| `keymap.c` | keymap `via` oficial + el aviso (todo al final del archivo) |
| `rules.mk` | `VIA_ENABLE` + `DEFERRED_EXEC_ENABLE` |
| `oficial_keychron_k2_he_ansi_rgb_via.bin` | firmware oficial del repo de Keychron, por si quieres volver |

## Compilar (Windows)

1. Instalar **QMK MSYS** desde https://msys.qmk.fm y abrirlo.
2. Bajar el firmware de Keychron (rama HE):
   ```
   qmk setup Keychron/qmk_firmware -b hall_effect_playground -H ~/keychron_qmk
   ```
3. Copiar esta carpeta como un keymap nuevo:
   ```
   mkdir -p ~/keychron_qmk/keyboards/keychron/k2_he/ansi_rgb/keymaps/follow
   cp /ruta/a/logi-switch/keychron-k2he-follow/{keymap.c,rules.mk} ~/keychron_qmk/keyboards/keychron/k2_he/ansi_rgb/keymaps/follow/
   ```
4. Compilar:
   ```
   cd ~/keychron_qmk && qmk compile -kb keychron/k2_he/ansi_rgb -km follow
   ```
   Sale `keychron_k2_he_ansi_rgb_follow.bin`.

## Flashear

1. Desconectar el cable USB y poner el switch del teclado en **Cable**.
2. Mantener **Esc** presionada (o el botón de reset debajo de la barra espaciadora) y conectar el
   cable. El teclado entra en modo de actualización (aparece como "STM32 BOOTLOADER").
3. Flashear con **QMK Toolbox** (abrir el `.bin`, luego *Flash*), o con
   `qmk flash -kb keychron/k2_he/ansi_rgb -km follow`.

**Para volver al oficial:** mismos pasos con `oficial_keychron_k2_he_ansi_rgb_via.bin`, o con
el actualizador de firmware de Keychron Launcher. El bootloader está en la memoria ROM del chip,
así que este modo de recuperación siempre está disponible.

## Después de flashear

- Revisar la calibración de los switches magnéticos en Keychron Launcher. No está confirmado si
  se conserva.
- En cada PC: `python logi_follow.py --keys` (requiere `pip install pynput`).
  - macOS: dar permiso de **Accesibilidad** y **Monitoreo de entrada** a Python o a la Terminal.
  - Linux: pynput solo funciona en X11; en Wayland no ve las teclas globales.
- Si emparejaste el teclado y el mouse en un orden distinto (por ejemplo, la PC A es host 1 del
  teclado pero canal 2 del mouse): `--kb-map 1:2,2:1,3:3`.

## Estado

- **Compilado** el 2026-11-12 con QMK MSYS 1.12.0, rama `hall_effect_playground` (commit
  `bc56b3c`), sin errores ni advertencias. Resultado: `keychron_k2_he_ansi_rgb_follow.bin`
  (124 KB), ya está en esta carpeta.
- **Flasheado** el 2026-11-12 con `dfu-util`. El teclado arranca y contesta: firmware
  `v1.0.0 2026-11-12-14:18:02`, protocolo Keychron 2.
- **Ojo, versión más vieja:** el de fábrica era `v1.3.0 2026-05-26` (protocolo Keychron 4) y la
  rama pública de GitHub va atrás. Puede que falten funciones nuevas de Keychron Launcher. Para
  volver a la v1.3.0 real, usa el actualizador de firmware de **Keychron Launcher**. El
  `oficial_...bin` de esta carpeta viene de la misma rama de GitHub, probablemente igual de vieja.
