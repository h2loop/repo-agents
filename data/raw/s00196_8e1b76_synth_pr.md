## Title: Fix buffer overflow vulnerability in SCTP connection lookup

### Summary
The `sctp_get_cnx()` function in the SCTP eNB task layer contains a buffer overflow vulnerability that occurs when the function returns connection elements with uninitialized `out_streams` fields (value 0). Callers validate stream indices using `if (stream >= sctp_cnx->out_streams)`, but when `out_streams` is 0, this bounds check passes for any valid stream value (>= 0). This allows out-of-bounds memory access, leading to potential crashes, data corruption, or exploitable security vulnerabilities.

This fix addresses the root cause by validating connection initialization within `sctp_get_cnx()` itself. The function now checks that `out_streams` is non-zero before returning a connection element, ensuring that only properly initialized connections are used for data transfer. If an uninitialized connection is found, the function returns NULL, allowing callers to handle the error gracefully.

### Changes
- `openair3/SCTP/sctp_eNB_task.c`: Added validation for `out_streams == 0` in both the `assoc_id` and `sd` lookup paths within `sctp_get_cnx()`. Returns NULL with descriptive error logging when an uninitialized connection is detected, preventing downstream buffer overflow.

### Implementation Details
The validation leverages the fact that SCTP connections negotiate stream counts during association setup, so a zero `out_streams` value reliably indicates incomplete initialization. The fix is placed at the source of the vulnerability rather than at each call site, providing a single point of protection. Callers already implement NULL checks on the returned pointer, so this change integrates cleanly with existing error handling paths.

### Testing
- Verified that the bounds check logic now correctly rejects invalid stream indices when connections are uninitialized
- Confirmed that existing NULL pointer handling in call sites properly manages the new error case
- Recommend running SCTP association stress tests and protocol conformance tests to validate initialization timing under various network conditions