## Title: Fix integer truncation in file descriptor getter functions

### Summary
File descriptors can exceed the range of a 32-bit `int` on some systems or under certain runtime conditions. The `device_get_fd()` and `socket_get_fd()` functions were returning `int`, which could cause integer truncation when the actual file descriptor value is stored or passed through function pointers. This change widens the return type to `long int` to safely accommodate file descriptor values across all supported platforms.

### Changes
- `openair3/NAS/COMMON/UTIL/device.c`: Changed `device_get_fd()` return type from `int` to `long int`
- `openair3/NAS/COMMON/UTIL/device.h`: Updated function declaration for `device_get_fd()`
- `openair3/NAS/COMMON/UTIL/socket.c`: Changed `socket_get_fd()` return type from `int` to `long int`
- `openair3/NAS/COMMON/UTIL/socket.h`: Updated function declaration for `socket_get_fd()`
- `openair3/NAS/UE/API/USER/user_api_defs.h`: Updated `getfd` function pointer typedef from `int (*getfd)(const void*)` to `long int (*getfd)(const void*)`

### Implementation Details
The change maintains backward compatibility while preventing potential integer overflow. The `fd` field within the internal `device_id_s` and `socket_id_s` structures remains typed as `int` (matching the system type for file descriptors), but the getter functions now promote the value to `long int` for safe propagation through the NAS layer's generic function pointer interface. This ensures consistent type handling across all call sites without requiring changes to the underlying socket or device implementations.