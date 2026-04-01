## Title: Add state validation in gNB tracer click handler

### Summary
The gNB tracer's click callback function processes button events without validating that the `gnb_data` structure and its critical fields are properly initialized. This can lead to NULL pointer dereferences and crashes if the callback is invoked before the database is ready or with corrupted parameters. The issue particularly affects the GUI interaction path where users may click buttons during initialization.

The fix adds comprehensive state validation at the function entry point. It checks that the private data pointer, notification data, and the essential `gnb_data` fields (`e` and `database`) are non-NULL before performing any operations. If validation fails, the function logs an error to stderr and returns early, preventing undefined behavior. Variable declarations were also reorganized to improve code clarity by grouping them before the validation logic.

### Changes
- `common/utils/T/tracer/gnb.c`: Added NULL checks for `private`, `notification_data`, `ed->e`, and `ed->database` in the `click()` function. Reorganized variable declarations to precede validation logic.

### Testing
- Verified the tracer GUI initializes and handles button clicks correctly under normal conditions
- Confirmed early return and error logging when validation fails
- Tested with various initialization states to ensure robustness