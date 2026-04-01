## Title: Fix pointer corruption in dft4096 scaling loop

### Summary
The `dft4096` function had a critical pointer arithmetic bug in its output scaling section that corrupted the base pointer during iteration. The loop directly incremented `y256` while performing scaling operations, causing the pointer to advance beyond the intended buffer bounds. This resulted in undefined behavior and potential memory corruption, which manifested as incorrect data in the DFT output buffer and could trigger downstream signaling errors.

The fix preserves the base pointer by introducing a separate iterator `y256p`. The scaling loop now uses this temporary pointer for traversal while leaving `y256` unchanged, ensuring correct memory access patterns and preventing buffer overruns.

### Changes
- `openair1/PHY/TOOLS/oai_dfts.c`: Added `y256p = y256;` initialization before the scaling loop and updated all pointer arithmetic within the loop to use `y256p` instead of `y256`. This prevents base pointer corruption and ensures proper scaling of all 4096 output elements.

### Testing
- Verified DFT output matches reference implementation for 4096-point transforms
- Ran PHY layer unit tests with multiple input patterns; all pass
- Tested with nr-uesoftmodem in loopback mode; no signaling anomalies observed
- Confirmed memory access patterns are correct using AddressSanitizer