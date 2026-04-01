## Title: Fix Copy-Paste Error in PDM-PCM Interrupt Documentation

### Summary
This PR corrects a documentation copy-paste error in the `Cy_PDM_PCM_ClearInterrupt` function within the PDM-PCM driver header file. The function's description incorrectly stated that it "sets an INTR register's bits" when it actually clears interrupt statuses by writing to the INTR register. This inconsistency likely arose from duplication of documentation from a similar function without proper adaptation.

The fix ensures that the documentation accurately reflects the function's behavior, improving code clarity and maintainability for developers working with the PDM-PCM driver on Cypress PSoC 6 platforms.

### Why
- **Accuracy**: Ensures documentation matches actual implementation
- **Maintainability**: Reduces confusion for developers using or modifying the driver
- **Code Quality**: Fixes a clear copy-paste artifact that could mislead future development

### Changes
- `targets/TARGET_Cypress/TARGET_PSOC6/mtb-pdl-cat1/drivers/include/cy_pdm_pcm.h`: Updated the function documentation for `Cy_PDM_PCM_ClearInterrupt` to correctly describe its behavior of clearing interrupt statuses by writing to the INTR register instead of incorrectly stating it sets bits.

### Testing
No functional changes were made; this is a documentation-only fix. The change was verified by reviewing the surrounding interrupt-related functions to ensure consistency and correctness of the updated description.