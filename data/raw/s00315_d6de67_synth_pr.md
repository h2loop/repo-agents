## Title: Fix null pointer dereference in tracer GUI textarea widget

### Summary
The tracer GUI's textarea widget contains null pointer dereference vulnerabilities in the `paint()` and `hints()` functions. When the text field (`t->t`) is NULL, the code crashes while attempting to log or render the widget contents. This issue manifests during GUI initialization or when displaying empty text areas, causing segmentation faults that terminate the tracing session.

The bug stems from missing defensive checks before dereferencing the text pointer. This fix adds null checks to both functions, allowing the GUI to gracefully handle uninitialized or empty text areas by rendering only the background rectangle and avoiding unsafe pointer access.

### Changes
- `common/utils/T/tracer/gui/textarea.c`: 
  - In `paint()`: Added NULL check for `t->t` before logging and string rendering. When NULL, the function now draws only the background rectangle and returns early.
  - In `hints()`: Added NULL check for `t->t` before logging to prevent dereference errors.

### Implementation Details
The fix maintains backward compatibility by preserving existing behavior for valid text pointers while adding graceful degradation for NULL pointers. The logging statements are updated to explicitly indicate when NULL text is encountered, aiding future debugging. No changes to the widget structure or API were required, ensuring minimal impact on the tracer subsystem.

### Testing
- Verified the tracer GUI starts without segmentation faults in scenarios with empty text areas.
- Confirmed normal rendering behavior persists for text areas with valid content.
- Tested with the `t_tracer` utility to ensure no regression in live tracing visualization.