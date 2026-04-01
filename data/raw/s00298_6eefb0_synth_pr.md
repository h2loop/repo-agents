## Title: Fix race condition in NFAPI P5 PHY info packing

### Summary
Fix a race condition in the NFAPI P5 parameter packing code where shared RF configuration data could be accessed concurrently from multiple threads without synchronization. The vulnerability existed in `pack_pnf_phy_info()` when packing RF config arrays, leading to potential data corruption and undefined behavior under multi-threaded operation.

The fix introduces an optional mutex mechanism in the codec configuration structure, allowing callers to provide thread-safe access to shared data during packing operations. This is a minimal, opt-in solution that doesn't break existing single-threaded usage while enabling safe concurrent access when needed.

### Changes
- **nfapi/open-nFAPI/nfapi/public_inc/nfapi_interface.h**: Added `pthread.h` include and a new `mutex` field to `nfapi_p4_p5_codec_config_t` structure for optional thread-safety
- **nfapi/open-nFAPI/nfapi/src/nfapi_p5.c**: Modified `pack_pnf_phy_info()` to accept codec config parameter and wrap RF config array packing with mutex lock/unlock when a mutex is provided

### Implementation Details
The mutex is optional and user-managed - if `config->mutex` is non-NULL, the packing function acquires the lock before accessing shared RF config data and releases it immediately after. This protects the critical section where `phy->rf_config` and `phy->excluded_rf_config` arrays are serialized. The change maintains backward compatibility by checking for NULL mutex and skipping synchronization when not provided.