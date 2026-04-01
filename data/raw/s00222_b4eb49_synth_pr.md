## Title: Fix ASN.1 encoding error by initializing EMM-SAP structure in emm_proc_attach_release

### Summary
The `emm_proc_attach_release` function in the NAS UE EMM Attach module passes a stack-allocated `emm_sap_t` structure to `_emm_attach_abnormal_cases_bcd()` for abnormal case handling. However, the structure was not explicitly initialized, causing ASN.1 encoding logic to read uninitialized memory fields when constructing protocol messages. This resulted in malformed encoded messages being sent downstream.

The fix adds explicit zero-initialization of the `emm_sap` structure using `memset()` before it is used, ensuring all fields have deterministic values during ASN.1 encoding.

### Changes
- `openair3/NAS/UE/EMM/Attach.c`: Added `memset(&emm_sap, 0, sizeof(emm_sap_t))` at the start of `emm_proc_attach_release()` to properly initialize the EMM-SAP structure before passing it to `_emm_attach_abnormal_cases_bcd()`.

### Implementation Details
The initialization is placed immediately after variable declarations and before the call to `_emm_attach_abnormal_cases_bcd()`, following the established pattern used elsewhere in the NAS codebase for stack-allocated protocol structures. This is a minimal, safe change that only affects local stack memory.

### Testing
- This resolves the ASN.1 encoding errors that occurred when the attach procedure was aborted due to NAS signaling connection release
- The change ensures deterministic encoding behavior by preventing use of uninitialized memory
- No functional behavior changes; only eliminates undefined behavior and encoding corruption