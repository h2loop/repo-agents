## Title: Fix NULL pointer dereference in SPI STM32 DMA callback

### Summary
This PR addresses a potential NULL pointer dereference in the `dma_callback` function within the SPI STM32 backend for EC host commands. The issue occurs when the `arg` parameter passed to the callback is NULL, which can lead to a crash if dereferenced without validation. Adding a NULL check prevents this undefined behavior and improves system stability.

The fix ensures that the `hc_spi` context is validated before use, logging an error and returning early if the context is invalid. This is a defensive programming practice that mitigates potential runtime failures in embedded environments where DMA callbacks may be invoked under unexpected conditions.

### Changes
- `subsys/mgmt/ec_host_cmd/backends/ec_host_cmd_backend_spi_stm32.c`: Added a NULL check for the `hc_spi` context at the beginning of the `dma_callback` function to prevent dereferencing a NULL pointer.

### Impact
Improves robustness of the SPI backend by preventing crashes due to invalid DMA callback arguments. No functional changes; existing behavior remains unchanged when the context is valid.