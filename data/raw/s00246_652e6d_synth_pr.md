## Title: Fix missing error handling in NGAP SCTP data indication processing

### Summary
The NGAP layer's SCTP data indication handler was not checking the return value from `ngap_gNB_handle_message()`, causing F1AP interface errors between CU and DU to go undetected. When message processing failed downstream, the system would silently continue without logging the failure, leading to potential message loss or corruption that was difficult to diagnose.

This fix adds proper error handling and logging to the SCTP data indication path. The return value from `ngap_gNB_handle_message()` is now captured and validated. When message handling fails, the system logs a detailed error message with association ID, stream number, and buffer length to aid debugging, while continuing processing to prevent additional message loss in the SCTP data path.

### Changes
- `openair3/NGAP/ngap_gNB.c`: Added return value capture for `ngap_gNB_handle_message()` call and error logging when the function returns a negative value. The error log includes context about the failed message to help identify F1AP interface issues.

### Implementation Details
- The error handling preserves the existing control flow to avoid disrupting the SCTP association
- Error logging uses the `NGAP_ERROR` macro for consistency with other NGAP error reporting
- The fix specifically addresses the gap between SCTP data receipt and NGAP message parsing where F1AP interface errors manifest

### Testing
- Verified error logging triggers appropriately when `ngap_gNB_handle_message()` returns failure
- Confirmed normal SCTP data processing continues uninterrupted for successful message handling
- Validated that no memory leaks occur with the existing buffer cleanup path