# Security

Report vulnerabilities through this repository's **Security → Report a vulnerability**
feature. Do not disclose exploitable details, credentials, account data or private
logs in a public issue. Ordinary bugs belong in Issues; redact personal data first.

Include the updater version, OS, affected command, a minimal reproduction using
disposable files, expected impact and relevant redacted output.

Only the latest published updater version is maintained. Windows 7, its legacy
Python runtime and Prism 7.2 are no longer supported upstream; compatibility tests
do not provide security updates for those components.

Release executables are unsigned. Use this repository's Releases page, verify
SHA256SUMS and keep LICENSE/NOTICE and the third-party license files with binaries.
Checksums detect a different download; they do not provide an independent signature.
