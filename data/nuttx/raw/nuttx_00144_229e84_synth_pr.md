## Title: Fix Missing Null Terminator in rpmsgfs_rename_handler

### Summary
This PR fixes a potential security and stability issue in the `rpmsgfs_rename_handler` where the `newpath` parameter might not be properly null-terminated. In the RPMsg filesystem server, rename operations pack two paths (old and new) consecutively in the message buffer. While the client ensures both paths are null-terminated, the server-side handler did not validate that the second path (`newpath`) was properly terminated within the message bounds before passing it to the `rename()` system call.

Without proper validation, a malformed message could cause the `rename()` function to read beyond the intended path string, potentially leading to unpredictable behavior or information disclosure. The fix adds bounds and null-termination checks for `newpath` using `memchr()` to ensure it is safe to use.

### Changes
- `fs/rpmsgfs/rpmsgfs_server.c`: Added validation in `rpmsgfs_rename_handler` to ensure `newpath` is within message bounds and null-terminated before use.

### Testing
- Validated that well-formed rename requests continue to work as expected.
- Confirmed that malformed messages with missing null terminators are properly rejected with `-EINVAL`.