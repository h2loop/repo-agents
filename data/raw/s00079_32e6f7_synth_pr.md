## Title: Fix errno corruption in RACH indication unpacking

### Summary
The `unpack_rach_indication_body_value` function in the nFAPI P7 codec fails to preserve errno when `nfapi_p7_allocate` fails. When memory allocation fails (setting errno to ENOMEM), the subsequent `NFAPI_TRACE` logging call may internally modify errno before the caller can check it. This causes upstream error handling to misinterpret the failure reason, potentially leading to incorrect error reporting or recovery actions.

This fix saves errno immediately after the allocation failure and restores it after logging, ensuring the original error code remains visible to callers. This follows the standard pattern of preserving errno across operations that might modify it.

### Changes
- `nfapi/open-nFAPI/nfapi/src/nfapi_p7.c`: In `unpack_rach_indication_body_value`, added `saved_errno` variable to capture errno before `NFAPI_TRACE` and restore it after, preventing logging from overwriting the allocation error code.

### Testing
- Verified errno preservation when allocation fails with ENOMEM
- Confirmed no regression in RACH indication message processing
- Validated error propagation to upstream callers correctly reports memory allocation failures