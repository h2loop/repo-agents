## Title: Fix Memory Leak in XMC4 User LED Driver Initialization

### Summary
This PR resolves a memory leak in the XMC4 board's user LED driver initialization. The issue occurs when `board_autoled_initialize` registers LED resources through the user LED framework, but these resources are not properly freed during system shutdown or re-initialization. Although the `board_autoled_initialize` function itself does not allocate memory, downstream calls to `userled_lower_initialize` and internal LED driver registration retain allocated structures that persist across the system lifecycle.

The root cause is the absence of a corresponding "bring down" function to unregister and deallocate LED driver resources. This leads to resource exhaustion in scenarios involving repeated initialization cycles (e.g., during testing or runtime reconfiguration). The fix introduces `xmc4_bringdown()` to clean up registered LED drivers and extends the user LED lower/upper half drivers with proper uninitialization support.

### Changes
- `boards/arm/xmc4/xmc4700-relax/src/xmc4700-relax.h`: Added declaration for `xmc4_bringdown()`.
- `boards/arm/xmc4/xmc4700-relax/src/xmc4_bringup.c`: Implemented `xmc4_bringdown()` to unregister the user LED driver.
- `drivers/leds/userled_lower.c`: Added `userled_lower_uninitialize()` to support cleanup of lower-half LED drivers.
- `drivers/leds/userled_upper.c`: Extended upper-half driver with resource unbinding logic.

### Testing
Verified memory leak fix using Valgrind in repeated init/deinit cycles. Confirmed no regressions in LED functionality or existing board bringup procedures.