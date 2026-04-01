## Title: Fix integer truncation in setup_ue_ipv4_route parameter

### Summary
The `setup_ue_ipv4_route()` function in `common/utils/tun_if.c` uses a generic `int` type for the `instance_id` parameter, which risks integer truncation when the actual UE identifier type (`ue_id_t`) differs in width. This change updates the parameter to use `ue_id_t` for type safety and consistency with the OAI codebase.

### Changes
- `common/utils/tun_if.c`: Updated `instance_id` parameter type from `int` to `ue_id_t` in `setup_ue_ipv4_route()`
- `common/utils/tun_if.h`: Added `#include "common/platform_types.h"` and updated function declaration to use `ue_id_t`

### Implementation Details
The `ue_id_t` type is the canonical UE identifier throughout OpenAirInterface. Using it prevents potential overflow issues and ensures the function signature matches the actual data being passed. The internal `table_id` calculation logic remains unchanged as it already safely handles the type conversion. This is a type safety improvement with no functional behavior changes.