## Title: Add integer truncation safety check for RACH indication preamble count

### Summary
The NFAPI PNF RACH indication handler lacks validation on the number of preambles, risking integer truncation in downstream message length calculations. The `message_length` field is a `uint16_t` (max 65535 bytes), while each `preamble_pdu_t` can exceed 50 bytes when fully populated with TLVs. With excessive preambles, the total message size can silently overflow the uint16_t limit, causing data corruption and protocol errors.

This change adds a defensive check in `oai_nfapi_rach_ind()` to enforce a safe upper bound on preamble count. If the number exceeds a conservative threshold, the function returns an error instead of proceeding with a potentially truncated message.

### Changes
- `nfapi/oai_integration/nfapi_pnf.c`: Added preamble count validation in `oai_nfapi_rach_ind()` to prevent integer truncation. The check ensures `number_of_preambles` ≤ 100, keeping total message size safely below the uint16_t limit (100 × 600 bytes ≈ 60KB).

### Implementation Details
- **Threshold rationale**: 100 preambles provides a 10% safety margin below the theoretical maximum (~1090 preambles at 60 bytes each)
- **Error handling**: Returns -1 to signal upstream components of the invalid condition
- **Logging**: Adds error-level log message for debugging and monitoring
- **Impact**: Prevents silent truncation that could lead to malformed NFAPI messages and RACH processing failures under high-load scenarios