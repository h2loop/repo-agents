## Title: Add critical failure logging to fill_nfapi_uci_acknak function

### Summary
The `fill_nfapi_uci_acknak` function in the eNB scheduler lacked proper error handling and logging for critical failure conditions. When invalid parameters were passed or internal state was corrupted, the function would fail silently or trigger assertions without providing diagnostic information. This made debugging difficult in production environments where assertion failures are undesirable and root cause analysis was challenging.

This patch adds comprehensive input validation and critical failure detection with appropriate error logging. The function now validates `module_idP`, `eNB` instance, and `CC_idP` parameters before dereferencing pointers, and checks for invalid HARQ information configuration. All error paths now log detailed diagnostic messages using the MAC error logging facility before returning error codes, enabling better observability and debugging without process termination.

### Changes
- `openair2/LAYER2/MAC/eNB_scheduler_primitives.c`: Added input validation checks for `module_idP`, `eNB` pointer, and `CC_idP` parameters at function entry. Added critical failure detection for invalid `n_pucch_1_0` values in both FDD and TDD HARQ information structures. All failure paths now call `LOG_E(MAC, ...)` with detailed context including RNTI, CCE index, and parameter values before returning.

### Implementation Details
The logging uses the existing `LOG_E` macro with the `MAC` module identifier to maintain consistency with the codebase's logging conventions. Each error log includes the function name, the specific validation failure, and relevant identifiers (`rntiP`, `cce_idxP`, `module_idP`, `CC_idP`) to enable quick correlation with other MAC layer logs. The function returns 0 on error to indicate failure to the caller, preserving the existing return value semantics.