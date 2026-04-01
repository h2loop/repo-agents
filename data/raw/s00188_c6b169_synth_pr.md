## Title: Fix stack buffer overflow in telnet server process stats command

### Summary
The telnet server's process stats command contained a stack buffer overflow vulnerability when parsing `/proc/[pid]/stat` files. The `process_command` function used unsafe `sprintf()` calls to format process information into a fixed-size 1024-byte stack buffer (`prntline`) without bounds checking. Malicious or unusually long process names and stat fields could overflow the buffer, corrupting the stack and potentially causing crashes or arbitrary code execution.

This fix replaces all `sprintf()` calls with `snprintf()` and implements proper bounds tracking. A `remaining` variable tracks available buffer space after each write, ensuring the buffer is never exceeded regardless of input field lengths.

### Changes
- `common/utils/telnetsrv/telnetsrv_proccmd.c`: 
  - Added `size_t remaining = sizeof(prntline)` to track buffer space
  - Replaced all `sprintf(lptr, ...)` calls with `snprintf(lptr, remaining, ...)`
  - Added bounds checking after each write: `remaining = (lptr > prntline) ? sizeof(prntline) - (lptr - prntline) : 0`
  - Replaced `sprintf(toksep, ...)` with `snprintf(toksep, sizeof(toksep), ...)` for token separator safety

### Testing
- Verified correct display of process stats via telnet interface
- Tested with long process names to ensure proper truncation without overflow
- Confirmed buffer boundaries are respected under various input conditions