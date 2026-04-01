## Title: Fix unchecked return value in LwM2M TLV dummy read function

### Summary
The `do_write_op_tlv_dummy_read()` function in the LwM2M OMA-TLV writer called `oma_tlv_get()` without checking its return value. If `oma_tlv_get()` fails due to malformed input data (e.g., a truncated or corrupted TLV payload from a malicious server), it returns a negative error code but the `tlv` structure remains uninitialized. The subsequent `while (tlv.length--)` loop would then iterate based on garbage data, potentially causing excessive looping or reading beyond the buffer bounds.

This fix captures the return value of `oma_tlv_get()` and propagates the error immediately if parsing fails, preventing undefined behavior from uninitialized TLV data.

### Changes
- `subsys/net/lib/lwm2m/lwm2m_rw_oma_tlv.c`: Added return value check for `oma_tlv_get()` in `do_write_op_tlv_dummy_read()`. The function now returns the error code if TLV parsing fails before entering the read loop.

### Testing
- Verified the fix handles malformed TLV input gracefully by returning an error instead of looping on garbage data.
- Confirmed existing LwM2M write operations continue to function correctly with valid TLV payloads.