## Title: Replace deprecated localtime() with thread-safe localtime_r()

### Summary
Replace two occurrences of the deprecated `localtime()` function with the thread-safe `localtime_r()` alternative in the `multi-rru-clean.c` utility. The `localtime()` function returns a pointer to a statically allocated struct which is not thread-safe and can be overwritten by subsequent calls. This poses correctness risks for any future multi-threaded usage of the tracer utility. The `localtime_r()` variant stores results in a caller-provided buffer, eliminating this concurrency hazard while maintaining identical functional behavior for time formatting in error messages.

### Changes
- `common/utils/T/tracer/hacks/multi-rru-clean.c`:
  - In `process_cache()` (line 76): Changed `struct tm *t;` to stack-allocated `struct tm t;`, replaced `t = localtime(&c[i].t.tv_sec)` with `localtime_r(&c[i].t.tv_sec, &t)`, and updated member accesses from `t->tm_hour` to `t.tm_hour` (and similar for min/sec)
  - In `main()` (line 199-200): Applied same transformation for the invalid tag error path, changing `struct tm *tt;` and `tt = localtime(&t.tv_sec)` to use `localtime_r()` with stack allocation
  - No functional behavior changes; only thread-safety improvement

### Testing
- Verified code compiles without warnings after the replacement
- Confirmed error message time formatting produces identical output format
- No performance regression expected; `localtime_r()` has same computational complexity as `localtime()`