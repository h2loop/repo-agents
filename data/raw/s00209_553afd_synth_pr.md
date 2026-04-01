## Title: Fix use-after-free vulnerability in PDN disconnect reject handling

### Summary
The `esm_proc_pdn_disconnect_reject()` function contains a use-after-free vulnerability where transaction data is accessed after being freed. The code releases the procedure transaction identity via `esm_pt_release()` and then subsequently calls `_pdn_disconnect_get_default_ebi()` using the freed transaction data to retrieve the EPS bearer identity. This can cause crashes, memory corruption, or undefined behavior when the UE processes PDN disconnect reject messages from the network.

The fix reorders the operations to extract the EPS bearer identity (EBI) from the transaction data BEFORE releasing the transaction, storing it in a local variable for subsequent use. This eliminates the use-after-free condition while preserving all original error handling and control flow.

### Changes
- `openair3/NAS/UE/ESM/PdnDisconnect.c`: Moved the `_pdn_disconnect_get_default_ebi()` call to occur before `esm_pt_release()`, adding a local `ebi` variable to store the result safely. All error handling paths and return conditions remain unchanged.

### Testing
- Verified fix with NAS UE simulator executing PDN disconnect reject scenarios
- Confirmed no regressions in standard attach/detach and bearer management procedures
- Memory sanitizer validation confirms elimination of use-after-free warnings