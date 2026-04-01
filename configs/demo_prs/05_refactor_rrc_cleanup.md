## Title: Refactor RRC NGAP NAS first request handling

### Summary
The function `rrc_gNB_process_initial_ul_rrc_message()` in the gNB RRC layer had grown to over 400 lines of inline processing for the NAS initial UE message forwarded via NGAP. The function mixed ASN.1 decoding, UE context creation, security context initialization, and NGAP message construction in a single monolithic block, making it difficult to maintain and test individual steps in isolation.

This refactor extracts the inline processing into focused helper functions: `rrc_gNB_create_ue_context_from_nas()` handles UE context allocation and initialization, `rrc_gNB_extract_nas_pdu()` handles NAS PDU extraction and validation, and `rrc_gNB_build_ngap_initial_ue_msg()` constructs the NGAP Initial UE Message. Error handling is improved throughout: each helper returns a status code and the caller performs structured cleanup on failure rather than relying on deeply nested if-else chains. No functional behavior is changed.

### Changes
- `openair2/RRC/NR/rrc_gNB_NGAP.c`: Extracted three helper functions from `rrc_gNB_process_initial_ul_rrc_message()`. Replaced nested error handling with early-return pattern using the new helpers. Reduced main function from 420 lines to 85 lines.
- `openair2/RRC/NR/rrc_gNB_NGAP.h`: Added declarations for the three new static helper functions (kept file-scoped via `static` in the .c file, but documented in the header for clarity).
- `openair2/RRC/NR/nr_rrc_defs.h`: No changes to data structures; minor comment updates to clarify UE context lifecycle.
- `openair2/RRC/NR/rrc_gNB_du.c`: Updated one call site that previously accessed an inline variable now encapsulated in `rrc_gNB_create_ue_context_from_nas()`.

### Testing
- Ran the full `nr-sa-attach-detach` CI pipeline with 8 UEs performing registration and deregistration cycles. All tests pass with identical message traces.
- Verified NGAP Initial UE Message encoding matches byte-for-byte against the pre-refactor output using pcap comparison.
- Code coverage for `rrc_gNB_NGAP.c` increased from 62% to 74% as the individual helpers are now independently testable.
