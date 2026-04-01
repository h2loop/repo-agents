## Title: Fix stack buffer overflow in nas_proc_get_loc_info

### Summary
The `nas_proc_get_loc_info()` function in the NAS UE subsystem uses `sprintf()` to format TAC and CI values into fixed-size caller-provided buffers without bounds checking. This can write beyond buffer boundaries if the hex formatting produces more characters than expected, leading to stack corruption and potential security vulnerabilities.

This patch replaces the unsafe `sprintf()` calls with `snprintf()` and adds explicit size limits that account for the null terminator. The TAC buffer (4 hex digits) is limited to 5 bytes, and the CI buffer (8 hex digits) is limited to 9 bytes, preventing overflow while maintaining identical output formatting.

### Changes
- `openair3/NAS/UE/nas_proc.c`: Replace `sprintf()` with `snprintf()` in `nas_proc_get_loc_info()` for TAC and CI formatting, adding size parameters of 5 and 9 respectively to ensure buffer safety.

### Implementation Details
The size parameters are set to `strlen(formatted_string) + 1` to accommodate the hexadecimal output plus null terminator: 4 hex digits + `\0` = 5 bytes for TAC, and 8 hex digits + `\0` = 9 bytes for CI. This preserves the original formatting behavior while eliminating the overflow risk.

### Testing
- Verified that TAC and CI strings are correctly formatted as 4-digit and 8-digit hexadecimal values respectively
- Confirmed no functional regression in location information reporting
- Static analysis confirms the buffer overflow path is eliminated