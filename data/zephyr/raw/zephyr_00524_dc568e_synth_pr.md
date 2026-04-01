## Title: Defer shell print operations in media controller callbacks to avoid interrupt context issues

### Summary
This PR fixes an issue where blocking shell print functions (`bt_shell_print`, `bt_shell_error`) were being called directly from Bluetooth audio callback functions that execute in interrupt context. This violates the Zephyr shell API contract, which prohibits use of these functions from ISRs, potentially leading to undefined behavior or system instability.

The fix implements a deferred execution pattern using Zephyr work queues. Callbacks now populate work structures with their parameters and submit them to the system work queue, where the shell operations are safely executed in thread context.

### Changes
- `subsys/bluetooth/audio/shell/media_controller.c`: 
  - Added work structures and handlers for `playing_order_recv_cb`, `playing_order_write_cb`, and `playing_orders_supported_recv_cb`
  - Modified callbacks to schedule work instead of calling shell functions directly
  - Added proper work initialization and submission logic

### Testing
Verified that shell output is correctly deferred and no longer triggers interrupt context assertions. All existing media controller shell commands continue to function as expected, with output now properly scheduled through the work queue mechanism.