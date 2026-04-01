## Title: Fix incorrect IPv4 address validation in config_assign_ipv4addr

### Summary
The `config_assign_ipv4addr()` function incorrectly rejects valid IPv4 addresses where the first octet is zero (e.g., `0.0.0.0`, `0.1.2.3`). The bug originates from an erroneous check `*(cfgoptions->uptr) > 0` that examines the first byte of the network-byte-order result from `inet_pton()`. This condition is both semantically wrong (addresses starting with 0 are valid) and redundant (since `inet_pton()` already validates address format). This caused configuration parsing to fail for legitimate IP addresses, potentially preventing proper network interface configuration in certain deployment scenarios.

The fix removes the invalid byte check, relying solely on `inet_pton()`'s return value to validate the IPv4 address.

### Changes
- `common/config/config_common.c`: Removed the erroneous `&& *(cfgoptions->uptr) > 0` condition from the validation logic in `config_assign_ipv4addr()`, leaving only the `inet_pton()` result check.

### Testing
- Verified that IPv4 addresses with leading zero octets (`0.0.0.0`, `0.1.2.3`) are now correctly accepted
- Confirmed that malformed IPv4 addresses are still properly rejected by `inet_pton()`
- Tested configuration loading with various valid and invalid IP address formats