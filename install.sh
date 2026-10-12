#!/usr/bin/env bash
# ==============================================================================
# Script de instalación automática para Live Preview OV5647 en pantalla DSI
# ==============================================================================
set -e

echo "[*] Instalando dependencias necesarias del sistema..."
sudo apt-get update
sudo apt-get install -y gcc build-essential python3 python3-numpy rpicam-apps-core

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[*] Compilando biblioteca acelerada C libyuv2rgb.so..."
gcc -O3 -fPIC -shared "$SCRIPT_DIR/src/yuv2rgb.c" -o "$SCRIPT_DIR/libyuv2rgb.so"

chmod +x "$SCRIPT_DIR/live_cam_fb0.py"

echo ""
echo "======================================================================"
echo "  [+] Instalación completada con éxito."
echo "      Para iniciar la vista previa en vivo ejecuta:"
echo "      $SCRIPT_DIR/live_cam_fb0.py"
echo "======================================================================"
