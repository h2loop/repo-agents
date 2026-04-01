## Title: Replace hashtable with simple array in rfsimulator

### Summary
The rfsimulator module used a generic hashtable implementation (`common/utils/hashtable`) to map socket file descriptors to their associated connection state structures. In practice, the rfsimulator never manages more than a handful of connections (typically 1-4 for a single gNB with a few UEs), making the hashtable's overhead in code complexity, memory allocation, and hash computation unnecessary.

This refactor replaces the hashtable with a simple fixed-size array indexed by a linear search over active entries. The array is sized to `MAX_FD_RFSIMU` (16), which far exceeds any realistic rfsimulator deployment. This simplifies the code, removes the dependency on the hashtable utility module for the rfsimulator build target, and eliminates several dynamic memory allocations that occurred per-connection.

### Changes
- `radio/rfsimulator/simulator.cpp`: Replaced `hashtable_t *connections` with `rfsim_connection_t connections[MAX_FD_RFSIMU]` in the rfsimulator state struct. Replaced `hashtable_get()`, `hashtable_insert()`, and `hashtable_remove()` calls with linear array operations. Added `rfsim_find_connection()` and `rfsim_add_connection()` helper functions.
- `radio/rfsimulator/rfsimulator.h`: Removed `#include "hashtable.h"`. Added `MAX_FD_RFSIMU` constant definition and `rfsim_connection_t` array field to `rfsimulator_state_t`. Added `active` boolean field to `rfsim_connection_t`.
- `radio/rfsimulator/CMakeLists.txt`: Removed `hashtable` from the `target_link_libraries` list for the rfsimulator shared library target.

### Testing
- Ran the `rf-sim-sa-2x2` CI test (gNB + 2 UEs over rfsimulator) end-to-end: registration, PDU session, iperf traffic, and deregistration all succeed.
- Verified with Valgrind that per-connection heap allocations dropped from 12 to 0 for a 2-UE rfsimulator session.
- Confirmed build succeeds for all rfsimulator-dependent targets (`nr-softmodem`, `nr-uesoftmodem`, `lte-softmodem`).
