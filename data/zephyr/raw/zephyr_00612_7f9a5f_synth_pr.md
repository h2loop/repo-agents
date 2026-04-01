## Title: Fix improper state transition in LP common terminate invalid PDU handling

### Summary
This PR addresses an issue in the Bluetooth controller's link layer control protocol (LLCP) state machine where `lp_comm_terminate_invalid_pdu` does not properly transition the connection to a terminated state. Currently, after setting the termination reason and calling `llcp_lr_complete`, the procedure context remains in an active state, which can lead to unexpected behavior or improper handling of subsequent events.

The fix ensures that `llcp_lr_terminate` is explicitly called to properly terminate the connection and transition the local procedure state machine to a disconnected state. This prevents potential race conditions or incorrect state handling in the LLCP layer when invalid PDUs are received during connection procedures.

### Changes
- `subsys/bluetooth/controller/ll_sw/ull_llcp_common.c`: Added explicit call to `llcp_lr_terminate` in `lp_comm_terminate_invalid_pdu` to ensure proper connection termination and state transition.

### Testing
- Verified correct state transition through manual inspection of state machine logic.
- Confirmed no regression in existing Bluetooth connection establishment and teardown procedures.