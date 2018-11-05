
#include "stm32f0xx.h"
#define LEDPORT (GPIOC)
#define LED1 (8)
#define ENABLE_GPIO_CLOCK (RCC->AHBENR |= RCC_AHBENR_GPIOCEN)
#define _MODER    MODER
#define GPIOMODER (GPIO_MODER_MODER8_0)


void ms_delay(int ms)
{
    while (ms-- > 0) {
        volatile int x=500;
        while (x-- > 0)
            __asm("nop");
    }
}

//Alternates blue and green LEDs quickly
int main(void)
{
    ENABLE_GPIO_CLOCK;              // enable the clock to GPIO
    LEDPORT->_MODER |= GPIOMODER;   // set pins to be general purpose output
    for (;;) {
    ms_delay(500);
    LEDPORT->ODR ^= (1<<LED1);  // toggle diodes
    }

    return 0;
}
