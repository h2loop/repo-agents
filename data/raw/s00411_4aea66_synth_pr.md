## Title: Add null pointer validation in PNF simulator UL config request handler

### Summary
Add a missing state validation check in the `phy_ul_config_req` function to prevent null pointer dereference when accessing the FAPI interface. The PNF (Physical Network Function) simulator processes uplink configuration requests from the VNF (Virtual Network Function), but previously assumed the `phy->fapi` pointer was always valid when handling these messages. In error scenarios or during initialization/teardown sequences, this pointer could be NULL, leading to potential segmentation faults. This change adds an explicit NULL check before dereferencing the pointer, aligning with defensive programming practices used elsewhere in the codebase.

### Changes
- `nfapi/open-nFAPI/pnf_sim/src/main.cpp`: Added null pointer validation for `phy->fapi` in `phy_ul_config_req()` at line 1714. If the pointer is NULL, the function now logs an error message and returns -1 instead of proceeding to dereference the invalid pointer.

### Implementation Details
The validation follows the existing error handling pattern in the PNF simulator, using `printf()` for logging and returning a negative error code. The check is placed immediately after the `fapi_req` structure declaration and before the `fapi_ul_config_request()` call, ensuring early failure with clear diagnostic output. This matches similar defensive checks found in other protocol message handlers within the same module.