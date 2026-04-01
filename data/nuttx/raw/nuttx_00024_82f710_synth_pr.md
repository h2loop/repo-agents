## Title: Handle work_queue return values in STM32 SDMMC interrupt handlers

### Summary
This PR addresses potential error conditions in the STM32H7 SDMMC driver where `work_queue` return values were not being checked. Although `sdio_mediachange` itself returns `void`, it calls `stm32_callback`, which may queue work items via `work_queue`. These queued operations can fail silently if `work_queue` returns an error, potentially leading to missed callbacks or unexpected behavior during card detection or data transfer interrupts.

The changes explicitly check the return value of `work_queue` calls in three locations:
1. `stm32_sdmmc_fifo_monitor` - when queuing FIFO monitoring work
2. `stm32_sdmmc_interrupt` - when queuing FIFO monitoring after RX FIFO handling
3. `stm32_callback` - when queuing user callbacks

In each case, an error is logged using `mcerr` if `work_queue` fails, improving debuggability and preventing silent failures.

### Why
While the likelihood of `work_queue` failing is low under normal conditions, checking its return value is a defensive programming practice that helps catch resource exhaustion or system overload scenarios. This makes the driver more robust and provides better diagnostic information when issues occur.

### Affected Files
- `arch/arm/src/stm32h7/stm32_sdmmc.c` - Added error checking for `work_queue` calls in interrupt handlers and callback functions