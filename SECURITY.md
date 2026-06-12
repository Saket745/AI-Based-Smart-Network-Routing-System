# Security Policy

We take security vulnerabilities seriously. This document outlines our vulnerability reporting policy and secure practices.

---

## 🛡️ Supported Versions

We actively maintain and support the current major branch:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | Yes (Development)  |

---

## 🔒 Reporting a Vulnerability

**Please do not report security vulnerabilities via public GitHub issues.** Instead, follow this process:

1. Send an email to `security@example.com` describing the vulnerability.
2. Include a detailed description, step-by-step reproduction steps, or a proof-of-concept (PoC) script.
3. We will acknowledge receipt of your report within 48 hours and work to resolve the issue as quickly as possible.

---

## 🔑 Secret and Credential Protection

To prevent accidental leaks of api-keys, tokens, or credentials:

* **Pre-commit Scan:** We run `detect-private-key` in our local git pre-commit hooks to block private keys from being staged.
* **Secret Leak Mitigation:** If you accidentally commit a secret (such as private credentials) to a public or shared branch:
  1. Revoke the credential immediately.
  2. Rewrite git history if the branch hasn't been merged to `main` (using `git filter-repo` or `git rebase`).
  3. Contact the administrator to prune the ref from the remote repository.
* **Local Configurations:** Keep private variables in a `.env` file or locally within `configs/local_settings.yaml`. These file paths are ignored in `.gitignore`.
