## Title: Fix thread-safety issue in X2AP UE context release handler

### Summary
The `x2ap_eNB_handle_ue_context_release` function accesses the shared `id_manager` resource without proper synchronization, creating a race condition when multiple threads process X2AP messages concurrently. This can lead to data corruption, inconsistent UE ID mappings, and potential crashes in multi-threaded gNB deployments under high X2 traffic load.

This fix introduces mutex protection around all accesses to the `id_manager` structure. A global mutex is acquired before any operations on the shared resource and explicitly released on all exit paths, including error handling branches. This ensures thread-safe access to UE ID mappings and prevents race conditions during context release processing.

### Changes
- `openair2/X2AP/x2ap_eNB_handler.c`: Added mutex lock before `id_manager` operations and corresponding unlock calls on all return paths in `x2ap_eNB_handle_ue_context_release()`. The critical section protects `x2ap_find_id_from_id_source()`, `x2ap_id_get_rnti()`, and `x2ap_release_id()` calls. Error handling ensures the mutex is always released even when validation fails.

### Implementation Details
- Uses existing global mutex (`extern pthread_mutex_t mutex`) for consistency with other X2AP modules
- Validates mutex lock/unlock return codes and logs errors appropriately
- Maintains proper cleanup of ITTI messages on error paths
- No functional changes to the X2AP protocol logic; purely synchronization enhancement

### Testing
- Verified with multi-threaded gNB simulation handling concurrent X2AP UE context releases
- No regressions observed in X2 handover success rates or latency metrics
- Thread sanitizer reports no data races in the modified function