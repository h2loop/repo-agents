## Title: Fix NULL pointer dereference vulnerability in UL DMRS parameter extraction

### Summary
Fix a NULL pointer dereference vulnerability in `get_ul_dmrs_params()` that could cause crashes when processing uplink DMRS configurations. The original code used nested ternary operators to access `dmrs_UplinkForPUSCH_MappingTypeA/B->choice.setup` without validating that these pointers were non-NULL. In configurations where these optional fields are absent, the code would dereference NULL pointers, leading to undefined behavior and potential segmentation faults.

The fix replaces the unsafe ternary chain with explicit NULL checks for both the mapping type structures and their `choice.setup` fields before dereferencing. This ensures safe access to DMRS uplink configuration parameters and prevents crashes when processing malformed or incomplete RRC configurations.

### Changes
- `openair2/LAYER2/NR_MAC_gNB/gNB_scheduler_primitives.c`: Refactored DMRS uplink config pointer extraction in `get_ul_dmrs_params()` to add comprehensive NULL checks for `dmrs_UplinkForPUSCH_MappingTypeA`, `dmrs_UplinkForPUSCH_MappingTypeB`, and their nested `choice.setup` fields before dereferencing.

### Testing
- Verified the fix with unit tests covering both mapping type A and B configurations with missing optional fields
- Validated normal operation with complete DMRS configurations remains unaffected
- Code review confirms all code paths now properly handle NULL pointers before dereferencing