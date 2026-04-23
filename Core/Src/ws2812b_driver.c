//INCLUDES
#include "ws2812b_driver.h"

//VARIABLES
// extern TIM_HandleTypeDef WS2812B_TIM;
static TIM_HandleTypeDef *ws2812b_tim = NULL;
static uint32_t ws2812b_channel;

WS2812B_LED_ATTR WS2812B_LED_DATA[WS2812B_NUM_LEDS];
uint16_t WS2812B_DMA_BUF[WS2812B_DMA_BUF_LEN];

volatile uint8_t WS2812B_DMA_COMPLETE_FLAG;

//FUNCTION DECLARATIONS
void WS2812B_BindTIM(TIM_HandleTypeDef *htim, uint32_t channel)
{
    ws2812b_channel = channel;
    ws2812b_tim = htim;
}

HAL_StatusTypeDef WS2812B_Init(){

    //Init PWM
    HAL_StatusTypeDef halStatus = HAL_TIM_PWM_Init(ws2812b_tim);

    //Clear DMA Buffer
    for( uint16_t bufIndex = 0; bufIndex < WS2812B_DMA_BUF_LEN; bufIndex++ ){
        WS2812B_DMA_BUF[bufIndex] = 0;
    }

    //Set the DMA Ready Flag
    WS2812B_DMA_COMPLETE_FLAG = 1;

    return halStatus;

}

void WS2812B_SetColor( uint8_t index, uint8_t r, uint8_t g, uint8_t b ){

    WS2812B_LED_DATA[index].color.r = r;
    WS2812B_LED_DATA[index].color.g = g;
    WS2812B_LED_DATA[index].color.b = b;

}

HAL_StatusTypeDef WS2812B_Update(){

    //Check if previous DMA Transfer is complete
    if ( !WS2812B_DMA_COMPLETE_FLAG ){
        return HAL_BUSY;
    }

    uint16_t bufIndex = 0;

    //Fill the DMA buffer with the LED Data
    for ( uint16_t ledIndex = 0; ledIndex < WS2812B_NUM_LEDS; ledIndex++ ){
        //Looping through each bit of data
        for( uint8_t bitIndex = 0; bitIndex < WS2812B_BITS_PER_LED; bitIndex++ ){
            
            if( WS2812B_LED_DATA[ledIndex].data & 1 << (WS2812B_BITS_PER_LED - 1 - bitIndex) ){
             
                WS2812B_DMA_BUF[bufIndex] = WS2812B_HI_VAL;
            
            } else{
                
                WS2812B_DMA_BUF[bufIndex] = WS2812B_LO_VAL;
            
            }

            bufIndex++;
        }
    }

    // When we reset the DMA buffer to zero, the remaining part of buffer is already zero -> reset

    //Start attempting to send the PWM data to Timer via DMA
    HAL_StatusTypeDef halStatus = HAL_TIM_PWM_Start_DMA(ws2812b_tim, ws2812b_channel,
                                                        (uint32_t *) WS2812B_DMA_BUF, 
                                                        (uint16_t) WS2812B_DMA_BUF_LEN);

    if (halStatus == HAL_OK){
        WS2812B_DMA_COMPLETE_FLAG = 0;
    }

    return halStatus;
}


//Called on Pulse Finish Function of DMA
void WS2812B_Callback(){
    HAL_TIM_PWM_Stop_DMA(ws2812b_tim, ws2812b_channel);
    WS2812B_DMA_COMPLETE_FLAG = 1;
}