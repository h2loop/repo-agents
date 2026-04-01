## Title: Fix race condition in ADC register access for STM32F0

### Summary
This PR addresses a potential race condition in the STM32F0 ADC low-level driver when accessing the ADC control register (`ADCx->CR`). Previously, the code used `MODIFY_REG` with a mask that included bits with hardware property "rs" (read-set), which could inadvertently clear other bits being set by concurrent operations. This could lead to unexpected behavior in multi-threaded or interrupt-driven environments where multiple ADC control bits are manipulated concurrently.

The fix replaces `MODIFY_REG` with `SET_BIT` for the ADC enable (`ADEN`), disable (`ADDIS`), and calibration (`ADCAL`) bits, ensuring that only the target bit is set without affecting other bits in the register. This change aligns with the hardware's "rs" property semantics and prevents race conditions.

### Changes
- `targets/TARGET_STM/TARGET_STM32F0/STM32Cube_FW/STM32F0xx_HAL_Driver/stm32f0xx_ll_adc.h`:
  - Replaced `MODIFY_REG` with `SET_BIT` in `LL_ADC_Enable`, `LL_ADC_Disable`, and `LL_ADC_StartCalibration` functions.
  - Updated comments to reflect the change in register access strategy for bits with "rs" property.

### Testing
- Verified compilation and basic ADC functionality in a test application.
- Confirmed that register bits are set correctly without clearing other bits through inspection of generated code.