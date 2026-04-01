## Title: Fix missing null terminator in UCI stats dump buffer

### Summary
The `dump_uci_stats()` function in the PUCCH module builds a formatted statistics report using `sprintf()` into a fixed-size character buffer, but fails to null-terminate the string before passing it to printing functions. This causes out-of-bounds memory reads when `fprintf()` or `printf()` attempts to determine the string length, leading to potential segmentation faults, buffer overreads, or garbage output in logs. The issue manifests downstream of `pucchfmt3_AvgSym()` due to the call chain during PUCCH processing.

This fix ensures proper string termination by explicitly adding the null terminator after the final `sprintf()` operation.

### Changes
- `openair1/PHY/LTE_TRANSPORT/pucch.c`: Added `output[strpos] = '\0'` after building the statistics string to properly terminate the buffer before printing.

### Implementation Details
The buffer `output[16384]` is populated incrementally via `sprintf()` calls that track the write position in `strpos`. The fix adds a single assignment to set the null terminator at the final write position, preventing the printing functions from reading beyond the intended buffer content.

### Testing
- Verified that UCI statistics now print correctly without garbage characters or crashes
- Confirmed no buffer overflow occurs when `strpos` approaches buffer bounds
- Validated normal PUCCH operation continues unaffected