## Title: Fix integer overflow in NR sidelink resource pool preparation

### Summary
The `prepare_NR_SL_ResourcePool` function in the NR UE sidelink preconfiguration code contains an integer overflow vulnerability when masking unused bits in the time resource buffer. The expression `0 - (1 << bits_unused)` relies on signed integer underflow, which is undefined behavior in C and can lead to incorrect bitmask generation on certain compilers or architectures. This patch replaces the unsafe underflow-based mask calculation with a well-defined bitwise operation that safely clears the unused least significant bits.

### Changes
- `openair2/RRC/NR_UE/rrc_sl_preconfig.c`: Replaced the integer underflow expression with explicit bitmask calculation using bitwise NOT operator

### Implementation Details
The fix introduces an intermediate `uint8_t mask` variable that computes `~((1 << bits_unused) - 1)` to create a proper mask for clearing unused bits. This approach avoids undefined behavior while maintaining the same functional result of masking out unused bits in the last byte of the time resource buffer. The change is minimal and preserves all existing logic for NR sidelink resource pool configuration.