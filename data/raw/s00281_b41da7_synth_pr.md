## Title: Fix missing error propagation in NB-IoT system information indication unpacker

### Summary
The `unpack_nb_iot_system_information_indication_value` function in `nfapi_p4.c` was silently returning failure (0) on parsing errors without logging the failure reason or invoking the codec's error callback. This made debugging NB-IoT system information processing issues difficult and inconsistent with other unpack functions in the codebase.

This fix adds explicit `NFAPI_TRACE` error logging for each failure condition and calls the `on_error()` callback (provided via `nfapi_p4_p5_codec_config_t`) before returning 0. This ensures errors are properly signaled up the call stack through the TLV unpacking chain and provides clear diagnostic information when NB-IoT SIB parsing fails.

### Changes
- `nfapi/open-nFAPI/nfapi/src/nfapi_p4.c`: Enhanced error handling in `unpack_nb_iot_system_information_indication_value` by adding error trace logging and `on_error()` callback invocations for three failure scenarios: (1) failure to unpack SIB type or length fields, (2) SIB length exceeding `NFAPI_MAX_SIB_LENGTH`, and (3) failure to unpack SIB data array.

### Implementation Details
The `on_error()` callback is a standard mechanism in the nFAPI codec configuration that allows upstream components to be notified of parsing failures. This change aligns the NB-IoT unpacker with the error handling pattern used by other system information unpackers in the same module.

### Testing
- Verified that error paths now produce appropriate trace logs when malformed NB-IoT system information messages are processed.
- Confirmed that the `on_error()` callback is invoked on parsing failures, enabling proper error propagation to calling layers.