## Title: Fix stack buffer overflow in tracer GUI label widget

### Summary
The `label_set_text()` function in the tracer GUI library passes user-provided text directly to `x_text_get_dimensions()`, which uses a fixed-size stack buffer that overflows with inputs exceeding ~1KB. This causes crashes when UE labels contain very long debug strings.

This fix introduces a 1023-character limit on text before X11 processing. Longer strings are truncated using `strndup()`, and NULL inputs are converted to empty strings. The function now passes the stored `this->t` (which may be truncated) to `x_text_get_dimensions()` instead of the original `text` parameter, ensuring consistent rendering dimensions.

### Changes
- `common/utils/T/tracer/gui/label.c`: 
  - Added length check: if text exceeds 1023 characters, truncate with `strndup(text, 1023)`
  - Added NULL safety: convert NULL input to empty string via `strdup(text ? text : "")`
  - Changed `x_text_get_dimensions()` to use `this->t` instead of `text` for dimension calculation
  - No functional change for strings ≤1023 characters

### Testing
- Verified tracer GUI starts and displays normal-length labels correctly
- Confirmed strings >1023 characters are truncated without crashing
- Checked call sites in `ue.c` and `gnb.c` remain compatible