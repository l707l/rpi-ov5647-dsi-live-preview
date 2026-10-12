#!/usr/bin/env python3
"""
Live Camera Preview directly onto DSI screen via /dev/fb0 (KMS Framebuffer).
Hardware: Raspberry Pi 3B+
Camera: OV5647 CSI (5 MP)
Display: DSI 800x480

Corrected for Broadcom ISP 64-byte row alignment:
- Visible resolution: 800x480
- Hardware ISP Y-stride: 832 bytes (13 * 64)
- Hardware ISP UV-stride: 416 bytes (13 * 32)
- Frame size: 599,040 bytes

Achieves full screen live video over TTY at 30 FPS without distortion or green tint.
Clean exit on Ctrl+C.
"""

import os
import sys
import time
import mmap
import ctypes
import signal
import argparse
import subprocess

WIDTH = 800
HEIGHT = 480
Y_STRIDE = 832
UV_STRIDE = 416
FRAME_SIZE = Y_STRIDE * HEIGHT * 3 // 2  # 599,040 bytes
FB_SIZE = WIDTH * HEIGHT * 2             # 768,000 bytes

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SO_PATH = os.path.join(SCRIPT_DIR, 'libyuv2rgb.so')
if not os.path.exists(SO_PATH):
    SO_PATH = '/home/v/libyuv2rgb.so'

# Auto-compile C acceleration library if not found
if not os.path.exists(SO_PATH):
    c_source = """
    #include <stdint.h>
    void yuv420_to_rgb565(const uint8_t *yuv, uint16_t *rgb565,
                          int visible_w, int visible_h,
                          int y_stride, int uv_stride) {
        const uint8_t *Y_plane = yuv;
        const uint8_t *U_plane = yuv + (y_stride * visible_h);
        const uint8_t *V_plane = U_plane + (uv_stride * (visible_h / 2));

        for (int y = 0; y < visible_h; y++) {
            int uv_y = y >> 1;
            const uint8_t *y_row = Y_plane + y * y_stride;
            const uint8_t *u_row = U_plane + uv_y * uv_stride;
            const uint8_t *v_row = V_plane + uv_y * uv_stride;
            uint16_t *dst_row = rgb565 + y * visible_w;

            for (int x = 0; x < visible_w; x += 2) {
                int uv_x = x >> 1;
                int u = (int)u_row[uv_x] - 128;
                int v = (int)v_row[uv_x] - 128;

                int r_term = (v * 1436) >> 10;
                int g_term = (u * 352 + v * 731) >> 10;
                int b_term = (u * 1815) >> 10;

                int y0 = (int)y_row[x];
                int r0 = y0 + r_term; if (r0 < 0) r0 = 0; else if (r0 > 255) r0 = 255;
                int g0 = y0 - g_term; if (g0 < 0) g0 = 0; else if (g0 > 255) g0 = 255;
                int b0 = y0 + b_term; if (b0 < 0) b0 = 0; else if (b0 > 255) b0 = 255;
                dst_row[x] = (uint16_t)(((r0 >> 3) << 11) | ((g0 >> 2) << 5) | (b0 >> 3));

                int y1 = (int)y_row[x + 1];
                int r1 = y1 + r_term; if (r1 < 0) r1 = 0; else if (r1 > 255) r1 = 255;
                int g1 = y1 - g_term; if (g1 < 0) g1 = 0; else if (g1 > 255) g1 = 255;
                int b1 = y1 + b_term; if (b1 < 0) b1 = 0; else if (b1 > 255) b1 = 255;
                dst_row[x + 1] = (uint16_t)(((r1 >> 3) << 11) | ((g1 >> 2) << 5) | (b1 >> 3));
            }
        }
    }
    void yuv420_to_fb16(const uint8_t *yuv, uint16_t *fb,
                        int visible_w, int visible_h,
                        int y_stride, int uv_stride) __attribute__((alias("yuv420_to_rgb565")));
    """
    tmp_c = '/tmp/yuv2rgb.c'
    with open(tmp_c, 'w') as f:
        f.write(c_source)
    subprocess.check_call(['gcc', '-O3', '-fPIC', '-shared', tmp_c, '-o', SO_PATH])

lib = ctypes.CDLL(SO_PATH)
lib.yuv420_to_rgb565.argtypes = [
    ctypes.POINTER(ctypes.c_uint8),
    ctypes.POINTER(ctypes.c_uint16),
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int
]

def set_cursor_blink(enabled):
    blink_path = '/sys/class/graphics/fbcon/cursor_blink'
    if os.path.exists(blink_path):
        try:
            with open(blink_path, 'w') as f:
                f.write('1' if enabled else '0')
        except PermissionError:
            pass
    # ANSI escape sequence to show/hide cursor
    sys.stdout.write('\033[?25h' if enabled else '\033[?25l')
    sys.stdout.flush()

def main():
    parser = argparse.ArgumentParser(description="Live camera preview to DSI screen via /dev/fb0")
    parser.add_argument("--vflip", action="store_true", help="Voltear imagen verticalmente")
    parser.add_argument("--hflip", action="store_true", help="Voltear imagen horizontalmente")
    parser.add_argument("--rotation", type=int, choices=[0, 180], default=0, help="Rotar imagen (0 o 180)")
    parser.add_argument("--fps", type=int, default=30, help="Tasa de fotogramas por segundo (default: 30)")
    args = parser.parse_args()

    fb_path = '/dev/fb0'
    if not os.path.exists(fb_path):
        print(f"[!] Error: {fb_path} no encontrado.")
        sys.exit(1)

    print(f"[*] Abriendo {fb_path} (Resolución visible: {WIDTH}x{HEIGHT} RGB565)...")
    print(f"[*] Alineación ISP de hardware: Stride Y={Y_STRIDE}B, Stride UV={UV_STRIDE}B ({FRAME_SIZE} B/frame)")

    fb_file = open(fb_path, 'r+b')
    fb_mem = mmap.mmap(fb_file.fileno(), FB_SIZE, mmap.MAP_SHARED, mmap.PROT_WRITE)
    c_fb = (ctypes.c_uint16 * (WIDTH * HEIGHT)).from_buffer(fb_mem)

    yuv_buf = bytearray(FRAME_SIZE)
    c_yuv = (ctypes.c_uint8 * FRAME_SIZE).from_buffer(yuv_buf)
    yuv_view = memoryview(yuv_buf)

    print(f"[*] Iniciando rpicam-vid (OV5647 CSI @ {args.fps} FPS)...")
    cmd = [
        'rpicam-vid',
        '-t', '0',
        '--width', str(WIDTH),
        '--height', str(HEIGHT),
        '--framerate', str(args.fps),
        '--codec', 'yuv420',
        '-o', '-',
        '--nopreview'
    ]
    if args.vflip:
        cmd.append('--vflip')
    if args.hflip:
        cmd.append('--hflip')
    if args.rotation:
        cmd.extend(['--rotation', str(args.rotation)])

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=FRAME_SIZE * 2)

    running = True

    def sig_handler(sig, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    set_cursor_blink(False)
    print("\n" + "="*60)
    print("  [+] VIDEO EN VIVO ACTIVO EN PANTALLA DSI (FULLSCREEN)")
    print("      Presiona Ctrl+C en cualquier momento para salir limpiamente.")
    print("="*60 + "\n")

    total_frames = 0
    fps_frames = 0
    t_start = time.time()
    t_fps = t_start

    try:
        while running and proc.poll() is None:
            bytes_read = 0
            while bytes_read < FRAME_SIZE and running:
                n = proc.stdout.readinto(yuv_view[bytes_read:])
                if not n:
                    break
                bytes_read += n

            if bytes_read < FRAME_SIZE:
                break

            lib.yuv420_to_rgb565(c_yuv, c_fb, WIDTH, HEIGHT, Y_STRIDE, UV_STRIDE)
            total_frames += 1
            fps_frames += 1

            now = time.time()
            if now - t_fps >= 1.0:
                fps = fps_frames / (now - t_fps)
                sys.stdout.write(f"\r[*] Transmitiendo a pantalla DSI: {fps:.1f} FPS | Fotogramas totales: {total_frames} ")
                sys.stdout.flush()
                fps_frames = 0
                t_fps = now

    except KeyboardInterrupt:
        pass
    finally:
        set_cursor_blink(True)
        print("\n\n[*] Deteniendo proceso de cámara...")
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

        del c_fb
        del c_yuv
        fb_mem.close()
        fb_file.close()

        total_time = time.time() - t_start
        avg_fps = total_frames / total_time if total_time > 0 else 0
        print(f"[+] Salida limpia completada. {total_frames} fotogramas proyectados en {total_time:.1f}s (Media: {avg_fps:.1f} FPS).")

if __name__ == '__main__':
    main()
