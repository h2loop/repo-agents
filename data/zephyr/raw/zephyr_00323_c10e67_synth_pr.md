## Title: Add Watchdog Feeding Around Potentially Long-Running Sensor Operations in STM32 DCMI Driver

### Summary
This PR addresses a potential watchdog timeout issue in the STM32 DCMI video driver. The `video_stm32_dcmi_set_fmt` function calls `video_set_format` and `video_estimate_fmt_size`, which may involve I2C communication or other time-consuming operations with the image sensor. These operations can take longer than the watchdog timeout period, especially in systems with aggressive watchdog configurations.

The fix adds `sys_watchdog_feed()` calls before and after the sensor-related `video_set_format` call to ensure the watchdog timer is serviced during these potentially long-running operations. This prevents premature watchdog resets while maintaining the driver's functionality.

### Changes
- `drivers/video/video_stm32_dcmi.c`: Added `sys_watchdog_feed()` calls before and after the `video_set_format()` invocation in `video_stm32_dcmi_set_fmt()` to prevent watchdog timeouts during sensor configuration.

### Testing
- Verified compilation with STM32 DCMI driver enabled.
- Confirmed no functional changes; driver behavior remains the same but with added watchdog protection.
- Tested on STM32H743-based board with OV2640 sensor; no watchdog resets observed during format setting operations.