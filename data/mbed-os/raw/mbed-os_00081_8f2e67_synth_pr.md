## Title: Prevent blocking RTOS API calls from interrupt context in SNMP functions

### Summary
This PR fixes an issue where SNMP OID conversion functions (`snmp_oid_to_ip4`, `snmp_ip4_to_oid`, `snmp_oid_to_ip6`, `snmp_ip6_to_oid`) could be called from interrupt context, potentially leading to undefined behavior or system crashes due to blocking RTOS API usage. The functions now check if they are being executed in an interrupt context and safely handle such cases by returning appropriate error values or default data instead of proceeding with potentially unsafe operations.

### Changes
- **connectivity/lwipstack/lwip/src/apps/snmp/lwip_snmp_core.c**: Added interrupt context checks using `core_util_is_isr_active()` for Mbed OS targets. When called from an interrupt context, the functions now return safe defaults or error codes instead of executing normal conversion logic that might involve blocking calls.

### Testing
- Verified that the functions correctly detect interrupt context and return appropriate values.
- Confirmed normal operation when called from thread context.
- No regressions observed in SNMP functionality during standard operations.