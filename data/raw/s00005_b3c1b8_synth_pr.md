## Title: Fix race condition between timer handlers and NGAP message processing

### Summary
The NGAP gNB SCTP data indication handler suffered from a use-after-free race condition. The original buffer was freed immediately after calling the downstream message processor, but asynchronous timer expiry handlers could still attempt to access this memory, leading to potential crashes or undefined behavior under load.

This fix eliminates the race by duplicating the SCTP buffer before passing it to the message handler. The original buffer is freed immediately as required by the SCTP layer, while the duplicate is owned by the NGAP processing pipeline and any associated timer handlers. This ensures safe concurrent access patterns without modifying the SCTP contract.

### Changes
- `openair3/NGAP/ngap_gNB.c`: Modified `ngap_gNB_handle_sctp_data_ind()` to allocate a buffer duplicate using `itti_malloc()` before invoking `ngap_gNB_handle_message()` or `amf_test_s1_notify_sctp_data_ind()`. Added proper null checks and preserved the immediate free of the original SCTP buffer.

### Testing
- This is a robustness fix that prevents crashes in high-load scenarios where timer handlers interleave with message processing.
- Memory lifecycle now follows a safe ownership model: SCTP layer frees its buffer immediately, NGAP processing uses its own allocated copy.
- No protocol behavior changes; verified compilation and static analysis show no resource leaks.