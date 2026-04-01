## Title: Fix uninitialized memory read in Bda2Str function

### Summary
This PR fixes an uninitialized memory read issue in the `Bda2Str` function within the Cordio BLE stack. The function was vulnerable to reading from uninitialized memory when a NULL pointer was passed as input, potentially leading to undefined behavior or security vulnerabilities.

The root cause was the lack of a NULL pointer check before processing the input address. When `pAddr` was NULL, the function would still attempt to increment and dereference the pointer, resulting in undefined behavior.

The fix adds a proper NULL pointer check at the beginning of the function. When a NULL pointer is detected, the function now returns a safe default string of zeros, preventing any uninitialized memory access while maintaining backward compatibility.

### Changes
- `connectivity/FEATURE_BLE/libraries/cordio_stack/wsf/sources/util/bda.c`: Added NULL pointer validation to `Bda2Str()` function. When `pAddr` is NULL, the function now initializes and returns a string of zeros instead of attempting to process invalid memory.

### Impact
This change improves the robustness and security of the BLE stack by preventing potential crashes or information disclosure through uninitialized memory reads. The fix is backward compatible and maintains all existing functionality for valid inputs.