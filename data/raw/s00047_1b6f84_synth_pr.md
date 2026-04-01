## Title: Fix missing error propagation in NAS security header setup

### Summary
The function `_emm_as_set_header()` in the NAS EMM SAP layer can return NULL when a security context exists but the integrity key is not available. However, three call sites in `emm_as.c` were not checking for this NULL return value, causing silent failures where execution would continue with an invalid pointer or skip critical message processing. This could lead to undefined behavior or security-related messages being dropped without error notification.

This fix adds proper NULL checks after each call to `_emm_as_set_header()`. When the function fails, we now log an explicit error message and return `RETURNerror` to propagate the failure up the call stack, ensuring that upper layers are aware of security header setup failures.

### Changes
- `openair3/NAS/UE/EMM/SAP/emm_as.c`: 
  - In `_emm_as_data_req()` (line 1082): Added NULL check after `_emm_as_set_header()` call with error logging and early return
  - In `_emm_as_status_ind()` (line 1176): Added NULL check with error logging and early return
  - In `_emm_as_security_res()` (line 1279): Added NULL check with error logging and early return
  - Restructured switch statements with proper braces for improved readability and safer control flow

### Implementation Details
The fix follows the existing error handling pattern in the codebase using `LOG_TRACE(ERROR, ...)` for error reporting and `LOG_FUNC_RETURN(RETURNerror)` for consistent function exit. The added error message clearly indicates that NAS security header setup failed due to missing integrity key, making debugging easier.