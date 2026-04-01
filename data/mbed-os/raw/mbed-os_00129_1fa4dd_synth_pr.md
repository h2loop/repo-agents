## Title: Add missing parameter validation in UART stop mode functions

### Summary
This PR fixes a potential null pointer dereference in the `HAL_UARTEx_EnableStopMode` and `HAL_UARTEx_DisableStopMode` functions by adding proper input parameter validation. Previously, these functions did not check if the `huart` handle was NULL before using it, which could lead to a crash or undefined behavior if called with invalid parameters.

The fix follows the standard error handling pattern used throughout the STM32 HAL drivers, where input parameters are validated at the beginning of each function. A check for `huart == NULL` has been added to both functions, returning `HAL_ERROR` immediately if the condition is met.

### Changes
- `targets/TARGET_STM/TARGET_STM32L5/STM32Cube_FW/STM32L5xx_HAL_Driver/stm32l5xx_hal_uart_ex.c`: 
  - Added NULL pointer check for `huart` parameter in `HAL_UARTEx_EnableStopMode`
  - Added NULL pointer check for `huart` parameter in `HAL_UARTEx_DisableStopMode`

### Testing
- Verified that functions now properly return `HAL_ERROR` when called with NULL handle
- Confirmed that normal operation is unaffected when valid handle is provided
- Checked consistency with other UART HAL functions that follow the same parameter validation pattern