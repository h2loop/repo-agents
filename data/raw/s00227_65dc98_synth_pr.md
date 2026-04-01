## Title: Fix buffer overflow vulnerability in E1AP bearer context setup

### Summary
The `cucp_cuup_bearer_context_setup_e1ap` function uses `memcpy()` to copy the `e1ap_bearer_setup_req_t` structure when preparing inter-task messages. This structure contains nested arrays for PDU sessions and DRB configurations. Using `memcpy()` on such complex structures results in shallow copying that can lead to buffer overflows when nested arrays exceed allocated bounds or contain pointer fields, causing memory corruption in the CU-CP to CU-UP interface.

This fix replaces the unsafe `memcpy()` with a dedicated `deep_copy_e1ap_bearer_setup_req()` function that safely copies each field individually. The deep copy iterates through PDU session arrays and DRB lists, ensuring proper duplication of all nested data structures without buffer overruns. This eliminates the memory corruption vulnerability while preserving all protocol functionality.

### Changes
- `openair2/RRC/NR/cucp_cuup_e1ap.c`: Added `deep_copy_e1ap_bearer_setup_req()` static function that performs field-by-field copying of the bearer setup request, including all nested PDU session and DRB structures. Replaced the vulnerable `memcpy()` call in `cucp_cuup_bearer_context_setup_e1ap()` with this safe deep copy implementation.

### Testing
- Verified successful compilation with `-Wall -Wextra` without warnings
- Code review confirms all nested structures and arrays are properly deep-copied
- No functional changes to E1AP bearer context setup behavior observed