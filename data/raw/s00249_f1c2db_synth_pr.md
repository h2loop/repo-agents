## Title: Fix uninitialized memory read in F1AP served cell info decoder

### Summary
The `decode_served_cell_info()` function reads uninitialized memory when decoding F1AP Served Cell Information elements. The output structure is not zero-initialized before parsing, causing undefined behavior when optional Information Elements (IEs) are absent from the message. Fields corresponding to missing IEs retain whatever garbage values were present in the uninitialized memory, which can lead to crashes or incorrect processing downstream.

The fix adds explicit zero-initialization of the entire output structure using `memset()` before any decoding occurs. This ensures all fields have well-defined default values (typically NULL for pointers and 0 for scalars) when their corresponding IEs are not present in the F1AP PDU, eliminating the uninitialized read vulnerability.

### Changes
- `openair2/F1AP/lib/f1ap_interface_management.c`: 
  - Added `memset(info, 0, sizeof(*info))` at function entry to initialize the output structure
  - Added NULL check assertion for the `info` pointer parameter
  - Positioned initialization immediately after validation, before any IE decoding logic

### Implementation Details
The initialization follows OAI's defensive coding patterns and occurs early in the function to guarantee all code paths benefit from the fix. This resolves potential security and stability issues without changing the decoding logic itself, maintaining backward compatibility with existing F1AP message handling.