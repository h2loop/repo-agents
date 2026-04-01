## Title: Add NULL sentinel to mode descriptor array in PHY coding module

### Summary
The `modedesc` string array in `coding_load.c` lacked a NULL terminator, creating a potential out-of-bounds read vulnerability when accessed with an invalid mode index. The array maps decoding mode constants to human-readable strings for logging, but without a sentinel value, any out-of-range access would read beyond allocated memory.

This fix adds a NULL sentinel as the final element of the `modedesc` array. This defensive programming practice ensures that any inadvertent out-of-bounds access returns NULL rather than garbage memory, making the failure mode predictable and easier to debug. The change aligns with the existing code comment stating that the table must match the `MODE_DECODE_XXX` macros defined in `PHY/defs.h`.

### Changes
- `openair1/PHY/CODING/coding_load.c`: Added NULL sentinel to the `modedesc` array to prevent out-of-bounds reads when accessing mode descriptions.

### Implementation Details
The `modedesc` array is used at line 178 in `prnt()` calls to log the current decoding mode. While the `curmode` variable is currently bounds-checked before use, the NULL sentinel provides an additional layer of safety against future refactoring or unexpected code paths that might access the array with an invalid index.

### Testing
- Verified compilation succeeds with the change
- Confirmed telnet command `coding mode` displays correctly for all valid modes (none, sse, C, avx2)
- No functional behavior changes; this is a hardening fix