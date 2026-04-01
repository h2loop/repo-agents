## Title: Fix integer overflow in TLV length calculation

### Summary
Fix integer overflow vulnerability in the TLV (Type-Length-Value) packing functions used throughout the nFAPI interface. The `pack_tlv()` and `pack_nr_tlv()` functions calculate length by subtracting pointers (`(*ppWritePackedMsg) - pStartOfValue`) and directly assign the result to a `uint16_t` field. When the packed data exceeds 65,535 bytes, this causes silent integer truncation, producing incorrect length headers that can lead to protocol errors or buffer overruns.

This change adds explicit bounds checking before the cast to `uint16_t`. The calculated length is stored in a `ptrdiff_t` variable first, validated against `UINT16_MAX`, and only written if it fits within the 16-bit field. If the length exceeds the maximum, the function logs an error and returns failure instead of producing a corrupted TLV header.

### Changes
- `nfapi/open-nFAPI/common/src/nfapi.c`: 
  - In `pack_tlv()`: Added overflow check for length calculation before casting to `uint16_t`
  - In `pack_nr_tlv()`: Added identical overflow check for NR-specific TLV packing
  - Added `#include <limits.h>` for `UINT16_MAX` definition

### Implementation Details
The fix uses `ptrdiff_t` to capture the full pointer difference, validates `if (calculated_length > UINT16_MAX)`, and returns 0 on error. This prevents the silent truncation that occurred when large messages were packed, particularly affecting UL configuration requests with extensive transmission parameter data. The error logging helps diagnose when message sizes approach the nFAPI protocol limit.