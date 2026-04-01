## Title: Fix buffer overflow and operator precedence in EPS QoS decoder

### Summary
The EPS QoS decoder suffers from two critical issues that can lead to out-of-bounds memory access and incorrect parsing:

1. **Buffer overflow vulnerability**: The internal `decode_eps_qos_bit_rates()` function reads 4 bytes from the buffer without verifying sufficient space remains, causing potential out-of-bounds reads.

2. **Operator precedence bug**: Length validation uses `ielen > 2 + (iei > 0) ? 1 : 0` which evaluates as `(ielen > 2) + (iei > 0) ? 1 : 0` due to operator precedence. This causes incorrect detection of optional field presence, leading to parsing the wrong memory regions.

The fix adds buffer length validation to the decoder and corrects the precedence by parenthesizing ternary expressions. Error propagation is added to handle truncated messages gracefully.

### Changes
- **openair3/NAS/COMMON/IES/EpsQualityOfService.c**:
  - Modified `decode_eps_qos_bit_rates()` to accept `buflen` parameter and validate minimum 4-byte requirement
  - Fixed operator precedence in field presence checks: `(ielen > (2 + (iei > 0 ? 1 : 0)))` and `(ielen > (6 + (iei > 0 ? 1 : 0)))`
  - Added error handling for decode failures with `-1` return value propagation
  - Pass remaining buffer length (`len - decoded`) to prevent OOB reads

### Testing
- Verified correct parsing of EPS QoS IE with and without optional bitRates and bitRatesExt fields
- Tested with malformed messages shorter than minimum length to ensure proper error handling
- Confirmed no regression in NAS message processing for attach and bearer setup procedures