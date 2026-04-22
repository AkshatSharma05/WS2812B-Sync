#ifndef WS2812B_DRIVER_H
#define WS2812B_DRIVER_H

/// INCLUDES
#include "stm32f1xx_hal.h"

/// DEFINES
#define WS2812B_NUM_LEDS        3

#define WS2812B_HI_VAL          30  // 0.6us
#define WS2812B_LO_VAL          15  // 0.3us

#define WS2812B_RST_CYCLES      100  //80us

#define WS2812B_BITS_PER_LED    24 // Three 8-bit channels

#define BITS_PER_LED            24

//The DMA buffer contains the Duty bits. The RST_CYCLES are also added to the buffer so they dont have to be manually passed. 
#define WS2812B_DMA_BUF_LEN ((WS2812B_NUM_LEDS * BITS_PER_LED) + WS2812B_RST_CYCLES)

typedef union{

    struct {
        
        uint8_t b;
        uint8_t r;
        uint8_t g;

    } color;

    uint32_t data;

} WS2812B_LED_ATTR;

/// VARIABLES
extern WS2812B_LED_ATTR WS2812B_LED_DATA[WS2812B_NUM_LEDS];
extern uint16_t WS2812B_DMA_BUF[WS2812B_DMA_BUF_LEN];

//volatile is used because this flag will be changed by the DMA only. So, it might get lost in optimization by the compiler if not volatile.
extern volatile uint8_t WS2812B_DMA_COMPLETE_FLAG;

/// FUNCTIONS
void                WS2812B_BindTIM(TIM_HandleTypeDef *htim, uint32_t channel);
HAL_StatusTypeDef   WS2812B_Init();
void                WS2812B_SetColor(uint8_t index, uint8_t r, uint8_t g, uint8_t b);
HAL_StatusTypeDef   WS2812B_Update();
void                WS2812B_Callback();

#endif