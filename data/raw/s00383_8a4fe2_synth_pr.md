## Title: Fix incorrect scale_flag propagation in dft1944 DFT function

### Summary
The `dft1944` function in the OAI DFT library was incorrectly passing a hardcoded `scale_flag` value of `1` to downstream `dft648` calls, ignoring the `scale_flag` parameter passed by the caller. This caused unintended scaling behavior in 1944-point DFT computations regardless of the caller's intent. When `scale_flag=0` was specified to disable scaling, the function would still apply scaling due to the hardcoded literal values, leading to incorrect DFT results and potential signal processing errors in PHY layer operations.

This patch ensures proper propagation of the `scale_flag` parameter through the DFT computation chain by passing the caller's specified value to all three `dft648` invocations.

### Changes
- `openair1/PHY/TOOLS/oai_dfts.c`: Modified three calls to `dft648()` within `dft1944()` to use the `scale_flag` parameter instead of the hardcoded value `1`.

### Implementation Details
The `dft1944` function implements a 1944-point DFT by decomposing it into three 648-point DFTs using a butterfly structure with twiddle factors. The three calls to `dft648()` at lines 8340-8342 were previously hardcoded with `scale_flag=1`, which forced scaling unconditionally. The fix replaces these literals with the `scale_flag` function parameter, ensuring consistent scaling behavior throughout the DFT computation pipeline and respecting the caller's configuration.

### Testing
- Verified DFT output correctness with both `scale_flag=0` (no scaling) and `scale_flag=1` (with scaling) configurations
- Ran PHY layer unit tests to ensure no regressions in DFT-dependent modules
- Validated numerical accuracy against reference implementations for various input patterns