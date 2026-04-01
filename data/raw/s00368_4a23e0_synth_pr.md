## Title: Replace deprecated CALLOC macro with standard calloc and add error handling

### Summary
The NFAPI VNF integration layer was using a deprecated `CALLOC` macro for dynamic memory allocation in PHY indication handlers. This macro had known safety issues and lacked proper error handling, risking undefined behavior when memory allocation failed. This patch replaces all `CALLOC` calls with the standard `calloc()` function and adds robust NULL-checking with graceful error handling. When allocation fails, the code now logs an explicit error message and returns early instead of proceeding with invalid pointers, preventing potential crashes and improving debuggability.

### Changes
- `nfapi/oai_integration/nfapi_vnf.c`: 
  - Replaced `CALLOC` with `calloc()` in `phy_nr_rach_indication()`, `phy_nr_uci_indication()`, and related PHY indication handlers
  - Added NULL pointer validation after each allocation with `LOG_E()` error logging
  - Implemented proper cleanup and early return on allocation failure
  - Updated `AssertFatal` messages to be more descriptive about allocation failures

### Testing
- Verified successful compilation with the new allocation pattern
- Confirmed error paths are reachable by injecting allocation failures
- Validated NFAPI VNF mode operation shows no functional regression in RACH and UCI indication processing