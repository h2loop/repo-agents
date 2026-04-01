## Title: Fix missing return statement in esm_msg_encode error path

### Summary
The `esm_msg_encode()` function in the NAS ESM message encoder had a missing return statement in its error handling path. When message encoding failed (`encode_result < 0`), the function would log the error but continue execution instead of immediately returning the error code. This caused fall-through to the success path, leading to undefined behavior and silent failures in the NAS layer where encoding errors were not properly propagated to the caller.

This patch adds the missing `LOG_FUNC_RETURN(encode_result)` statement to ensure proper error propagation when ESM message encoding fails, preventing subsequent code from executing with invalid encoded data.

### Changes
- `openair3/NAS/COMMON/ESM/MSG/esm_msg.c`: Added missing `LOG_FUNC_RETURN(encode_result)` at line 373 in the error handling branch of `esm_msg_encode()`. This ensures the function returns the error code immediately when encoding fails, rather than falling through to the success path.

### Implementation Details
The fix follows the established OAI NAS coding pattern using `LOG_FUNC_RETURN()`, which handles both logging and returning values consistently across the codebase. The change is minimal and surgical—only one line added with no modifications to function signatures, data structures, or control flow logic. All code paths now properly return a value as required for non-void functions.

### Testing
- Static code analysis confirms all execution paths now return a value
- Code review verifies the fix aligns with surrounding error handling patterns in the NAS module
- The error propagation path now correctly returns negative error codes to calling functions for proper handling at higher layers in the NAS stack