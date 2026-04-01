## Title: Fix NULL pointer dereference vulnerabilities in STM32G4 LL TIM functions

### Summary
This PR addresses multiple NULL pointer dereference vulnerabilities in the STM32G4 Low-Level Timer (LL TIM) driver functions. The affected functions (`LL_TIM_Init`, `LL_TIM_ENCODER_Init`, `LL_TIM_HALLSENSOR_Init`, `LL_TIM_BDTR_Init`, and output compare configuration functions) were missing NULL pointer checks on their initialization structure parameters, which could lead to crashes or undefined behavior if called with NULL inputs.

The issue was identified during a security audit of the STM32G4 HAL driver code. While these functions are typically called with valid structures in normal operation, adding explicit NULL checks improves robustness and prevents potential crashes in edge cases or when used in more complex configurations.

### Changes
- Added NULL pointer validation for all initialization structure parameters in LL TIM functions
- Functions now return `ERROR` immediately if any initialization structure parameter is NULL
- Affected files:
  - `targets/TARGET_STM/TARGET_STM32G4/STM32Cube_FW/STM32G4xx_HAL_Driver/stm32g4xx_ll_tim.c`

### Testing
- Verified that all modified functions properly handle NULL inputs
- Confirmed that normal operation with valid structures remains unchanged
- No functional changes to existing behavior when valid parameters are provided