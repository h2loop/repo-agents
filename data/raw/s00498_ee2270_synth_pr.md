## Title: Add parameter validation in UE context lookup to prevent power control errors

### Summary
The function `rrc_eNB_find_ue_context_from_gnb_rnti` lacked validation for the `gnb_rnti` parameter, allowing negative values to be processed. This caused undefined behavior during red-black tree traversal and could result in incorrect UE context matches. Downstream power control calculations would then use invalid UE parameters, leading to incorrect transmit power levels.

The fix adds an explicit check to reject negative `gnb_rnti` values before tree traversal, ensuring only valid RNTI values are processed and preventing the power control error.

### Changes
- `openair2/RRC/LTE/rrc_eNB_UE_context.c`: Added validation for `gnb_rnti` parameter in `rrc_eNB_find_ue_context_from_gnb_rnti()`. Returns NULL immediately if `gnb_rnti < 0`.

The validation is placed at the function entry point, maintaining the existing error-handling contract while adding protection against invalid inputs that could corrupt downstream power control decisions.