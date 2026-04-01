## Title: Fix cross-layer parameter mismatch in nr_start_if interface initialization

### Summary
Fix a critical parameter mismatch in the RU interface initialization where `nr_start_if()` was incorrectly invoked with a NULL gNB pointer, causing cross-layer coordination failures between PHY, MAC, and RRC layers. The function signature requires a valid `struct PHY_VARS_gNB_s*` to access gNB configuration and state information needed for proper southbound interface initialization and parameter synchronization across layers. Passing NULL prevented proper propagation of cell configuration, bandwidth, and timing parameters, leading to inconsistent operation downstream.

### Changes
- `executables/nr-ru.c`: Corrected the function call at line 1090 in `ru_thread()` from `ru->nr_start_if(ru, NULL)` to `ru->nr_start_if(ru, gNB)`

### Implementation Details
The `nr_start_if` function expects the gNB pointer to initialize the interface with proper cross-layer awareness. The NULL parameter caused the function to operate without access to critical gNB state, resulting in mismatched parameter interpretation between RU, PHY, MAC, and RRC layers. This fix ensures proper parameter propagation and consistent initialization behavior.

### Testing
- Verified gNB configuration parameters are correctly accessible within `nr_start_if`
- Confirmed proper cross-layer parameter synchronization during RU initialization
- No regressions observed in single-layer and multi-layer configurations