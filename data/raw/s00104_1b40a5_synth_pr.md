## Title: Fix use-after-free vulnerability in bfly5_tw1 FFT butterfly function

### Summary
The `bfly5_tw1` function in the OAI DFT library performs a 5-point butterfly operation for FFT computations using SIMD intrinsics. The original implementation repeatedly dereferenced input pointers (`x0` through `x4`) throughout the function body. If the caller freed the input memory buffer after the first dereference (or during the function execution in multi-threaded contexts), subsequent accesses would operate on freed memory, leading to undefined behavior, potential crashes, or silent data corruption.

The vulnerability manifested as intermittent segmentation faults during high-throughput PHY processing, particularly under memory pressure when custom memory allocators were active.

### Changes
- `openair1/PHY/TOOLS/oai_dfts.c`: Modified `bfly5_tw1()` to load all input values into local variables (`local_x0` through `local_x4`) at function entry. All subsequent computations now use these cached values instead of repeatedly dereferencing the input pointers. This ensures the function operates on consistent data regardless of the caller's memory management.

### Implementation Details
The fix introduces five `simde__m128i` local variables that capture the input values via a single dereference at the start of the function. The complex arithmetic operations (twiddle factor multiplications, additions, and MAC operations) now reference these locals exclusively. This pattern eliminates the use-after-free risk while maintaining the same computational semantics and performance characteristics, as the data is loaded into registers immediately and stays in cache throughout the function's execution.

### Testing
- Verified FFT output bit-exactness against golden reference vectors for all transform sizes using `bfly5_tw1`
- Ran `phy_simulator` test suite with AddressSanitizer enabled; confirmed no memory errors
- Executed multi-threaded PHY load tests; eliminated previously observed intermittent segfaults