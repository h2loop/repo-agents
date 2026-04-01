## Title: Fix cross-layer RNTI type mismatches in mac_remove_nr_ue calls

### Summary
The `mac_remove_nr_ue()` function expects an `rnti_t` type for its second parameter, but several cross-layer call sites were passing raw integer types without explicit casting. This parameter mismatch between MAC and RRC layers could lead to inconsistent type handling and potential truncation issues on platforms where `rnti_t` differs from the caller's integer type. The root cause is missing explicit type casts at the call sites, which violates the function contract and creates cross-layer inconsistency.

### Changes
- `openair2/LAYER2/NR_MAC_gNB/mac_rrc_dl_handler.c`: Added explicit cast to `rnti_t` when dereferencing `old_gNB_DU_ue_id` before passing to `mac_remove_nr_ue()`
- `openair2/RRC/NR/rrc_gNB_nsa.c`: Added explicit cast to `rnti_t` for the `rnti` parameter when calling `mac_remove_nr_ue()`

### Implementation Details
The fix ensures type safety by explicitly casting integer UE identifiers to the proper `rnti_t` type expected by the MAC layer API. This resolves the cross-layer parameter mismatch and guarantees consistent type handling between RRC and MAC components. The casts are safe as the source values are validated UE identifiers that fit within the `rnti_t` type definition.

### Testing
- Verified compilation with strict type checking enabled
- Confirmed no functional regressions in UE removal procedures
- Validated cross-layer parameter passing consistency across MAC and RRC boundaries