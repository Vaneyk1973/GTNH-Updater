# Verification record

Last manual runtime verification: **2026-10-24**, GTNH **daily-2026-10-24+800**.
This describes tests actually performed. GitHub Actions is configured separately
and has not run until the repository is published.

| Environment | Source / packaged CLI | Real client | Real server |
| --- | --- | --- | --- |
| Linux x64, glibc 2.36, Java 21 | 25 passed, 1 Windows-only test skipped, each | Main menu, 322 loaded mods, clean exit | Test world ready, save and shutdown |
| Windows 7 SP1 x64 VM, Java 8 | 26 passed each | Main menu, 321 loaded mods, exit 0 | Test world ready, save, exit 0 |
| Windows 10 LTSC 2021 x64 VM, Java 21 | 26 passed each | Main menu, 322 loaded mods, exit 0 | Test world ready, save, exit 0 |
| Windows 11 x64 VM, Java 21 | 26 passed each | Main menu; created, entered, moved in and saved a singleplayer world; exit 0 | Test world ready, save, exit 0 |

Win7 executable was also tested on Windows 10. Win7 clean install/status/help were
checked without Python installed or on PATH. Embedded Python was added later only
for the source test suite. All ready-made builds contain their runtime.

Publication preparation added one packaging test: on Linux, both source and the
unchanged executable passed **27 tests, with 1 Windows-only skip** (26 passed).
The new packaging test has not been run on the Windows guests. Workflow syntax was
checked locally with actionlint 1.7.12; a GitHub-hosted run is still pending.

The suite covers preview without mutation, full backups, preservation, overrides,
config edits, exact rollback, process-interruption recovery, second-target failure,
Java guards, locking, downgrade opt-in, unsafe archives, corrupted JARs, HTTPS source
restrictions, truncated/ranged downloads, Windows long paths and legacy Prism.
Fixtures use temporary directories, never a user's game. Packaging has a separate
test for excluding private files and including licenses/manifests.

## Limits

* Clients used an existing offline profile and cached official libraries, launched
  directly with Java arguments derived from Prism metadata. Microsoft authentication
  and authenticated Prism-to-game startup were **not** verified.
* Windows servers used their Java entry points; the generated Windows server wrapper
  was not exercised end to end. Linux used Start-Server.sh; clean JVM shutdown was
  observed, but its numeric exit code was not recorded.
* QEMU/KVM guests used Mesa llvmpipe software rendering. Mesa is test infrastructure,
  not bundled/installed by the updater. GPU passthrough was not tested.
* These are startup/save checks, not long gameplay or a guarantee for every world,
  custom mod, antivirus setup or future upstream release. Mod warnings remain.
* Defender blocked an earlier harness launched from a network share. Final suites
  passed from local files with protection enabled. Binaries are unsigned; reputation
  warnings or antivirus false positives remain possible.
* Modern binaries: CPython 3.13.17 / PyInstaller 6.16.0; legacy: CPython 3.8.10 /
  PyInstaller 5.13.2. Final Windows binaries were built on Windows 10 and tested on
  the target guests. A future CI build alone does not prove Win7 compatibility.

Full private logs stay outside the public repository. Never upload accounts.json,
VM credentials, game worlds or Windows images. The packaging test added during
publication preparation has not been rerun on the Windows 7 guest.
