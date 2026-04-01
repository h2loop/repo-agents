## Title: Add mutex protection for shared state in config response unpacking

### Summary
Fix a race condition in the nFAPI P5 configuration response handling by adding optional mutex protection around the TLV unpacking critical section. The `unpack_config_response` function accesses shared state through callbacks invoked by `unpack_tlv_list`, but previously lacked synchronization when called from multiple threads. This could lead to data corruption or inconsistent state updates.

This change introduces an optional mutex pointer in the codec configuration structure, allowing callers to provide synchronization when needed. The mutex is only acquired if provided, maintaining backward compatibility with existing single-threaded code paths.

### Changes
- `nfapi/open-nFAPI/nfapi/public_inc/nfapi_interface.h`: Added `pthread_mutex_t* mutex` field to `nfapi_p4_p5_codec_config_t` for optional thread-safe callback execution
- `nfapi/open-nFAPI/nfapi/src/nfapi_p5.c`: Modified `unpack_config_response()` to conditionally lock/unlock the provided mutex around the `unpack_tlv_list()` call, protecting the critical section that accesses shared state

### Implementation Details
- The mutex pointer is optional (nullable) to preserve backward compatibility
- Locking is performed only when `config` and `config->mutex` are non-NULL
- The lock scope covers the entire TLV unpacking operation to ensure atomic access to shared data structures
- Error handling preserves the original behavior while ensuring the mutex is always unlocked appropriately

### Testing
- Verified thread safety analysis no longer reports the previous race condition
- Confirmed existing single-threaded code paths continue to work without modification
- Validated that providing a mutex properly serializes concurrent access to shared state