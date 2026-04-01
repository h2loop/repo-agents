## Title: Fix SRS periodicity offset bounds checking in RRC configuration

### Summary
The `configure_periodic_srs` function in the NR RRC configuration module was assigning raw offset values without validating them against the selected periodicity bounds. When offset values exceeded the maximum allowed for a given periodicity (e.g., offset ≥ 4 for sl4 periodicity), invalid configurations could be created, leading to potential CRC computation errors and false positive error detection downstream in the MAC layer.

The fix applies modulo arithmetic to ensure all offset values are constrained within valid ranges defined by 3GPP TS 38.331, preventing out-of-bounds access and ensuring consistent SRS resource allocation behavior.

### Changes
- `openair2/RRC/NR/nr_rrc_config.c`: Applied modulo operations to SRS periodicity offset assignments in `configure_periodic_srs()` to bound values within their respective periodicity ranges (e.g., `offset % 4` for sl4, `offset % 5` for sl5, etc.)

### Implementation Details
The change modifies 12 periodicity configuration branches to use `offset % period` pattern, ensuring the offset is always less than the period value. This aligns with the ASN.1 PER encoding constraints for SRS-PeriodicityAndOffset and prevents misconfiguration that could propagate to lower layers.

### Testing
- Verified offset wrapping behavior for all supported periodicity values (sl4 through sl320)
- Validated against 3GPP conformance test cases for SRS resource configuration
- Confirmed no regressions in RRC connection setup procedures with SRS configuration