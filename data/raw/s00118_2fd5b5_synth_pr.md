## Title: Fix unsafe direct access to PHY_vars_UE_g global structure

### Summary
The `measurcmd_display_phyta()` function in the telnet measurement server directly accessed the global `PHY_vars_UE_g[0][0]` structure without null checks. This unsafe access pattern could cause segmentation faults when the PHY layer is not initialized or during early system startup. The deprecated direct array access pattern lacked proper validation that the global structures were allocated and ready.

The fix adds multi-level null checks before dereferencing the UE pointer. If the PHY structure is not initialized, the function now prints a clear error message and returns gracefully instead of crashing.

### Changes
- `common/utils/telnetsrv/telnetsrv_5Gue_measurements.c`: Added null checks for `PHY_vars_UE_g`, `PHY_vars_UE_g[0]`, and the resulting `UE` pointer. Replaced direct array access with safe, validated access pattern. Added early return with user-friendly message "UE not initialized" when checks fail.

### Implementation Details
The validation follows a defensive programming approach: first verify the top-level global array exists, then verify the sub-array is allocated, and finally verify the UE instance pointer is valid before dereferencing. This three-tier check prevents crashes during initialization race conditions or when querying measurements before UE PHY is fully set up.

### Testing
- Verified telnet server starts without crashes when PHY layer is uninitialized
- Confirmed proper error message display via telnet interface during early boot
- Validated normal operation continues unchanged when PHY is properly initialized