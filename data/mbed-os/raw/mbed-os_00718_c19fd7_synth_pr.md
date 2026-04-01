## Title: Fix signed/unsigned comparison warning in HAL_FDCAN_ConfigGlobalFilter

### Summary
This PR resolves a signed/unsigned integer comparison warning in the `HAL_FDCAN_ConfigGlobalFilter` function within the STM32U5 HAL driver. The issue occurs when comparing the `hfdcan->State` (of type `uint32_t`) against the enum value `HAL_FDCAN_STATE_READY`, which is treated as a signed integer in some contexts. This mismatch triggers compiler warnings and can lead to unexpected behavior on certain platforms.

The fix explicitly casts `HAL_FDCAN_STATE_READY` to `uint32_t` to match the type of `hfdcan->State`, ensuring consistent and well-defined comparison.

### Changes
- `targets/TARGET_STM/TARGET_STM32U5/STM32Cube_FW/STM32U5xx_HAL_Driver/stm32u5xx_hal_fdcan.c`: Cast `HAL_FDCAN_STATE_READY` to `uint32_t` in the state check condition.

### Testing
- Verified compilation with GCC and IAR compilers; warning is resolved.
- Confirmed functional correctness with STM32U5-based FDCAN communication tests.