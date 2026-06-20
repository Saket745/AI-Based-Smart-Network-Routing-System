# Commit Governance Audit

## 1. Commit Grammar

The repository enforces a variation of the **Conventional Commits** specification.

### Header Format
`type(scope)!: description`

- **type**: Required. Must be one of: `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style`, `test`.
- **scope**: Optional. Alphanumeric with `_`, `-`, `/`.
- **!**: Optional. Indicates breaking change.
- **description**: Required. Minimum 5 characters.

### Ignored Patterns
- `Merge branch ...`
- `Merge pull request ...`
- `Merge remote-tracking branch ...`
- `Merge <sha> into <sha>`

## 2. Compatibility Matrix

| Commit Type | Status | Notes |
|-------------|--------|-------|
| Conventional Commits | ✅ Supported | Full support for standard types. |
| Google Jules Commits | ✅ Supported | Follows Conventional Commits. |
| GitHub Merge Commits | ✅ Supported | Explicitly ignored by validator. |
| Squash Commits | ⚠️ Partial | Depends on the squash message. If it defaults to PR title, PR title must be conventional. |
| Revert Commits | ❌ Failing | Auto-generated `Revert "..."` fails validation. |
| Dependabot Commits | ✅ Supported | Usually follows `build(deps): ...` or `chore(deps): ...`. |
| Security Fixes | ✅ Supported | Can use `fix(security): ...`. |

## 3. Unsupported Commit Patterns

1.  **Standard Git Revert**: Auto-generated `Revert "feat: ..."` messages are rejected because they don't match the `type: description` pattern or the `revert: ...` pattern with specific case sensitivity.
2.  **Initial Commits**: `initial commit` or `Initial commit` will fail.
3.  **WIP Commits**: `wip`, `saving work`, etc., will fail (intentional, but can be a bottleneck for some workflows).
4.  **Capitalized Types**: `Feat: ...` fails because the regex specifies `[a-z]+`.

## 4. Recommended Validator Modifications

1.  **Handle Revert Commits**: Update the ignore logic to include `Revert "..."` patterns.
2.  **Case Insensitivity for Types**: Allow types to be case-insensitive, although lowercase is preferred.
3.  **Improved Merge Detection**: Ensure all variants of GitHub/GitLab/Bitbucket merge commits are handled.
4.  **Flexible Description**: While 5 chars is a good minimum, sometimes `fix: typo` is rejected if 'typo' is too short (4 chars).
