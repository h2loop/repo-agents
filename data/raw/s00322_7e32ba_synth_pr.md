## Title: Fix missing error propagation in LTE PHY GPIB calibration functions

### Summary
The LTE PHY simulation calibration code was silently ignoring GPIB communication failures. The `gpib_send()` function detected errors but only printed messages without returning status codes. The `calibration()` function had a void return type and continued execution even after GPIB command failures, leading to invalid test configurations being used silently downstream.

This patch implements proper error propagation throughout the GPIB control path. The `gpib_send()` function now returns an integer status (0 on success, -1 on failure), and the `calibration()` function checks each GPIB operation and propagates errors upstream. This ensures calibration failures are detected and can be handled by calling code, preventing silent failures during test equipment setup.

### Changes
- `openair1/SIMULATION/LTE_PHY/LTE_Configuration.c`: 
  - Modified `gpib_send()` to return `int` instead of `void`, returning -1 on GPIB errors and 0 on success
  - Modified `calibration()` to return `int` instead of `void`
  - Added error checking after every `gpib_send()` call in `calibration()`, returning -1 immediately on failure
  - This ensures GPIB communication failures are properly propagated instead of being silently ignored
- `openair1/SIMULATION/LTE_PHY/LTE_Configuration.h`: Updated function prototypes for `gpib_send()` and `calibration()` to reflect new return types

### Testing
- Verified compilation of the modified LTE PHY simulation module
- Error paths now properly trigger when GPIB equipment is unavailable or fails to respond
- Prevents silent failures during automated test calibration procedures