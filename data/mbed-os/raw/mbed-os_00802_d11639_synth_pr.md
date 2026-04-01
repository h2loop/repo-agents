## Title: Initialize ext_key_usage structure in x509_get_ext_key_usage to prevent undefined behavior

### Summary
This PR addresses a potential security and correctness issue in the X.509 certificate parsing code where the `ext_key_usage` structure was not being initialized before use in the `x509_get_ext_key_usage` function. This could lead to undefined behavior if the structure contained garbage data, particularly in error paths or when processing malformed certificates.

The fix ensures the `mbedtls_x509_sequence` structure is zero-initialized before populating it, preventing any potential information leakage or incorrect parsing behavior. This is a defensive programming improvement that enhances the robustness of the certificate parsing logic.

### Changes
- `connectivity/mbedtls/source/x509_crt.c`: Added `memset` call to initialize the `ext_key_usage` structure to zero before processing in `x509_get_ext_key_usage` function.

### Impact
This change affects X.509 certificate parsing, particularly when processing the Extended Key Usage extension. It improves the reliability and security of certificate validation by ensuring predictable behavior regardless of the initial memory state. The fix has minimal performance impact as it only affects the initialization phase of extension parsing.