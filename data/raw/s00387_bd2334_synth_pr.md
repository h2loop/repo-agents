## Title: Fix resource leak in get_prb_blacklist config parsing

### Summary
The `get_prb_blacklist()` function in the gNB configuration module leaks resources when encountering early return conditions. The function initializes the configuration module via `config_get_if()` but fails to properly clean it up on error paths, leading to accumulated memory leaks and potential resource exhaustion during repeated configuration reloads.

The leak occurs specifically when the UL PRB blacklist configuration string is NULL or empty, triggering an early return without calling `end_configmodule()`. While the normal execution path also lacked cleanup, the early return path made the leak more likely to manifest during runtime configuration updates.

This fix ensures proper resource cleanup by calling `end_configmodule(config_get_if())` on all exit paths from the function.

### Changes
- `openair2/GNB_APP/gnb_config.c`: Added `end_configmodule(config_get_if())` before both the early return path (when `ulprbbl` is NULL) and the normal return path at function exit. This ensures the configuration module is properly deinitialized in all scenarios.

### Implementation Details
The configuration subsystem allocates internal resources during `config_get_if()` that must be explicitly freed using `end_configmodule()`. The function now maintains proper symmetry: every successful `config_get_if()` call is matched with a corresponding `end_configmodule()` call before returning, preventing resource leaks in both success and error conditions.

### Testing
- Verified clean compilation with resource leak detection enabled
- Confirmed proper cleanup behavior through code inspection of all exit paths
- This is a defensive fix that prevents resource accumulation during configuration parsing failures