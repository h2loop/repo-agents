## Title: Fix null pointer dereference in nfapi_nr_pnf_pnf_param_resp

### Summary
The `nfapi_nr_pnf_pnf_param_resp` function in the nFAPI PNF interface had a potential null pointer dereference vulnerability on the `config->send_p5_msg` function pointer. While the function validated the `config` and `resp` parameters, it did not check if the `send_p5_msg` callback was initialized before dereferencing it. The existing `AssertFatal` macro only provided debug-build protection and could be compiled out in release builds, risking production crashes.

This fix adds an explicit runtime NULL check for the `send_p5_msg` function pointer prior to invocation. If NULL, the function logs an error via `NFAPI_TRACE` and returns -1, enabling graceful error handling by callers. The debug assertion is removed as it's superseded by proper runtime validation that protects both debug and release builds.

### Changes
- `nfapi/open-nFAPI/pnf/src/pnf_interface.c`: Added NULL check for `config->send_p5_msg` with error logging and early return. Replaced `AssertFatal` with defensive runtime validation to prevent crashes when the function pointer is uninitialized.

### Testing
- Code review confirms the NULL check prevents dereferencing of uninitialized function pointers.
- Static analysis no longer flags this code path as vulnerable.
- The error return path allows upstream components to handle configuration issues gracefully instead of crashing.