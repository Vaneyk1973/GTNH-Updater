# Changelog

## 0.1.0 — 2026-10-24

First public cross-platform release, replacing the legacy PowerShell implementation.

* Update GTNH clients and servers to the same daily/stable or exact release.
* Preview changes and validate official archives before replacing files.
* Detect running Windows Java instances through canonical paths, including short
  8.3 names, junctions and dot segments.
* Full backups including hidden files and worlds; managed-file rollback includes
  Prism metadata/libraries and supports recovery after interruption.
* Portable clean-install with official GTNH, Prism Launcher and Temurin downloads.
* Bundled Linux x64 and Windows 10/11 x64 executables, plus a legacy Windows 7 x64
  build. No separate Python installation is needed for packaged builds.
* Source tests, manual VM verification records, build workflows and release tooling.

Windows 7 requires OS updates/runtime components and uses unsupported legacy Prism.
Binaries are unsigned. Tests used offline profiles; Microsoft authentication was not
verified. See docs/TESTING.md for the exact test scope and limits.

Original MIT copyright and project provenance are retained in LICENSE and NOTICE.
