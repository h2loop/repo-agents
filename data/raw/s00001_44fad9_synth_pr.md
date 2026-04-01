## Title: Fix missing MAC-I field in PDCP control plane PDU serialization

### Summary
The PDCP control plane PDU serialization function for SRBs was omitting the mandatory MAC-I field, causing incomplete signaling messages. According to 3GPP TS 36.323 Section 6.2.2, control plane data PDUs must include a 32-bit MAC-I field for integrity protection immediately following the 5-bit sequence number. The existing implementation only serialized the sequence number, leaving the subsequent 4 bytes uninitialized. This resulted in malformed PDUs that could cause integrity verification failures at the receiver.

The fix adds proper serialization of the MAC-I field by copying the 4-byte integrity protection data from the PDU structure to the appropriate offset in the output buffer.

### Changes
- `openair2/LAYER2/PDCP_v10.1.0/pdcp_primitives.c`: Added MAC-I field serialization in `pdcp_serialize_control_plane_data_pdu_with_SRB_sn_buffer()`. The MAC-I bytes are now copied from `pdu->mac_i` to `pdu_buffer[1..4]` using `memcpy` immediately after the sequence number is written to `pdu_buffer[0]`.

### Testing
- Verified PDCP PDU structure now conforms to 3GPP TS 36.323 specification
- Confirmed MAC-I field is correctly populated in outgoing SRB1/SRB2 control plane messages
- Validated no regressions in PDCP unit tests for control plane PDU handling