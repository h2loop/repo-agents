## Title: Fix Invalid State Transitions in Bluetooth Mesh BLOB Client

### Summary
This PR addresses an issue in the Bluetooth mesh BLOB client where improper protocol state machine transitions could occur downstream of the `chunk_idx_decode` function. The problem manifests when `handle_block_report` or `handle_block_status` are invoked while the client is in an invalid state, potentially leading to inconsistent behavior or protocol errors during BLOB transfers.

The root cause was missing state validation in these handler functions. We've added explicit checks to ensure they're only called when the client is in a valid state (`BT_MESH_BLOB_CLI_STATE_BLOCK_START`, `BT_MESH_BLOB_CLI_STATE_BLOCK_SEND`, or `BT_MESH_BLOB_CLI_STATE_BLOCK_CHECK`). If an invalid state is detected, the handlers now log a warning and return `-EBUSY`, preventing unintended state transitions.

### Changes
- `subsys/bluetooth/mesh/blob_cli.c`: 
  - Added state validation in `handle_block_report()` at line 1294
  - Added state validation in `handle_block_status()` at line 1350
  - Both checks ensure the client is in a valid block processing state before proceeding

### Impact
This change improves robustness of the BLOB client by preventing invalid state transitions that could cause transfer failures or inconsistent states. It aligns the implementation with expected Bluetooth mesh BLOB transfer protocol behavior where block reports and status messages should only be processed during active block transfer phases.