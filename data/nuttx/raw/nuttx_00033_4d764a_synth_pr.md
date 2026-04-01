## Title: Add watchdog servicing in RX65N USB host driver to prevent timeout during long operations

### Summary
This PR addresses a potential watchdog timeout issue in the RX65N USB host driver during long-running operations. The RX65N's hardware watchdog timer may reset the system if not periodically serviced during intensive USB transfers or pipe configuration loops. This can cause unexpected system resets when handling large data transfers or device enumeration.

The fix implements periodic watchdog servicing in critical sections of the USB host driver where delays may occur, specifically:
- In `usb_cstd_set_nak()` during pipe NAK processing
- In `usb_cstd_chg_curpipe()` during pipe switching operations

A new static function `rx65n_wdt_service()` is added to properly refresh the watchdog timer using the required WDT register sequence.

### Changes
- `arch/renesas/src/rx65n/rx65n_usbhost.c`: 
  - Added `rx65n_wdt_service()` function to handle watchdog refresh
  - Inserted watchdog servicing calls in long-running loops and polling operations
  - Serviced watchdog every 256 iterations in `usb_cstd_set_nak()` and in pipe change polling loops

### Testing
Tested with USB mass storage devices requiring large data transfers. System no longer resets during prolonged USB operations. Verified normal USB enumeration and data transfer functionality remains intact.