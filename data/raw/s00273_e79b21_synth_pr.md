## Title: Fix nFAPI P7 CRC indication packing and bounds checking

### Summary
The nFAPI P7 CRC indication packing functions contained multiple issues that could cause buffer overflows, incorrect serialization, and process crashes. The `pack_crc_indication_body_value()` function used an assert that would terminate the process when PDU count exceeded `NFAPI_CRC_IND_MAX_PDU`, rather than returning an error gracefully. Additionally, the instance length calculation lacked bounds checking, risking underflow, and the `push16()` call ignored its return value. In `pack_nr_crc_indication_body()`, the code block CRC array size calculation was incorrect (using commented-out code with integer division truncation instead of proper ceiling division), and the array packing call was disabled entirely.

These issues could lead to silent data corruption, memory corruption, or abrupt gNB crashes during high-load scenarios with numerous CRC indications or large transport blocks with many code blocks.

### Changes
- **nfapi/open-nFAPI/nfapi/src/nfapi_p7.c**:
  - Replaced assert with graceful error handling and early return when `number_of_crcs` exceeds maximum
  - Added bounds checking for instance length calculation to prevent pointer underflow
  - Added return value validation for `push16()` operations
  - Fixed `cb_crc_array_size` calculation using proper ceiling division: `(num_cb + 7) / 8`
  - Re-enabled and corrected `pusharray8()` call for code block CRC status array
  - Fixed typo "maxium" → "maximum" in error message

### Testing
- Verified correct serialization of CRC indications with varying PDU counts (including boundary values)
- Tested code block CRC array packing with `num_cb` values from 1 to 64
- Validated error paths return 0 instead of crashing
- Confirmed backward compatibility with existing nFAPI interfaces