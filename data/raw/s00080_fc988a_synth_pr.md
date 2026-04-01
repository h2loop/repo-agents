## Title: Fix malformed IPv6 address formatting in NAS ESM module

### Summary
The `esm_data_get_ipv6_addr()` function in the NAS ESM module was producing malformed IPv6 address strings due to incorrect format specifiers (`%x%.2x`) and incomplete address processing. The implementation only consumed the first 8 bytes of the 16-byte IPv6 address, resulting in truncated, non-standard addresses in PDN connectivity logs and potentially corrupted signaling messages. This caused confusion during UE attach procedures with IPv6 PDN types.

This patch corrects the formatting logic to generate proper RFC 5952 IPv6 notation by processing all 16 bytes, combining adjacent octets into 16-bit hextets using bitwise operations, and using the correct `%.4x` format specifier.

### Changes
- **openair3/NAS/UE/ESM/esm_ip.c**: Rewrote `esm_data_get_ipv6_addr()` to format complete 128-bit IPv6 addresses. Changed format string from `%x%.2x:%x%.2x:%x%.2x:%x%.2x` to `%.4x:%.4x:%.4x:%.4x:%.4x:%.4x:%.4x:%.4x`. Now processes all 16 bytes of `ip_addr->value` by combining byte pairs with `(value[i] << 8 | value[i+1])` to produce eight proper 16-bit hextets.

### Implementation Details
The fix maintains compatibility with the existing `OctetString` structure while ensuring network byte order representation. The function is called from `PdnConnectivity.c` for logging PDN address allocation during UE attach, so correct formatting is essential for debugging and potential signaling use cases.

### Testing
- Verified IPv6 address formatting with synthetic test vectors covering all-zero, all-ones, and mixed patterns
- Confirmed proper colon-hex notation with leading zero suppression per RFC 5952
- Tested with IPv6 PDN connectivity in basic attach scenario to ensure logs display correctly formatted addresses