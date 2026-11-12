/* Copyright 2024 @ Keychron (https://www.keychron.com)
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#include QMK_KEYBOARD_H
#include "keychron_common.h"

enum layers {
    MAC_BASE,
    MAC_FN,
    WIN_BASE,
    WIN_FN,
};

#define FN_MAC MO(MAC_FN)
#define FN_WIN MO(WIN_FN)

// clang-format off
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    [MAC_BASE] = LAYOUT_ansi_84(
        KC_ESC,   KC_BRID,  KC_BRIU,  KC_MCTRL, KC_LNPAD, RGB_VAD,  RGB_VAI,  KC_MPRV,  KC_MPLY,  KC_MNXT,  KC_MUTE,  KC_VOLD,  KC_VOLU,  KC_SNAP,  KC_DEL,   RGB_MOD,
        KC_GRV,   KC_1,     KC_2,     KC_3,     KC_4,     KC_5,     KC_6,     KC_7,     KC_8,     KC_9,     KC_0,     KC_MINS,  KC_EQL,   KC_BSPC,            KC_PGUP,
        KC_TAB,   KC_Q,     KC_W,     KC_E,     KC_R,     KC_T,     KC_Y,     KC_U,     KC_I,     KC_O,     KC_P,     KC_LBRC,  KC_RBRC,  KC_BSLS,            KC_PGDN,
        KC_CAPS,  KC_A,     KC_S,     KC_D,     KC_F,     KC_G,     KC_H,     KC_J,     KC_K,     KC_L,     KC_SCLN,  KC_QUOT,            KC_ENT,             KC_HOME,
        KC_LSFT,            KC_Z,     KC_X,     KC_C,     KC_V,     KC_B,     KC_N,     KC_M,     KC_COMM,  KC_DOT,   KC_SLSH,            KC_RSFT,  KC_UP,    KC_END,
        KC_LCTL,  KC_LOPTN, KC_LCMMD,                               KC_SPC,                                 KC_RCMMD, FN_MAC,   KC_RCTL,  KC_LEFT,  KC_DOWN,  KC_RGHT),

    [MAC_FN] = LAYOUT_ansi_84(
        _______,  KC_F1,    KC_F2,    KC_F3,    KC_F4,    KC_F5,    KC_F6,    KC_F7,    KC_F8,    KC_F9,    KC_F10,   KC_F11,   KC_F12,   _______,  _______,  RGB_TOG,
        _______,  BT_HST1,  BT_HST2,  BT_HST3,  P2P4G,    _______,  _______,  _______,  _______,  _______,  _______,  _______,  _______,  _______,            _______,
        RGB_TOG,  RGB_MOD,  RGB_VAI,  RGB_HUI,  RGB_SAI,  RGB_SPI,  _______,  _______,  _______,  _______,  _______,  _______,  _______,  _______,            _______,
        _______,  RGB_RMOD, RGB_VAD,  RGB_HUD,  RGB_SAD,  RGB_SPD,  _______,  _______,  _______,  _______,  _______,  _______,            _______,            _______,
        _______,            _______,  _______,  _______,  _______,  BAT_LVL,  NK_TOGG,  _______,  _______,  _______,  _______,            _______,  _______,  _______,
        _______,  _______,  _______,                                _______,                                _______,  _______,  _______,  _______,  _______,  _______),

    [WIN_BASE] = LAYOUT_ansi_84(
        KC_ESC,   KC_F1,    KC_F2,    KC_F3,    KC_F4,    KC_F5,    KC_F6,    KC_F7,    KC_F8,    KC_F9,    KC_F10,   KC_F11,   KC_F12,   KC_PSCR,  KC_DEL,   RGB_MOD,
        KC_GRV,   KC_1,     KC_2,     KC_3,     KC_4,     KC_5,     KC_6,     KC_7,     KC_8,     KC_9,     KC_0,     KC_MINS,  KC_EQL,   KC_BSPC,            KC_PGUP,
        KC_TAB,   KC_Q,     KC_W,     KC_E,     KC_R,     KC_T,     KC_Y,     KC_U,     KC_I,     KC_O,     KC_P,     KC_LBRC,  KC_RBRC,  KC_BSLS,            KC_PGDN,
        KC_CAPS,  KC_A,     KC_S,     KC_D,     KC_F,     KC_G,     KC_H,     KC_J,     KC_K,     KC_L,     KC_SCLN,  KC_QUOT,            KC_ENT,             KC_HOME,
        KC_LSFT,            KC_Z,     KC_X,     KC_C,     KC_V,     KC_B,     KC_N,     KC_M,     KC_COMM,  KC_DOT,   KC_SLSH,            KC_RSFT,  KC_UP,    KC_END,
        KC_LCTL,  KC_LGUI,  KC_LALT,                                KC_SPC,                                 KC_RALT,  FN_WIN,   KC_RCTL,  KC_LEFT,  KC_DOWN,  KC_RGHT),

    [WIN_FN] = LAYOUT_ansi_84(
        _______,  KC_BRID,  KC_BRIU,  KC_TASK,  KC_FILE,  RGB_VAD,  RGB_VAI,  KC_MPRV,  KC_MPLY,  KC_MNXT,  KC_MUTE,  KC_VOLD,  KC_VOLU,  _______,  _______,  RGB_TOG,
        _______,  BT_HST1,  BT_HST2,  BT_HST3,  P2P4G,    _______,  _______,  _______,  _______,  _______,  _______,  _______,  _______,  _______,            _______,
        RGB_TOG,  RGB_MOD,  RGB_VAI,  RGB_HUI,  RGB_SAI,  RGB_SPI,  _______,  _______,  _______,  _______,  _______,  _______,  _______,  _______,            _______,
        _______,  RGB_RMOD, RGB_VAD,  RGB_HUD,  RGB_SAD,  RGB_SPD,  _______,  _______,  _______,  _______,  _______,  _______,            _______,            _______,
        _______,            _______,  _______,  _______,  _______,  BAT_LVL,  NK_TOGG,  _______,  _______,  _______,  _______,            _______,  _______,  _______,
        _______,  _______,  _______,                                _______,                                _______,  _______,  _______,  _______,  _______,  _______)
};

// clang-format on

/* ------------------------------------------------------------------------
 * logi_follow: avisar a la PC antes de cambiar de host Bluetooth.
 *
 * Al presionar BT_HST1..3 (Fn+1/2/3) el teclado primero manda F18/F19/F20 a la
 * PC actual, y despues de ~120 ms (para que ese aviso salga por Bluetooth)
 * ejecuta el cambio de host normal de Keychron. El agente logi_follow en la PC
 * ve la tecla y manda el mouse al mismo canal.
 *
 * La tecla presionada (y su liberacion) se reenvian al manejador original, asi
 * que mantenerla presionada para emparejar sigue funcionando igual.
 * --------------------------------------------------------------------- */
#ifdef LK_WIRELESS_ENABLE
#    include "transport.h"
#    include "report_buffer.h"
#    include "keychron_wireless_common.h"

#    define FOLLOW_DELAY_MS 120
#    define FOLLOW_MAX_WAIT_MS 400

static uint16_t   follow_keycode  = KC_NO;
static keyrecord_t follow_press;
static keyrecord_t follow_release;
static bool       follow_released = false;
static uint16_t   follow_started;

static uint32_t follow_fire(uint32_t trigger_time, void *cb_arg) {
    // esperar a que el aviso (F18-F20) haya salido del buffer inalambrico
    if (!report_buffer_is_empty() && timer_elapsed(follow_started) < FOLLOW_MAX_WAIT_MS) {
        return 10;
    }
    uint16_t kc    = follow_keycode;
    follow_keycode = KC_NO;
    process_record_keychron_wireless(kc, &follow_press);
    if (follow_released) {
        process_record_keychron_wireless(kc, &follow_release);
    }
    return 0;
}
#endif

/* ------------------------------------------------------------------------
 * Cambio de host pedido DESDE LA PC, usando las luces del teclado.
 *
 * Por Bluetooth lo unico que la PC le manda al teclado es el estado de las
 * luces (Bloq Mayus / Bloq Despl). La app las cambia rapido un numero par de
 * veces (quedan como estaban):
 *     4 cambios = host 1,   6 = host 2,   8 = host 3
 * cada cambio a menos de 700 ms del anterior. Windows usa Bloq Despl y macOS
 * Bloq Mayus; aqui se cuentan los dos. (Con 250 ms macOS a veces retrasaba un
 * cambio de mas y la secuencia se partia en dos.)
 * --------------------------------------------------------------------- */
#ifdef LK_WIRELESS_ENABLE
#    include "wireless.h"

#    define LEDCMD_GAP_MS 700

static uint8_t        ledcmd_count = 0;
static uint16_t       ledcmd_last;
static bool           ledcmd_init = false;
static led_t          ledcmd_prev;
static deferred_token ledcmd_token = INVALID_DEFERRED_TOKEN;

static uint32_t ledcmd_check(uint32_t trigger_time, void *cb_arg) {
    if (timer_elapsed(ledcmd_last) < LEDCMD_GAP_MS) {
        return 50;   // todavia llegan cambios
    }
    uint8_t n    = ledcmd_count;
    ledcmd_count = 0;
    ledcmd_token = INVALID_DEFERRED_TOKEN;
    if (get_transport() == TRANSPORT_BLUETOOTH && n >= 4 && n <= 8 && n % 2 == 0) {
        wireless_connect_ex(n / 2 - 1, 0);   // 4->1, 6->2, 8->3
    }
    return 0;
}

bool led_update_user(led_t state) {
    if (!ledcmd_init) {
        ledcmd_init = true;
        ledcmd_prev = state;
        return true;
    }
    if (state.caps_lock != ledcmd_prev.caps_lock || state.scroll_lock != ledcmd_prev.scroll_lock) {
        ledcmd_count++;
        ledcmd_last = timer_read();
        if (ledcmd_token == INVALID_DEFERRED_TOKEN) {
            ledcmd_token = defer_exec(50, ledcmd_check, NULL);
        }
    }
    ledcmd_prev = state;
    return true;
}
#endif

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
#ifdef LK_WIRELESS_ENABLE
    if (keycode >= BT_HST1 && keycode <= BT_HST3 && get_transport() == TRANSPORT_BLUETOOTH) {
        if (record->event.pressed) {
            if (follow_keycode != KC_NO) return false;  // ya hay un cambio en curso
            tap_code(KC_F18 + (keycode - BT_HST1));      // F18=host1, F19=host2, F20=host3
            follow_keycode  = keycode;
            follow_press    = *record;
            follow_released = false;
            follow_started  = timer_read();
            defer_exec(FOLLOW_DELAY_MS, follow_fire, NULL);
            return false;
        }
        if (follow_keycode == keycode) {               // soltaron antes de ejecutar el cambio
            follow_release  = *record;
            follow_released = true;
            return false;
        }
    }
#endif
    if (!process_record_keychron_common(keycode, record)) {
        return false;
    }
    return true;
}
