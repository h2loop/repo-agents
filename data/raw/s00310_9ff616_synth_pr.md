## Title: Fix HARQ indication message size calculation in nFAPI P7 interface

### Summary
The nFAPI P7 interface incorrectly calculates message size when packing HARQ indication messages, causing CRC computation errors and potential buffer corruption. The `nfapi_pnf_p7_harq_ind` function uses `sizeof(nfapi_harq_indication_t)` which only accounts for the fixed header portion, omitting the variable-length payload containing actual HARQ PDUs. This results in incomplete message transmission and incorrect CRC values, leading to false error detection or dropped HARQ indications at the receiver.

The root cause is that `nfapi_harq_indication_t` contains a flexible array member whose size depends on `harq_indication_body.number_of_harqs`. The fix properly calculates total message size by including the payload before calling the pack-and-send routine.

### Changes
- `nfapi/open-nFAPI/pnf/src/pnf_p7_interface.c`: Modified `nfapi_pnf_p7_harq_ind` to compute correct message size including variable-length HARQ PDU payload. The calculation now uses: `sizeof(nfapi_harq_indication_t) + (ind->harq_indication_body.number_of_harqs * sizeof(nfapi_harq_indication_pdu_t))`.

### Implementation Details
The fix ensures the complete HARQ indication message (header + all PDU entries) is included in the size passed to `pnf_p7_pack_and_send_p7_message`, enabling proper CRC computation and preventing buffer underrun during message serialization. This aligns with the nFAPI specification's variable-length message format for HARQ indications.