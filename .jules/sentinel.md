# Sentinel's Security Journal

## 2026-08-05 - [FastAPI Upload File OOM Denial of Service (CWE-400)]
**Vulnerability:** In `/api/config/ingest`, uploading extremely large files could lead to Out-Of-Memory (OOM) crashes because `await file.read()` loads the entire file into RAM by default.
**Learning:** Checking file size using `file.headers.get("content-length")` is fragile because `file.headers` holds individual form-data part headers, which are not populated by typical HTTP clients or testing utilities. Instead, inspecting the top-level HTTP request headers via `request.headers.get("content-length")` offers a robust early validation mechanism, coupled with a strict read-size limit on the actually read bytes.
**Prevention:** Always combine early top-level HTTP header `Content-Length` checks with actual stream chunk/byte read counters to enforce secure upload limits under defense-in-depth principles.

## 2026-08-16 - [Path validation must enforce containment explicitly]
**Vulnerability:** The path validator normalized and resolved user-supplied paths but did not provide a containment check for callers that require files to stay inside a trusted directory.
**Learning:** `Path.resolve()` canonicalizes traversal such as `../secret.txt`; canonicalization alone does not make the path safe. Security-sensitive file selection needs an explicit relationship check against an allowed root.
**Prevention:** When validating untrusted filesystem paths, resolve both the candidate and trusted root, then require the candidate to remain relative to that root before use.

## 2026-08-18 - [Bearer token comparison must be constant-time]
**Vulnerability:** `verify_token` compared a supplied bearer token with the configured secret using normal string equality, exposing a potential timing side channel during authentication.
**Learning:** Token validation should use the standard library's constant-time comparison primitive so the comparison does not reveal matching-prefix information through ordinary string-comparison timing.
**Prevention:** Use `secrets.compare_digest` for bearer-token comparisons and keep regression coverage for valid, invalid, and missing credentials.
