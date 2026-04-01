## Title: Fix buffer overflow vulnerabilities in NR UE sidelink configuration

### Summary
Replace unsafe `sprintf` calls with bounded `snprintf` in NR UE sidelink preconfiguration functions to prevent stack buffer overflow vulnerabilities. The functions `prepare_NR_SL_SyncConfig`, `prepare_NR_SL_ResourcePool`, and `prepare_NR_SL_BWPConfigCommon` construct configuration parameter prefixes using `sprintf` without bounds checking into a fixed-size buffer (`aprefix[MAX_OPTNAME_SIZE*2 + 8]`). If configuration parameter names exceed expected lengths, this could overflow the stack buffer, leading to memory corruption and potential security exploits. The fix adds proper size specifiers using `sizeof(aprefix)` to ensure all string formatting operations respect buffer boundaries.

### Changes
- `openair2/RRC/NR_UE/rrc_sl_preconfig.c`: Replace 5 instances of `sprintf(aprefix, ...)` with `snprintf(aprefix, sizeof(aprefix), ...)` across sidelink configuration preparation functions. This ensures all constructed configuration path strings are properly bounded.

### Implementation Details
The vulnerability occurred when building nested configuration parameter paths (e.g., `SL-PRECONFIGURATION[0].SL-SYNCCONFIG-LIST[0]`). The `aprefix` buffer size is calculated as `MAX_OPTNAME_SIZE*2 + 8` to accommodate two parameter names plus index notation, but `sprintf` provided no overflow protection. The change is minimal and maintains identical functionality while enforcing memory safety.

### Testing
- Verified successful compilation with GCC 11.4.0
- Tested sidelink mode 2 initialization with maximum-length parameter names
- Confirmed no regressions in existing sidelink configuration parsing behavior
- Validated via static analysis that all string operations now respect buffer bounds