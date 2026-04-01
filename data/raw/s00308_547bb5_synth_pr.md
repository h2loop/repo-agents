## Title: Fix incorrect slot boundary calculation causing protocol state machine violation

### Summary
The `get_slot_from_timestamp()` function in the PHY initialization layer contains an off-by-one error in its slot boundary detection logic that violates 3GPP timing specifications. The while loop condition uses strict inequality (`>`) instead of inclusive (`>=`) when comparing timestamps against slot boundaries. This causes timestamps that fall exactly on slot boundaries to be assigned to the subsequent slot index, leading to incorrect protocol state machine transitions downstream. The miscalculation particularly impacts timing-critical procedures that depend on precise slot identification for state transitions, resulting in potential non-compliance with 3GPP TS 38.211 slot timing requirements.

### Changes
- `openair1/PHY/INIT/nr_parms.c`: Change the loop condition in `get_slot_from_timestamp()` from `while (timestamp_rx > samples_till_the_slot)` to `while (timestamp_rx >= samples_till_the_slot)` on line 268. This ensures timestamps at exact slot boundaries are correctly assigned to their intended slot rather than the next slot.

### Implementation Details
This is a minimal, targeted fix that corrects the boundary condition logic without affecting the overall algorithm structure. The change ensures proper handling of the edge case where `timestamp_rx` equals `samples_till_the_slot`, which represents the exact start of the next slot boundary.

### Testing
- Verified slot index calculation returns correct values for timestamps at slot boundaries
- Ran unit tests covering all slot positions within a frame (0-19 for 15kHz SCS)
- Validated protocol state machine transitions now occur at correct slot boundaries per 3GPP spec
- Executed `nr-uesoftmodem` with rfsimulator to confirm no regression in normal operation