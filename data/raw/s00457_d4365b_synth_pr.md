## Title: Add error handling for thread scheduling and PNF start operations

### Summary
The `pnf_start_thread` function in the NFAPI PNF integration layer previously ignored return values from critical system calls, potentially masking failures during thread initialization and PNF startup. Specifically, `pthread_setschedparam()` and `nfapi_pnf_start()` could fail without any error reporting or propagation, leading to undefined behavior and difficult-to-diagnose issues in the NFAPI subsystem.

This fix adds proper error checking and logging for both function calls. When `pthread_setschedparam()` fails to set the SCHED_FIFO scheduling parameters, the error is now logged and the thread exits with the error code. Similarly, failures from `nfapi_pnf_start()` are captured and logged before returning the error status to the caller. This ensures that initialization failures are visible through the NFAPI tracing system and can be properly handled upstream.

### Changes
- `nfapi/oai_integration/nfapi_pnf.c`: Added return value checks for `pthread_setschedparam()` and `nfapi_pnf_start()` calls in `pnf_start_thread()`. Added error logging via `NFAPI_TRACE()` and proper error code propagation.

### Implementation Details
The function now stores return values in a local `ret` variable, checks for non-zero status, logs detailed error messages using the NFAPI tracing infrastructure, and returns the error code cast to `void*` for pthread compatibility. On success, it returns `(void *)0` as before, maintaining the original API contract.

### Testing
- Verified compilation with the NFAPI integration enabled
- Confirmed error paths are properly handled through code inspection
- No functional changes to successful execution paths