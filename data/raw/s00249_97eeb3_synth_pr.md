## Title: Fix unreachable code path in UL config request PDU removal

### Summary
Fix a synchronization bug in `oai_nfapi_ul_config_req()` where the local variable `num_pdus` becomes stale after calling `remove_ul_config_req_pdu()`. The helper function decrements `ul_config_req->ul_config_request_body.number_of_pdus` internally by shifting PDU entries, but the caller also decrements its local `num_pdus` copy. This divergence causes incorrect loop conditions and unreachable code paths when processing duplicate CQI requests for the same UE.

The fix ensures `num_pdus` is re-synchronized with the authoritative struct value after each PDU removal, maintaining correct iteration bounds and preventing off-by-one errors in the inner processing loop.

### Changes
- `nfapi/oai_integration/nfapi_vnf.c`: In `oai_nfapi_ul_config_req()`, replace the manual `num_pdus--` decrement with `num_pdus = ul_config_req->ul_config_request_body.number_of_pdus;` after calling `remove_ul_config_req_pdu()`.

### Implementation Details
The `remove_ul_config_req_pdu()` function directly modifies the request body's PDU count and list. The caller's local `num_pdus` variable must reflect this change to ensure the inner loop condition `j < num_pdus` evaluates correctly on subsequent iterations. The updated assignment guarantees the local variable stays consistent with the actual PDU count after each removal operation.

### Testing
- Code inspection confirms the synchronization issue and that the fix restores proper loop semantics
- The change is minimal and isolated to the duplicate CQI detection and removal path