## Title: Fix resource leak in ESP32-S3 dedicated GPIO and button initialization

### Summary
This PR addresses two resource leak issues in the ESP32-S3 board support package. First, the `esp_dedic_gpio_new_bundle` function did not properly clean up allocated resources when `register_driver` failed, leading to memory and GPIO resource leaks. Second, the button initialization in `esp32s3_bringup.c` could leak file descriptors if the lower-half button driver failed to initialize, as the file descriptor was opened but never closed on error paths.

The changes ensure proper cleanup of dedicated GPIO resources on registration failure and prevent file descriptor leaks during button driver initialization by restructuring error handling to use goto-based cleanup patterns.

### Changes
- `arch/xtensa/src/common/espressif/esp_dedic_gpio.c`: Added proper resource cleanup in `esp_dedic_gpio_new_bundle` when `register_driver` fails, including decrementing references, releasing occupied masks, disabling clock if needed, and freeing private data.
- `boards/xtensa/esp32s3/esp32s3-devkit/src/esp32s3_gpio.c`: Added error checking for `esp_dedic_gpio_new_bundle` return value and proper error handling to prevent resource leaks during GPIO initialization.

### Testing
- Verified successful GPIO initialization and driver registration on ESP32-S3-DevKit
- Confirmed proper cleanup when driver registration fails through code inspection
- Tested button functionality and initialization error paths