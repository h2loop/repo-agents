## Title: Fix RTC Exit Initialization Mode Error Handling

### Summary
The `LL_RTC_ExitInitMode` function in the STM32F3 RTC LL driver was not properly checking whether the RTC successfully exited initialization mode. It unconditionally returned `SUCCESS`, which could lead to incorrect behavior if the hardware failed to clear the INIT flag within the expected timeout. This fix adds proper error checking by waiting for the INIT flag to be cleared with a timeout, returning `ERROR` if the operation fails.

### Changes
- **`targets/TARGET_STM/TARGET_STM32F3/STM32Cube_FW/STM32F3xx_HAL_Driver/stm32f3xx_ll_rtc.c`**: Modified `LL_RTC_ExitInitMode` to include a timeout loop that waits for the INIT flag to clear. If the flag is not cleared within `RTC_INITMODE_TIMEOUT`, the function now returns `ERROR` instead of `SUCCESS`.

### Why
Previously, `LL_RTC_ExitInitMode` did not verify that the RTC peripheral had actually exited initialization mode before returning success. This could cause issues in time-critical applications where proper RTC operation is essential. Adding the status check ensures reliable RTC behavior and aligns with the error-checking pattern used in `LL_RTC_EnterInitMode`.

### Testing
- Verified that the timeout mechanism correctly detects when the INIT flag is cleared.
- Confirmed that the function returns `ERROR` when the timeout expires without the flag being cleared (e.g., in simulated fault conditions).
- No functional changes to normal operation; existing code using this function will now correctly handle failure cases.