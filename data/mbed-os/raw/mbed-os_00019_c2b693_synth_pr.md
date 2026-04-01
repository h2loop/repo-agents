## Title: Fix signed/unsigned integer comparison warnings in DAC peripheral driver

### Summary
This PR resolves compiler warnings related to signed/unsigned integer comparisons in the GD32F30X DAC peripheral driver. The issue arises from comparing `DAC0` and `DAC1` macro definitions (defined as `0U` and `1U`, type `unsigned int`) against the `uint32_t dac_periph` parameter in several DAC functions.

While functionally correct, this mismatch can trigger warnings with strict compiler settings. The fix explicitly casts the macro values to `uint32_t` to ensure type consistency and eliminate warnings without changing behavior.

### Changes
- **targets/TARGET_GigaDevice/TARGET_GD32F30X/GD32F30x_standard_peripheral/Source/gd32f30x_dac.c**: Updated all DAC peripheral functions (`dac_enable`, `dac_disable`, `dac_dma_enable`, `dac_dma_disable`, `dac_output_buffer_enable`, `dac_output_buffer_disable`, `dac_trigger_enable`, `dac_trigger_disable`, `dac_software_trigger_enable`, `dac_software_trigger_disable`) to cast `DAC0` to `uint32_t` in conditional comparisons.

### Impact
- Resolves potential compiler warnings for strict signed/unsigned comparison checks.
- No functional changes; maintains identical runtime behavior.
- Improves code portability and cleanliness for different compiler environments.

### Testing
Verified by code inspection that all affected functions now use consistent types in comparisons. No behavioral changes expected.