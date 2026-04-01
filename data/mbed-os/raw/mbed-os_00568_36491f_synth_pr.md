## Title: Fix buffer overflow in L2CACHE_LockdownByWayEnable due to missing bounds check

### Summary
The `L2CACHE_LockdownByWayEnable` function in the NXP MCUXpresso cache driver is vulnerable to a buffer overflow when an invalid `masterId` parameter is passed. The function accesses the `LOCKDOWN[masterId]` array without runtime validation, potentially leading to out-of-bounds memory access if `masterId` exceeds `L2CACHE_LOCKDOWN_REGNUM`.

While the function includes `assert()` calls for bounds checking, these are typically disabled in release builds, leaving the vulnerability exploitable in production code. This fix adds explicit runtime bounds checking that returns early if `masterId` is out of range, preventing the buffer overflow while maintaining performance in the valid case.

### Changes
- `targets/TARGET_NXP/TARGET_MCUXpresso_MCUS/TARGET_MIMXRT1050/drivers/fsl_cache.c`: Added runtime bounds check for `masterId` parameter before array access
- `targets/TARGET_NXP/TARGET_MCUXpresso_MCUS/TARGET_MIMXRT1170/drivers/fsl_cache.c`: Added identical bounds check for consistency across NXP platforms

### Why
This change mitigates a potential security vulnerability where malicious or corrupted input could cause memory corruption in the L2 cache controller, which could lead to system instability or information disclosure. The fix is minimal and maintains backward compatibility while closing the security gap in release builds.