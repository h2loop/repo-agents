## Title: Fix power control TLV packing in nFAPI P7 TX data interface

### Summary
The nFAPI P7 interface was incorrectly handling power control TLVs (tags 2-10) in TX data PDU packing and unpacking functions. These critical TLVs were falling through to a default case that only logged a FIXME comment, causing power control parameters to be silently skipped during message serialization. This resulted in incorrect transmit power levels being applied at the gNB, as the power control data was either corrupted or omitted from TX data requests.

The fix adds explicit case handlers for all power control TLV types in both `pack_tx_data_pdu_list_value()` and `unpack_tx_data_pdu_list_value()`, implementing proper array-based packing/unpacking with `pusharray32()`/`pullarray32()`. The default case now returns an error instead of continuing, preventing silent failures from unsupported tags.

### Changes
- `nfapi/open-nFAPI/nfapi/src/nfapi_p7.c`: 
  - Added dedicated case handlers for TLV tags 2-10 (power control, transmit power offset, power headroom, path loss reference, P0 nominal, alpha value, CLTD control, and uplink power control)
  - Implemented proper array packing/unpacking with correct length alignment calculations
  - Enhanced trace logging for power control TLV operations
  - Changed default case from `break` to `return 0` for proper error propagation

### Testing
- Verified power control parameters are now correctly serialized/deserialized in TX data requests
- Confirmed transmit power levels match configured values after the fix
- Validated error handling for invalid TLV tags returns appropriate failure codes
- No regression observed in existing nFAPI message flows