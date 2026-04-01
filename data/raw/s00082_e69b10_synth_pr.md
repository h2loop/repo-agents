## Title: Enforce 3GPP compliance for conditionally mandatory ServCellIndex in F1AP UE Context messages

### Summary
3GPP TS 38.473 specifies that the `ServCellIndex` IE is conditionally mandatory when `SpCellID` (NRCGI) is present in UE Context Modification Request messages. The current F1AP implementation does not enforce this constraint, allowing non-compliant messages to be encoded or decoded, which can cause interoperability issues with compliant DU implementations.

This change adds validation logic to ensure that whenever `SpCellID` is included in UE Context Modification Request, UE Context Setup Request, or CU-to-DU RRC Information structures, the `ServCellIndex` must also be present. The validation is applied symmetrically on both encoding and decoding paths to catch violations early and prevent propagation of malformed messages.

### Changes
- `openair2/F1AP/lib/f1ap_ue_context.c`: Added conditional mandatory validation in four functions:
  - `encode_ue_context_mod_req()`: Returns NULL if SpCellID present without ServCellIndex
  - `decode_ue_context_mod_req()`: Returns false and frees decoded struct on violation
  - `decode_cu_to_du_rrc_info()`: Returns false on violation
  - `decode_ue_context_setup_req()`: Logs warning on violation (maintains backward compatibility for setup)

### Implementation Details
The validation checks if both `plmn` and `nr_cellid` are non-NULL (indicating SpCellID presence) and `servCellIndex` is absent. On encoding/decoding failure, the functions log an error message referencing 3GPP TS 38.473 and perform appropriate cleanup to prevent memory leaks. This ensures strict compliance while maintaining robust error handling.