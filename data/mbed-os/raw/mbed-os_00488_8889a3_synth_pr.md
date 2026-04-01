## Title: Fix I2S DMA Callback Deadlock by Releasing Lock Before DMA Start

### Summary
This PR resolves a potential deadlock in the STM32WL I2S driver that occurs when user callbacks are invoked from DMA interrupt context while the I2S handle lock is still held. The issue arises because the `__HAL_LOCK` mechanism is not released before starting DMA transfers, but callbacks (like `HAL_I2S_RxHalfCpltCallback`) may attempt to acquire the same lock or call other HAL functions that do, leading to a deadlock.

The fix follows the pattern used in more mature STM32 families (like F4), where the lock is released before initiating the DMA transfer to prevent callback-induced deadlocks. This ensures that user callbacks can safely interact with the HAL without causing system hangs.

### Changes
- **targets/TARGET_STM/TARGET_STM32WL/STM32Cube_FW/STM32WLxx_HAL_Driver/stm32wlxx_hal_i2s.c**:
  - Moved `__HAL_UNLOCK(hi2s)` before DMA start in both `HAL_I2S_Transmit_DMA` and `HAL_I2S_Receive_DMA`
  - Removed redundant unlock calls in error paths to maintain correct lock semantics

### Why
Without this fix, any user implementation of I2S callbacks that attempts to use HAL APIs can cause a system deadlock due to inconsistent lock acquisition ordering. This is a critical concurrency issue that affects real-time performance and system stability.