# Sentinel's Security Journal

## 2026-08-05 - [FastAPI Upload File OOM Denial of Service (CWE-400)]
**Vulnerability:** In `/api/config/ingest`, uploading extremely large files could lead to Out-Of-Memory (OOM) crashes because `await file.read()` loads the entire file into RAM by default.
**Learning:** Checking file size using `file.headers.get("content-length")` is fragile because `file.headers` holds individual form-data part headers, which are not populated by typical HTTP clients or testing utilities. Instead, inspecting the top-level HTTP request headers via `request.headers.get("content-length")` offers a robust early validation mechanism, coupled with a strict read-size limit on the actually read bytes.
**Prevention:** Always combine early top-level HTTP header `Content-Length` checks with actual stream chunk/byte read counters to enforce secure upload limits under defense-in-depth principles.

## 2026-08-10 - [Path Traversal Validator Restore (CWE-22)]
**Vulnerability:** A merge conflict regression completely removed the definition of the critical path traversal validator `validate_file_path` while leaving its imports intact, causing runtime import failures and bypassing file path safety boundaries in simulation and config loading.
**Learning:** Critical security functions can be lost or broken during complex automated merges. Maintaining comprehensive unit tests that specifically verify path validation is essential to detect when security mechanisms are silently dropped.
**Prevention:** Always verify import paths and compile-time status on all validator utilities. Ensure all merge commits are thoroughly verified against a green unit test run.
