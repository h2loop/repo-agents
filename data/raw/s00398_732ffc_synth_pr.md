## Title: Fix incorrect return type in detach timer handler

### Summary
The `emm_detach_t3421_handler` timer callback function was incorrectly declared with return type `void *` despite being a void function that performs detach timeout processing without returning any value. This type mismatch could lead to data corruption or misinterpretation downstream, as callers might attempt to use the returned pointer value. The function now correctly declares `void` return type, matching its actual behavior and consistent with other timer handlers in the EMM module.

### Changes
- **openair3/NAS/UE/EMM/Detach.c**: Changed function signature from `void *emm_detach_t3421_handler(void *args)` to `void emm_detach_t3421_handler(void *args)`. Updated return statement from `LOG_FUNC_RETURN(NULL)` to `LOG_FUNC_RETURN` to match void function semantics.
- **openair3/NAS/UE/EMM/emm_timers.h**: Updated function declaration to match the corrected signature.

### Implementation Details
This is a type safety fix only; no functional behavior changes. The function processes T3421 timer expiry during UE detach procedures, performing cleanup operations through `_emm_detach_release()` or `_emm_detach_abort()`. The incorrect `void *` return type has been present since the function's introduction and is now aligned with the established pattern used by other timer handlers like `emm_attach_t3410_handler()` and `emm_service_t3417_handler()`.