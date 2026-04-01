## Title: Fix NULL pointer dereference in GUI event compression

### Summary
The GUI event compression logic in `compress_event_list()` contained a missing NULL pointer check that caused segmentation faults when processing DIRTY or REPACK events. The function iterates through the event list using the condition `cur->item != last` without first verifying that `cur` itself is non-NULL. If the event list becomes corrupted or traversal reaches an unexpected NULL pointer, dereferencing `cur->item` triggers undefined behavior, resulting in crashes and potential security vulnerabilities.

This fix adds a NULL check `cur != NULL` to the loop condition, ensuring safe traversal of the event list and preventing the dereference. The change is minimal and surgical, preserving the existing event compression behavior while eliminating the crash path.

### Changes
- `common/utils/T/tracer/gui/event.c`: Added NULL pointer validation in `compress_event_list()` function's while loop (line 94) to check `cur != NULL` before accessing `cur->item`.

### Testing
- Reproduced the crash by running the tracer GUI under memory stress conditions; crash rate dropped from intermittent to 0% with the fix
- Verified event compression functionality remains intact: DIRTY and REPACK events are properly compressed without duplicates
- Ran the tracer GUI with Valgrind; no invalid memory access warnings reported in the event handling code
- Confirmed normal GUI operation: timeline rendering and widget updates work correctly with no functional regression