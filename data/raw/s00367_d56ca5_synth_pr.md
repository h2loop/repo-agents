## Title: Fix buffer overflow vulnerability in RRCConnectionReconfiguration_BR encoder

### Summary
The `do_RRCConnectionReconfiguration_BR` function in the LTE RRC subsystem encodes ASN.1 RRC connection reconfiguration messages into a provided buffer. Previously, the function called `uper_encode_to_buffer()` but did not validate whether the resulting encoded data fit within the supplied `buffer_size`. If the encoded message exceeded the buffer capacity, the function would still return the encoded size, causing the caller to write beyond the allocated buffer bounds. This vulnerability could be triggered by large RRC configurations or constrained buffer sizes, potentially leading to memory corruption or crashes.

This fix adds an explicit bounds check after encoding. If the encoded size `(enc_rval.encoded + 7) / 8` exceeds `buffer_size`, the function now logs an error and returns 0 to indicate failure, preventing the buffer overflow.

### Changes
- `openair2/RRC/LTE/MESSAGES/asn1_msg.c`: Added buffer overflow validation after `uper_encode_to_buffer()` call in `do_RRCConnectionReconfiguration_BR()`. The check ensures the encoded byte count fits within the provided buffer size. On overflow detection, logs an error message via `LOG_E()` and returns 0 instead of proceeding.

### Testing
- Verified encoding of maximum-sized RRC reconfiguration messages with various buffer sizes to ensure proper overflow detection.
- Confirmed normal operation remains unaffected when encoded data fits within buffer bounds.
- Ran RRC unit tests to validate no regression in message generation for valid configurations.