## Title: Add error handling to NAS ESM message container XML dump functions

### Summary
The `dump_esm_message_container_xml()` function in the NAS ESM module called `dump_octet_string_xml()` without checking its return value, risking undefined behavior if XML generation failed. The underlying `dump_octet_string_xml()` function also lacked proper error handling for `snprintf()` failures, NULL pointer inputs, and potential buffer overflows. These issues could lead to segmentation faults or corrupted debug output when processing malformed ESM message containers or when buffer limits are exceeded.

This fix implements comprehensive defensive programming practices by validating inputs, checking return values, and preventing buffer overflows. When errors occur, the functions now return meaningful XML-formatted error messages instead of crashing or producing undefined behavior.

### Changes
- `openair3/NAS/COMMON/IES/EsmMessageContainer.c`: Added NULL validation for the ESM message container and the output from `dump_octet_string_xml()`. Added error handling that prints `<Error>` tags in XML output when failures occur.
- `openair3/NAS/COMMON/UTIL/OctetString.c`: Added NULL pointer checks for input validation, verification of `snprintf()` return values to catch encoding errors, and buffer size tracking to prevent overflows. Returns descriptive error messages embedded in XML when failures are detected.

### Testing
- Verified graceful handling of NULL pointer inputs
- Confirmed error messages are properly formatted as valid XML
- Ensured normal operation remains unchanged for valid inputs
- No regressions observed in existing NAS protocol tests