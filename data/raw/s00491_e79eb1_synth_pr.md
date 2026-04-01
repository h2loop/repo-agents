## Title: Remove commented dead code in ProtocolConfigurationOptions decoder

### Summary
Remove an obsolete commented-out line in the `decode_protocol_configuration_options()` function that represented dead code from a previous implementation attempt. This commented line incorrectly demonstrated parameter passing to the `IES_DECODE_U16` macro and was superseded by the correct implementation in the subsequent while loop. Its presence could mislead developers about the proper macro usage pattern. Removing it improves code clarity without affecting functionality.

### Changes
- `openair3/NAS/COMMON/IES/ProtocolConfigurationOptions.c`: Removed commented-out `IES_DECODE_U16` macro call on line 59.

### Testing
- Verified successful compilation of the modified NAS module
- Confirmed the active `IES_DECODE_U16` invocations in the while loop (starting line 60) correctly follow the macro definition from `TLVDecoder.h` by passing buffer pointer and decoded offset as separate parameters
- No functional impact on NAS protocol configuration options decoding logic