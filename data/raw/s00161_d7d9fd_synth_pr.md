## Title: Fix C-RNTI byte order encoding for F1AP interface compatibility

### Summary
The C-RNTI MAC CE in MSG3 was being encoded in host byte order instead of network byte order, causing F1AP interface handling errors between the CU and DU. This mismatch resulted in message corruption or loss when the C-RNTI value was transmitted across the F1AP interface, as the receiving end interpreted the bytes incorrectly.

The manual byte swapping implementation `((crnti & 0xFF) << 8) | ((crnti >> 8) & 0xFF)` was not portable and didn't guarantee network byte order. The fix uses the standard `htons()` function to ensure proper network byte order encoding, making the code more portable and explicit about its intent.

### Changes
- `openair2/LAYER2/NR_MAC_UE/nr_ra_procedures.c`: Replace manual byte swapping with `htons()` in `fill_msg3_crnti_pdu()` function for proper network byte order encoding of C-RNTI MAC CE.

### Implementation Details
The change occurs in the MSG3 construction path during random access procedures. The `htons()` function is the standard way to convert host byte order to network byte order, ensuring compatibility across different platform architectures and proper F1AP interface handling.