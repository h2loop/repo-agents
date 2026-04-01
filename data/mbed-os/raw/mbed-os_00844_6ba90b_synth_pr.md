## Title: Fix Uninitialized `md_type` in PKCS#5 PBKDF2 Parameter Parsing

### Summary
This PR resolves a potential use of uninitialized memory in the `pkcs5_parse_pbkdf2_params` function within Mbed TLS. The `md_type` parameter was not being initialized to its default value (`MBEDTLS_MD_SHA1`) before parsing the ASN.1 structure, which could lead to undefined behavior if the optional `prf` field was absent from the PBKDF2 parameters.

The fix ensures that `*md_type` is explicitly set to `MBEDTLS_MD_SHA1` at the start of the function, conforming to the PKCS#5 specification that mandates SHA-1 as the default pseudorandom function.

### Changes
- `connectivity/mbedtls/source/pkcs5.c`: Initialize `*md_type` to `MBEDTLS_MD_SHA1` at the beginning of `pkcs5_parse_pbkdf2_params`.

### Testing
- Verified correct default assignment when `prf` field is omitted.
- Confirmed no regression in existing PBKDF2 parsing functionality with explicit `prf`.