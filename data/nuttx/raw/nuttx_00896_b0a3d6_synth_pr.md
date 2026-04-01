## Title: Fix Memory Leak in VEML6070 Driver by Adding Unregister Function

### Summary
This PR addresses a memory leak in the VEML6070 sensor driver where allocated private data was not freed when the device was unregistered. The driver allocated memory using `kmm_malloc` during registration but lacked a corresponding cleanup mechanism, leading to memory leaks when the driver was unloaded.

The fix implements a proper `veml6070_unregister` function that safely unregisters the character driver and frees the allocated private data structure. This ensures proper resource management and prevents memory leaks during driver lifecycle management.

### Changes
- **drivers/sensors/veml6070.c**: 
  - Added `veml6070_unregister` function to properly clean up allocated resources
  - Improved error handling in `veml6070_register` to ensure memory is freed on initialization failures
- **include/nuttx/sensors/veml6070.h**: 
  - Added function prototype for `veml6070_unregister`

### Why
Without this fix, each registration/unregistration cycle of the VEML6070 driver would leak memory, which is particularly problematic in embedded systems with limited memory resources. The addition of the unregister function provides a clean API for driver management and ensures proper resource cleanup.

### Testing
The fix follows NuttX driver patterns and maintains compatibility with existing driver registration APIs. The implementation properly handles inode reference counting and memory deallocation.