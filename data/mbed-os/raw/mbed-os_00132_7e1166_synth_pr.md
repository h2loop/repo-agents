## Title: Fix race condition in FLEXIO I2C master baud rate and transfer count functions

### Summary
This PR resolves a race condition in the `FLEXIO_I2C_MasterSetBaudRate` and `FLEXIO_I2C_MasterSetTransferCount` functions that could occur when these functions were called concurrently with interrupt handlers or other threads accessing the same hardware registers. The issue was caused by direct, unsynchronized access to the `TIMCMP` register, which could lead to data corruption or unexpected behavior.

The fix implements critical section protection by disabling interrupts during register modifications and re-enabling them afterward, using the standard `DisableGlobalIRQ()` and `EnableGlobalIRQ()` functions from the MCUXpresso SDK.

### Changes
- **targets/TARGET_Freescale/TARGET_MCUXpresso_MCUS/TARGET_K82F/drivers/fsl_flexio_i2c_master.c**: 
  - Added `#include "fsl_common.h"` for interrupt control functions
  - Wrapped register access in `FLEXIO_I2C_MasterSetBaudRate` with interrupt disable/enable
  - Wrapped register access in `FLEXIO_I2C_MasterSetTransferCount` with interrupt disable/enable
  - Added local variable `regPrimask` to save and restore interrupt state

### Testing
Verified that I2C functionality remains correct after the change. The race condition fix ensures thread/interrupt safety without altering the functional behavior of the I2C master driver.