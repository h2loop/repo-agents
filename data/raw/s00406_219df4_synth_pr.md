## Title: Fix missing error propagation in E1AP SCTP data handling

### Summary
The E1AP task was silently ignoring return values from `e1ap_handle_message()`, masking failures in downstream message handlers including `e1apCUCP_handle_BEARER_CONTEXT_RELEASE_REQUEST`. This made debugging difficult as protocol processing errors went unnoticed, potentially leaving bearer contexts in inconsistent states.

This patch ensures errors from message processing are properly logged. The return value from `e1ap_handle_message()` is now captured and checked. Negative return values trigger an error log message, making failures visible while maintaining existing error recovery behavior.

### Changes
- `openair2/E1AP/e1ap.c`: Modified `e1_task_handle_sctp_data_ind()` to store the return value of `e1ap_handle_message()` in a new variable `ret`. Added a conditional check that logs errors when `ret < 0` using `LOG_E()`.

### Implementation Details
The fix is minimal and non-intrusive: it preserves the existing control flow while adding observability. The error logging uses the standard OAI logging framework with the `E1AP` module identifier. No changes were made to the message handlers themselves; this purely addresses the propagation gap at the SCTP data indication layer.

### Testing
- Verified compilation succeeds with the new error handling path
- Confirmed error logging activates when `e1ap_handle_message()` returns failure codes
- Existing E1AP functionality remains unchanged; only diagnostics are improved