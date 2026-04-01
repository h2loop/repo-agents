## Title: Add missing mutex lock in HAL_I2S_Init to prevent race conditions

### Summary
This PR fixes a potential race condition in the STM32F4 HAL I2S driver by adding missing mutex locking in the `HAL_I2S_Init` function. Unlike other HAL drivers (e.g., SPI), the I2S initialization function was not acquiring a lock before modifying shared resources, which could lead to data corruption or undefined behavior in multi-threaded environments.

The fix follows the same locking pattern used in other STM32 HAL drivers, where `__HAL_LOCK()` is called at the beginning of the initialization function and `__HAL_UNLOCK()` is called before every return point to ensure proper synchronization.

### Changes
- `targets/TARGET_STM/TARGET_STM32F4/STM32Cube_FW/STM32F4xx_HAL_Driver/stm32f4xx_hal_i2s.c`: 
  - Added `__HAL_LOCK(hi2s)` after parameter validation at the start of `HAL_I2S_Init`
  - Added `__HAL_UNLOCK(hi2s)` before error return paths
  - Added `__HAL_UNLOCK(hi2s)` before the final successful return

### Testing
- Verified the lock/unlock pattern matches other HAL drivers (SPI, UART)
- Confirmed no functional changes in normal operation
- Checked all return paths properly release the lock