## Title: Fix use-after-free in GOEP server setpath handler

### Summary
The GOEP server's setpath handler in the OBEX implementation contained a use-after-free vulnerability where a network buffer was accessed after being freed. When processing a setpath request, the function would free the net_buf containing the request data, but subsequent error handling paths attempted to read from the already-freed buffer to extract header information for response formatting. This could lead to memory corruption, crashes, or potentially exploitable behavior if an attacker crafted malicious OBEX setpath packets.

The fix ensures that all required data is extracted from the buffer before it is freed, and removes any accesses to the buffer after the free point. The response is now constructed using locally saved values rather than dereferencing the freed buffer pointer.

### Changes
- `subsys/bluetooth/host/classic/obex.c`: In `obex_server_setpath()`, saved required header fields to local variables before freeing the net_buf. Removed buffer dereference after the free call in error handling paths.

### Testing
- Verified with fuzzing tests sending malformed setpath requests to the GOEP server; no crashes or memory errors observed.
- Ran ASan-enabled build with OBEX test suite: zero use-after-free reports.
- Confirmed normal setpath operations continue to work correctly with valid requests.