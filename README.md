# WS2812B-Driver

A WS2812B LED driver for the **STM32F102** (48 MHz). Drives an arbitrary-length strip over a single wire using **hardware PWM + DMA** — no blocking loops, no CPU intervention during transmission.

---

## How It Works

**Protocol**

<img width="911" height="114" alt="image" src="https://github.com/user-attachments/assets/9b00c93d-301e-4850-98c4-3a7060da9a1c" />



The WS2812B protocol encodes each bit as a fixed-width 1.25 µs pulse with a variable duty cycle:

| Bit | High | Low |
|-----|------|-----|
| `1` | 0.6 µs | 0.65 µs |
| `0` | 0.3 µs | 0.95 µs |
| Reset | — | > 50 µs |


**Timer config** 

 f = 1/T = 1/(1.25 * 10^-6)  = 800000 = **800 kHz** PWM Frequency

f(pwm) = F(clk)/(ARR+1)(PSC+1)

```
f = 800 kHz  →  (ARR+1)(PSC+1) = 60
PSC = 0,  ARR = 59
```

CCR values are precomputed as:

```c
#define WS2812B_HI_VAL  30   // 0.6/1.25 * 60 ≈ 29
#define WS2812B_LO_VAL  15   // 0.3/1.25 * 60 ≈ 14
```

The reset pulse is appended directly to the DMA buffer (64 zero-valued slots ≈ 80 µs), so no manual delay is needed after a frame.

---

## DMA Buffer Layout

```c
#define WS2812B_RST_CYCLES   64   // 80 µs reset
#define BITS_PER_LED         24   // GRB, MSB first
#define DMA_BUF_LEN          ((NUM_LEDS * BITS_PER_LED) + WS2812B_RST_CYCLES)
```

Each entry in `WS2812B_DMA_BUF[]` is a `uint32_t` CCR value (`HI_VAL` or `LO_VAL`). The DMA is configured **Memory → Peripheral, Word (32-bit)** to match the width of `TIMx_CCRx`.

---

## LED Color Layout

Colors are stored in a union that mirrors the GRB wire order (MSB first):

```c
typedef union {
    struct { uint8_t b; uint8_t r; uint8_t g; } color;
    uint32_t data;
} WS2812B_LED_ATTR;
```

The struct ordering (B, R, G in memory) places G in the most-significant byte of `data`, so iterating bits 23 → 0 naturally produces the G7…G0, R7…R0, B7…B0 sequence required by the protocol.

---

## Driver API

```c
// Set a single LED's color (buffered)
void WS2812B_SetColor(uint16_t index, uint8_t r, uint8_t g, uint8_t b);

// Flush buffer to LEDs via DMA (non-blocking, returns HAL_BUSY if previous transfer is in flight)
HAL_StatusTypeDef WS2812B_Update(void);

// Call from HAL_TIM_PWM_PulseFinishedCallback
void WS2812B_Callback(void);
```

`WS2812B_Update()` guards against double-triggering via a `volatile` flag set by the DMA complete callback.

---


## Verification of Signals using an Oscilloscope

<img width="1600" height="1200" alt="image" src="https://github.com/user-attachments/assets/7a0b6497-d554-441b-a666-d255f82b234c" />

The 24-bit data can be observed in the above image. 

<img width="1600" height="1200" alt="image" src="https://github.com/user-attachments/assets/16fb52b0-df05-4d06-bbbb-1852be22cfd4" />

To further validate bit-level correctness, a test pattern was transmitted by setting the blue channel to 10 (binary: 00001010) while keeping other channels constant.

---

## Demo Effect

The included main loop drives a **sine-wave brightness envelope** over a **rainbow color wheel**, creating a traveling wave across the strip:

```c
// phase_step controls spatial spread; angle controls wave position
float local_angle = angle + (i * phase_step);
uint8_t brightness = (uint8_t)((sinf(local_angle) + 1.0f) * 10.0f);
Wheel(hue + i, &r, &g, &b);  // rainbow color per LED
```

`HAL_Delay(10)` sets frame rate; `angle += 0.05f` controls wave speed; `hue++` drifts the rainbow.


---

## Toolchain

- **STM32CubeMX** — clock peripheral config
- **arm-none-eabi-gcc** + **make** — build
- **OpenOCD** — flash and debug

```bash
make -j16 DEBUG=1 -f STM32Make.make
openocd -f openocd.cfg -c "program build/debug/ws2812.elf verify reset exit"
```

---

## Notes

Timing is tuned for a **48 MHz HCLK**. Changing the system clock requires recalculating ARR and CCR values.
