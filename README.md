# Raspberry Pi 3B+ • OV5647 CSI Live Preview en Pantalla DSI (Headless / TTY)

[![Platform: Raspberry Pi 3B+](https://img.shields.io/badge/Platform-Raspberry%20Pi%203B%2B-red.svg)](https://www.raspberrypi.com/)
[![OS: Raspberry Pi OS Lite](https://img.shields.io/badge/OS-Raspberry%20Pi%20OS%20Lite%20(64--bit)-blue.svg)](https://www.raspberrypi.com/software/)
[![Camera: OmniVision OV5647](https://img.shields.io/badge/Camera-OV5647%20CSI%20(5MP)-green.svg)](https://www.ovt.com/)
[![Display: DSI 800x480](https://img.shields.io/badge/Display-DSI%20800x480-orange.svg)]()
[![Performance: 30 FPS](https://img.shields.io/badge/Performance-30%20FPS%20%7C%20%3C15%25%20CPU-brightgreen.svg)]()

Solución integral de alto rendimiento y latencia mínima (< 50 ms) para proyectar el flujo de video en vivo de una cámara **OmniVision OV5647 CSI** directamente sobre una pantalla conectada al bus **DSI**, a pantalla completa ($800 \times 480$), sin servidor gráfico X11/Wayland ni gestor de ventanas.

---

## 📸 Arquitectura y Solución Técnica

En entornos headless/consola con el stack moderno del kernel (`vc4-kms-v3d` y `libcamera`), los comandos nativos como `rpicam-vid` proyectan la previsualización en un plano DRM overlay (`Plane 100`). Sin un gestor de composición gráfico, la consola virtual de Linux (`fbcon` en `Plane 76`) oculta dicho plano o bloquea la salida visual.

Este proyecto resuelve el problema implementando una tubería de procesamiento directo a memoria:

```
[ Cámara CSI (OV5647) ]
           │
           ▼
[ Hardware ISP Unicam ] ──(Raw YUV420 @ 30 FPS / Stride 832B)──> [ Pipe Unix ]
                                                                       │
                                                                       ▼
[ Motor C Vectorizado (libyuv2rgb.so) ] <──(YUV420 a RGB565)───────────┤
           │
           ▼
[ Memoria Mapeada mmap(/dev/fb0) ] ──(800x480 @ 16 bpp)──> [ Pantalla DSI ]
```

### 🔬 Resolución del Problema de Franjas y Tinte Verde (*Hardware Stride*)
El procesador de señal de imagen (**ISP VideoCore**) alinea cada línea horizontal de video a múltiplos de **64 bytes**:
* Ancho visible: **800 píxeles** (no divisible por 64).
* Stride de luminancia (Y): **$13 \times 64 = 832\text{ bytes}$** por fila.
* Stride de crominancia (UV): **$13 \times 32 = 416\text{ bytes}$** por fila.
* Tamaño exacto de fotograma: **$599{,}040\text{ bytes}$** ($832 \times 480 \times 1.5$).

Si el algoritmo de conversión asume 800 bytes lineales, se acumula un desfase de 32 bytes por línea (creando **franjas verticales periódicas**) y desplazando el inicio de los planos U y V en $15{,}360\text{ bytes}$ (provocando un **tinte verde saturado**). La biblioteca C incluida en este repositorio respeta exactamente el *hardware stride* de 832/416 bytes, produciendo una imagen nítida con colores reales.

---

## ⚡ Rendimiento Medido (Raspberry Pi 3B+)

| Métrica | Valor Obtenido |
| :--- | :--- |
| **Tasa de Refresco** | **30.5 – 31.5 FPS** constantes |
| **Latencia de Entrada a Pantalla** | **~45 ms** |
| **Consumo Total de CPU** | **< 15%** (85.4% de la CPU en reposo / *idle*) |
| **Consumo de Memoria RAM** | **~12 MB** (Python) + 20 MB (ISP Buffers) |
| **Resolución Nativa** | **800 × 480** (Fullscreen DSI) |

---

## 🛠️ Requisitos de Hardware y Software

* **Placa:** Raspberry Pi 3 Modelo B+
* **Cámara:** Módulo CSI 5 MP (sensor OmniVision OV5647, cable flex 15 pines)
* **Pantalla:** Pantalla DSI conectada por flex al puerto DSI (resolución $800 \times 480$, 16 bpp RGB565)
* **Sistema Operativo:** Raspberry Pi OS Lite (Debian Bookworm o Trixie) 64-bit

---

## ⚙️ Configuración del Sistema (`/boot/firmware/config.txt`)

Verifica que tu archivo `/boot/firmware/config.txt` (o `/boot/config.txt`) contenga las siguientes directivas:

```ini
# Aceleración por hardware DRM KMS (Full KMS)
dtoverlay=vc4-kms-v3d
max_framebuffers=2

# Detección automática del sensor CSI y la pantalla DSI
camera_auto_detect=1
display_auto_detect=1

# Asignación de memoria GPU para buffers de video
gpu_mem=128

# Kernel de 64 bits y optimizaciones
arm_64bit=1
disable_overscan=1
arm_boost=1
```

---

## 🚀 Instalación Rápida

Clona el repositorio y ejecuta el script de instalación en tu Raspberry Pi:

```bash
git clone https://github.com/l707l/rpi-ov5647-dsi-live-preview.git
cd rpi-ov5647-dsi-live-preview
chmod +x install.sh
./install.sh
```

---

## 💻 Uso

### 1. Ejecución Básica
```bash
./live_cam_fb0.py
```
*Para detener la transmisión limpiamente y regresar a la terminal, presiona `Ctrl+C`.*

### 2. Opciones de Rotación y Volteo
Si el sensor está montado en posición invertida o necesitas orientación tipo espejo:

```bash
# Rotar 180 grados:
./live_cam_fb0.py --rotation 180

# Voltear verticalmente:
./live_cam_fb0.py --vflip

# Voltear horizontalmente:
./live_cam_fb0.py --hflip

# Ajustar tasa de fotogramas (por ejemplo a 25 FPS):
./live_cam_fb0.py --fps 25
```

---

## 🔄 Inicio Automático al Encender (Systemd Service)

Si deseas que la cámara funcione en modo quiosco o monitor continuo al arrancar el sistema:

```bash
sudo cp systemd/dsi-cam-preview.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable dsi-cam-preview.service
sudo systemctl start dsi-cam-preview.service
```

Para verificar el estado o detener el servicio:
```bash
sudo systemctl status dsi-cam-preview.service
sudo systemctl stop dsi-cam-preview.service
```

---

## 📁 Estructura del Repositorio

```text
rpi-ov5647-dsi-live-preview/
├── live_cam_fb0.py                 # Script ejecutable principal en Python
├── install.sh                      # Script de instalación y compilación
├── src/
│   ├── yuv2rgb.c                   # Código fuente C optimizado con SIMD/NEON
│   └── Makefile                    # Makefile para compilar libyuv2rgb.so
├── config/
│   ├── config.txt                  # Referencia de configuración de arranque
│   └── cmdline.txt                 # Parámetros del kernel
├── systemd/
│   └── dsi-cam-preview.service     # Unidad de servicio para arranque automático
├── .gitignore
└── README.md                       # Documentación técnica completa
```

---

## 📄 Licencia

Distribuido bajo la licencia MIT. Consulta `LICENSE` para más información.
