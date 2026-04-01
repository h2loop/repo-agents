## Title: Fix ENET peripheral deinitialization order issue

### Summary
This PR addresses an initialization order issue in the ENET driver's deinitialization sequence. The problem occurred because the Ethernet module was not being properly reset during `ENET_Deinit`, which could leave the peripheral in an inconsistent state when reinitialized. This fix ensures a clean shutdown by resetting the ENET module before disabling its clock, matching the initialization sequence used in `ENET_Init`.

The issue was identified by comparing the `ENET_Init` and `ENET_Deinit` functions, where it was clear that the deinitialization path was missing the module reset step that occurs during initialization. This could lead to unexpected behavior when the Ethernet peripheral was reinitialized after being deinitialized.

### Changes
- `targets/TARGET_Freescale/TARGET_MCUXpresso_MCUS/TARGET_MCU_K64F/drivers/fsl_enet.c`: Added `ENET_Reset(base)` call in the `ENET_Deinit` function to ensure the Ethernet module is properly reset during deinitialization, bringing it in line with the initialization sequence.

### Testing
- Verified that Ethernet functionality works correctly after multiple init/deinit cycles
- Confirmed that the reset operation doesn't introduce any regressions in normal Ethernet operation
- Tested with Ethernet example applications to ensure proper behavior during reinitialization scenarios