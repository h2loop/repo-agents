## Title: Replace magic numbers with symbolic constants in BLER calculation

### Summary
The `get_bler_val()` function in the NR UE PHY interface used hardcoded column indices (4 and 5) to access dropped packets and total packets from the BLER lookup table. These magic numbers reduced code readability and maintainability, making it unclear what data each column represented and increasing the risk of errors if the table structure changed.

This patch introduces symbolic constants for BLER table column indices and replaces all magic number occurrences with these named constants. The change improves code clarity by explicitly documenting the purpose of each column access while preserving identical functional behavior.

### Changes
- `openair2/NR_UE_PHY_INTERFACE/NR_Packet_Drop.h`: Added `BLER_COL_SINR`, `BLER_COL_DROPPED_PACKETS`, and `BLER_COL_TOTAL_PACKETS` preprocessor defines with descriptive names and comments documenting each column's purpose.
- `openair2/NR_UE_PHY_INTERFACE/NR_Packet_Drop.c`: Replaced all 8 instances of hardcoded indices `[0]`, `[4]`, and `[5]` with the new symbolic constants throughout the `get_bler_val()` function, including boundary condition checks and linear interpolation logic.

### Testing
- Verified successful compilation with the changes applied
- Confirmed BLER calculation logic remains functionally identical through code inspection
- All array access patterns maintain the same semantics with improved readability

### Implementation Details
The constants are defined at the header level to allow potential reuse across other BLER-related functions. Column 4 represents dropped packet counts, column 5 represents total packet counts, and column 0 represents SINR values (scaled by 10x) used for table lookup and interpolation.