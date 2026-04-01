## Title: Fix RLC AM protocol timer compliance and poll retransmit logic

### Summary
This change corrects two 3GPP TS 36.322 specification violations in the RLC AM entity. First, the `t-Reordering` timer decoding table contained an incorrect maximum value of 1600ms (entry 31) instead of the required 2000ms, causing non-compliant timer behavior when the highest encoded value is configured. Second, the logic for stopping `t-PollRetransmit` incorrectly used sequence number comparisons rather than checking for equality with `poll_sn`, leading to premature or missed timer stops during ARQ operations.

### Changes
- `openair2/LAYER2/rlc_v2/asn1_utils.c`: Correct `decode_t_reordering()` lookup table entry 31 from 1600ms to 2000ms per 3GPP 36.322 Table 7.3.2-1
- `openair2/LAYER2/rlc_v2/rlc_entity_am.c`: Fix `t_poll_retransmit_start` reset conditions in both ACK and NACK handling paths to match 3GPP 36.322 section 5.2.2.2

### Implementation Details
The poll retransmit timer stop logic now correctly implements the specification: for ACK processing, stop only when `ack_sn == poll_sn` (not on less-than comparison); for NACK processing, stop when `poll_sn <= nack_sn`. This ensures proper ARQ behavior where the timer stops exactly when receiving status feedback for the polled sequence number.

### Testing
- Verified timer decoding values against 3GPP TS 36.322 specification tables
- Confirmed ARQ state machine maintains correct behavior with the corrected timer stop conditions