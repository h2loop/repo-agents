## Title: Fix heap buffer overflow in coresight TMC ETR driver

### Summary
This PR fixes a heap buffer overflow vulnerability in the `tmc_etr_hw_read` function within the coresight TMC ETR driver. The issue occurred due to missing bounds validation of hardware-provided read (`rrp`) and write (`rwp`) pointers, which could be manipulated to point outside the allocated buffer bounds. This could lead to out-of-bounds memory access when calculating buffer offsets and lengths.

The fix adds proper validation to ensure both `rrp` and `rwp` pointers are within the valid buffer range before use, and includes additional bounds checking for the calculated buffer parameters. Error logging has been added to report out-of-bounds conditions, and the buffer length is clamped to prevent overflow.

### Changes
- `drivers/coresight/coresight_tmc_etr.c`: Added bounds checking for `rrp` and `rwp` pointers in `tmc_etr_hw_read`. Added `inttypes.h` include for format specifiers. Added validation logic to ensure pointers are within buffer bounds and prevent buffer overflow conditions.
- `include/nuttx/coresight/coresight_tmc.h`: No structural changes, but the fix ensures safer usage of the buffer management fields in the `coresight_tmc_dev_s` structure.

### Testing
- Verified compilation with NuttX build system
- Tested with various buffer pointer scenarios to ensure proper bounds checking
- Confirmed error logging works correctly when out-of-bounds conditions are detected