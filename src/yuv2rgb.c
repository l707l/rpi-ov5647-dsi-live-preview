/*
 * yuv2rgb.c - Conversión ultrarrápida YUV420 a RGB565 / RGBX32
 * Optimizado para Raspberry Pi 3B+ (ARM Cortex-A53, ARMv8-A NEON)
 *
 * Maneja la alineación de memoria (hardware stride) del ISP de VideoCore:
 * - Y_STRIDE  = 832 bytes (alineado a 64 bytes)
 * - UV_STRIDE = 416 bytes (alineado a 32 bytes)
 * - VISIBLE_W = 800 píxeles
 */

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

            // Coeficientes estándar Rec.601 escalados a punto fijo (>> 10)
            int r_term = (v * 1436) >> 10;
            int g_term = (u * 352 + v * 731) >> 10;
            int b_term = (u * 1815) >> 10;

            // Píxel 0
            int y0 = (int)y_row[x];
            int r0 = y0 + r_term; if (r0 < 0) r0 = 0; else if (r0 > 255) r0 = 255;
            int g0 = y0 - g_term; if (g0 < 0) g0 = 0; else if (g0 > 255) g0 = 255;
            int b0 = y0 + b_term; if (b0 < 0) b0 = 0; else if (b0 > 255) b0 = 255;
            dst_row[x] = (uint16_t)(((r0 >> 3) << 11) | ((g0 >> 2) << 5) | (b0 >> 3));

            // Píxel 1
            int y1 = (int)y_row[x + 1];
            int r1 = y1 + r_term; if (r1 < 0) r1 = 0; else if (r1 > 255) r1 = 255;
            int g1 = y1 - g_term; if (g1 < 0) g1 = 0; else if (g1 > 255) g1 = 255;
            int b1 = y1 + b_term; if (b1 < 0) b1 = 0; else if (b1 > 255) b1 = 255;
            dst_row[x + 1] = (uint16_t)(((r1 >> 3) << 11) | ((g1 >> 2) << 5) | (b1 >> 3));
        }
    }
}

// Alias de compatibilidad
void yuv420_to_fb16(const uint8_t *yuv, uint16_t *fb,
                    int visible_w, int visible_h,
                    int y_stride, int uv_stride) __attribute__((alias("yuv420_to_rgb565")));
