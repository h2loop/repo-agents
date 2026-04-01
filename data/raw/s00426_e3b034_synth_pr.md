## Title: Fix DFT/IDFT buffer size miscalculation affecting power control

### Summary
Correct buffer size calculation in DFT/IDFT implementations that caused incorrect transmit power levels in the PHY layer. The bug stemmed from using `sizeof tmp` (compile-time array size) instead of the actual data size `sz*2*sizeof(int16_t)` in memcpy operations. This miscalculation led to buffer overruns and corrupted frequency domain data, which propagated to power control calculations downstream of the main processing path. The issue primarily manifested when processing non-aligned input buffers, causing the PHY to compute incorrect power scaling factors.

### Changes
- **openair1/PHY/TOOLS/oai_dfts.c**: 
  - Fixed memcpy size in `dft_implementation()` from `sizeof tmp` to `sz*2*sizeof(int16_t)`
  - Fixed memcpy size in `idft_implementation()` with same correction
  - Updated alignment mask logic to conditionally apply 0x1F alignment only for non-multiples of 3
  - Corrected log message from "DFT called" to "IDFT called" in inverse transform path

- **openair1/PHY/TOOLS/oai_dfts_neon.c**:
  - Applied identical memcpy size fix in NEON-optimized `dft_implementation()`
  - Added conditional alignment check for multiples of 3 (no NEON implementation exists for these sizes)

### Implementation Details
The root cause was conflating stack array size with actual data size. The `tmp` buffer is allocated with compile-time constant `sz*2`, but `sz` is runtime-determined and can be smaller than the array bound. Using `sizeof tmp` caused memcpy to read/write beyond valid data, corrupting adjacent stack variables used in power control calculations.

### Testing
- Verified DFT/IDFT numerical accuracy with unit tests for all size indices
- Validated power control loop stability under maximum UE load
- Confirmed no performance regression in PHY throughput tests