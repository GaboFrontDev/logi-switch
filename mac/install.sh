#!/bin/bash
# Instala o actualiza Logi Switch en macOS y la firma con un certificado propio,
# para que macOS conserve los permisos (Monitoreo de entrada / Accesibilidad)
# entre versiones.
#
#   curl -fsSL https://raw.githubusercontent.com/GaboFrontDev/logi-switch/main/mac/install.sh | bash
#
# La primera vez crea el certificado "Logi Switch Local" en tu llavero de inicio
# de sesion y macOS te pide tu contrasena para confiar en el (solo para firmar
# codigo). Las siguientes veces solo descarga, reemplaza y firma.

set -euo pipefail

REPO="GaboFrontDev/logi-switch"
CERT="Logi Switch Local"
APP="/Applications/Logi Switch.app"
KEYCHAIN="$HOME/Library/Keychains/login.keychain-db"
OPENSSL=/usr/bin/openssl   # el de macOS (LibreSSL); el de Homebrew genera .p12 que security no importa

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }

# 1) certificado propio (una sola vez) ------------------------------------------
if ! security find-certificate -c "$CERT" "$KEYCHAIN" >/dev/null 2>&1; then
    say "Creando el certificado \"$CERT\" (una sola vez)…"
    tmp=$(mktemp -d)
    cat > "$tmp/cfg" <<EOF
[req]
distinguished_name = dn
x509_extensions = ext
prompt = no
[dn]
CN = $CERT
[ext]
keyUsage = critical, digitalSignature
extendedKeyUsage = critical, codeSigning
basicConstraints = critical, CA:false
EOF
    "$OPENSSL" req -x509 -newkey rsa:2048 -nodes -days 3650 \
        -keyout "$tmp/key.pem" -out "$tmp/cert.pem" -config "$tmp/cfg" 2>/dev/null
    "$OPENSSL" pkcs12 -export -inkey "$tmp/key.pem" -in "$tmp/cert.pem" \
        -out "$tmp/id.p12" -passout pass:logiswitch -name "$CERT"
    security import "$tmp/id.p12" -k "$KEYCHAIN" -P logiswitch -T /usr/bin/codesign >/dev/null
    say "macOS te va a pedir tu contraseña para confiar en el certificado (solo para firmar código)."
    security add-trusted-cert -r trustRoot -p codeSign -k "$KEYCHAIN" "$tmp/cert.pem"
    rm -rf "$tmp"
fi

# 2) descargar la ultima version ------------------------------------------------
say "Buscando la última versión…"
url=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" \
      | grep -o '"browser_download_url": *"[^"]*macos-arm64\.zip"' \
      | sed -E 's/.*"(https[^"]+)"/\1/')
if [ -z "$url" ]; then
    echo "No encontré el .zip de macOS en la última release." >&2
    exit 1
fi
echo "$url"
tmp=$(mktemp -d)
curl -fsSL -o "$tmp/app.zip" "$url"
ditto -x -k "$tmp/app.zip" "$tmp/x"

# 3) cerrar la version abierta y reemplazarla -----------------------------------
say "Instalando en /Applications…"
osascript -e 'quit app "Logi Switch"' >/dev/null 2>&1 || true
sleep 1
pkill -f "Logi Switch.app/Contents/MacOS" >/dev/null 2>&1 || true
rm -rf "$APP"
ditto "$tmp/x/Logi Switch.app" "$APP"
rm -rf "$tmp"

# 4) quitar la cuarentena y firmar con el certificado propio --------------------
xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true
codesign --force --deep --sign "$CERT" "$APP"
codesign --verify --deep "$APP" && echo "Firmada con \"$CERT\"."

say "Abriendo Logi Switch…"
open "$APP"

cat <<'EOF'

Listo. Si es la primera vez con el certificado propio:
  1. Ajustes del Sistema > Privacidad y seguridad > Monitoreo de entrada y Accesibilidad:
     quita las entradas viejas de Logi Switch (-) y activa la nueva.
  2. Cierra y abre la app (clic derecho > Salir, y ábrela otra vez).
En las próximas actualizaciones ya no hará falta: corre este mismo comando y listo.
EOF
