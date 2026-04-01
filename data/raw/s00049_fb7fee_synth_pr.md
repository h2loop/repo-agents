## Title: Fix buffer overflow in NSSAI parsing loop

### Summary
The `parse_allowed_nssai` function in the NAS UE message parser extracts NSSAI (Network Slice Selection Assistance Information) entries from a network message into a fixed-size array of 8 elements. The while loop condition only verified that the buffer pointer remained within bounds but failed to check the array index, allowing potential writes beyond the allocated `nssaiList[8]` array if the message contained more than 8 NSSAI entries.

This fix adds a bounds check to the loop condition to prevent buffer overflow and memory corruption when processing malformed or unusually large NSSAI lists from the network.

### Changes
- `openair3/NAS/NR_UE/nr_nas_msg.c`: In `parse_allowed_nssai()`, modify the while loop condition from `while (buf < end)` to `while (buf < end && nssai_cnt < 8)` to ensure the array index never exceeds the allocated size.

### Testing
- Verified successful compilation of the `nr-uesoftmodem` target.
- Code inspection confirms the fix prevents out-of-bounds writes while correctly parsing valid messages with up to 8 NSSAI entries.