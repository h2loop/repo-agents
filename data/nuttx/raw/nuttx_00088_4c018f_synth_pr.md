## Title: Fix error handling in nrf52_bringup to prevent resource leaks

### Summary
This PR addresses a resource leak in the `nrf52_bringup` function where errors during initialization (e.g., procfs mount or IEEE802154 radio setup) were only logged, without returning an error code or cleaning up allocated resources. This could lead to resource exhaustion or unexpected behavior on repeated initialization attempts.

The fix ensures that any failure during the bring-up process is properly reported by returning the appropriate error code, allowing the calling code to handle the failure correctly.

### Changes
- `boards/arm/nrf52/nrf9160-dk-nrf52/src/nrf52_bringup.c`:
  - Added `#include <errno.h>` for error code definitions.
  - Modified error paths to return the error code (`ret`) instead of continuing execution.
  - Removed unused `ret` variable at the end of the function.
  - Fixed typo in log message ("IEE802154" → "IEEE802154").

### Impact
Improves system reliability by ensuring proper error propagation and preventing potential resource leaks during board initialization.