## Title: Fix integer type mismatch for remote_port in pnf_sim phy_info

### Summary
The `phy_info` class in the pnf_sim component incorrectly declared `remote_port` as `int`, which is inconsistent with standard network port representation and could lead to integer truncation issues. Network ports are conventionally unsigned 16-bit values (0-65535) per protocol specifications. This change corrects the type mismatch to improve type safety, prevent potential sign-related bugs, and align with the underlying nfapi protocol expectations.

### Changes
- `nfapi/open-nFAPI/pnf_sim/src/main.cpp`: Changed `remote_port` member variable type from `int` to `uint16_t` in the `phy_info` class (line 125)

### Implementation Details
The `remote_port` field is updated to use the semantically correct `uint16_t` type. This is a minimal, targeted fix that ensures proper type alignment without affecting the existing logic. The change prevents potential issues from implicit integer conversions and makes the port value range explicit, matching how port numbers are represented throughout the network stack and nfapi interfaces.

### Testing
- Verified compilation succeeds with the type change
- Confirmed no other code modifications are needed as the field is already used consistently with uint16_t values in the config_request flow and related network operations
- Validated that port values are correctly handled during PNF simulation initialization and configuration requests