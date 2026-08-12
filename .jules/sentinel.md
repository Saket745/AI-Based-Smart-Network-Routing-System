# Sentinel's Security Journal

## 2026-08-05 - [FastAPI Upload File OOM Denial of Service (CWE-400)]
**Vulnerability:** In `/api/config/ingest`, uploading extremely large files could lead to Out-Of-Memory (OOM) crashes because `await file.read()` loads the entire file into RAM by default.
**Learning:** Checking file size using `file.headers.get("content-length")` is fragile because `file.headers` holds individual form-data part headers, which are not populated by typical HTTP clients or testing utilities. Instead, inspecting the top-level HTTP request headers via `request.headers.get("content-length")` offers a robust early validation mechanism, coupled with a strict read-size limit on the actually read bytes.
**Prevention:** Always combine early top-level HTTP header `Content-Length` checks with actual stream chunk/byte read counters to enforce secure upload limits under defense-in-depth principles.

## 2026-08-11 - [Accidental Deletion of Critical Security Validation Function during Code Health Cleanup]
**Vulnerability:** A robust file path validation function (`validate_file_path`) designed to prevent directory traversal and null-byte injection was deleted during a generic "remove unused functions" refactor. This broke the secure file-loading mechanisms in several ingestion and simulation modules, leaving files unprotected or uncompilable.
**Learning:** Static-analysis cleanups ("dead-code removal") can sometimes erroneously identify security guardrails or cross-module utility functions as dead code, especially if imports are handled dynamically or lost during git merges. Removing validation functions leaves call sites broken and vulnerable if they are reintroduced or bypassed.
**Prevention:** Before performing generic dead-code elimination or refactoring, verify all test suites and reference targets across the codebase to ensure security-critical validation modules remain intact and fully functional.
