## Title: Fix stale protocol state in NFAPI PNF threads

### Summary
The NFAPI PNF start threads did not clean up protocol state after procedure completion or failure. When `pnf_start_thread` or `pnf_nr_start_thread` finished executing, the dynamically allocated `nfapi_pnf_config_t` configuration object was never destroyed, leaving stale protocol state in memory. This caused memory leaks and potential state contamination during subsequent PNF initializations, particularly problematic in scenarios with multiple PNF start/stop cycles or error recovery paths.

This fix adds explicit resource cleanup to both thread entry points. After the PNF stops and `nfapi_pnf_start()` or `nfapi_nr_pnf_start()` returns, the code now calls `nfapi_pnf_config_destroy(config)` to release all allocated resources and reset protocol state. This ensures proper state management throughout the PNF lifecycle.

Additionally, a duplicate `configure_nr_nfapi_pnf` function definition was removed to eliminate dead code.

### Changes
- `nfapi/oai_integration/nfapi_pnf.c`: 
  - Added `nfapi_pnf_config_destroy(config)` cleanup in `pnf_start_thread()` after `nfapi_pnf_start()`
  - Added `nfapi_pnf_config_destroy(config)` cleanup in `pnf_nr_start_thread()` after `nfapi_nr_pnf_start()`
  - Removed duplicate `configure_nr_nfapi_pnf()` function definition

### Testing
- Verified memory cleanup with Valgrind during multiple PNF start/stop cycles
- Confirmed no regression in NFAPI P5/P7 interface operations with OAI gNB
- Tested error recovery paths to ensure clean state after PNF failures