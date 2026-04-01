## Title: Fix off-by-one error in LSM6DSV320X accelerometer mode handling

### Summary
This PR fixes an off-by-one error in the LSM6DSV320X accelerometer driver that occurred when mapping hardware mode values to ODR (Output Data Rate) array indices. The `lsm6dsv320x_accel_get_mode` function was returning mode values (0, 1, 3, 4, 5, 6, 7) that didn't align with the ODR map array indices (0, 1, 2), causing potential out-of-bounds array access in `lsm6dsv320x_freq_to_odr_val`.

The issue was resolved by introducing a mapping function `lsm6dsv320x_mode_to_odr_index()` that correctly translates hardware mode values to valid ODR map indices, and adding proper bounds checking to prevent invalid array access.

### Changes
- `drivers/sensor/st/lsm6dsvxxx/lsm6dsv320x.c`: 
  - Added `lsm6dsv320x_mode_to_odr_index()` function to map hardware modes to ODR array indices
  - Modified `lsm6dsv320x_freq_to_odr_val()` to use the new mapping function and validate mode indices
  - Updated logging to show both hardware mode and ODR index for debugging

### Testing
Verified that accelerometer frequency configuration works correctly across all supported modes without array bounds violations. The fix maintains backward compatibility while preventing potential crashes or incorrect ODR settings.