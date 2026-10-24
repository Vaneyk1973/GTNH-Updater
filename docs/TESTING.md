# Verification record

Verification date: **2026-10-24**, GTNH **daily-2026-10-24+800**.
This records checks actually performed and separates final executable tests from
an earlier real-game startup check.

## Final release executables

| Environment | Source suite | Packaged executable suite |
| --- | --- | --- |
| Linux x64, glibc 2.36, Java 21 | 27 run, 1 Windows-only skip | 27 run, 1 Windows-only skip |
| Windows 7 SP1 x64 VM, Java 8 | 27 passed | 27 passed, legacy EXE |
| Windows 10 LTSC 2021 x64 VM, Java 21 | 27 passed with Python 3.8 and 3.13 | 27 passed each, legacy and modern EXEs |
| Windows 11 x64 VM, Java 21 | 27 passed | 27 passed, modern EXE |

All executable suites use the same binary bytes distributed in release 0.1.0.
Windows binaries were built on Windows 10. Win7 clean-install/status/help were also
checked without Python installed or on PATH; embedded Python was added later only
for source tests. Ready-made builds contain their runtime.

A GitHub-hosted Windows run exposed a missed running Java process when TEMP used
an 8.3 short path. The final core canonicalizes absolute command-line paths before
comparison. The Windows JVM regression fixture now deliberately uses a noncanonical
path, and passed on Windows 7, 10 and 11. Packaging explicitly preserves executable
TAR modes even when packaged on Windows.

GitHub Actions passed for application commit `809b488`:

* [Tests: four jobs](https://github.com/Vaneyk1973/GTNH-Updater/actions/runs/40129503469),
  Ubuntu 22.04 and Windows 2022, each with Python 3.8 and 3.13.
* [Build archives: three jobs](https://github.com/Vaneyk1973/GTNH-Updater/actions/runs/40129729378),
  Linux, modern Windows and legacy Windows builds, including executable tests.

The suite covers preview without mutation, full backups, preservation, overrides,
config edits, exact rollback, process-interruption recovery, second-target failure,
Java guards, locking, downgrade opt-in, unsafe archives, corrupted JARs, HTTPS source
restrictions, truncated/ranged downloads, Windows long paths and legacy Prism.
Fixtures use temporary directories, never a user's game. Packaging has a separate
test for excluding private files and including licenses/manifests.

## Real GTNH startup checks

These checks preceded the final Windows process-guard correction and rebuild.
They verify the installed GTNH/Java/Prism files; they are not a claim that every
real-game check was repeated using the final executable.

| Environment | Real client | Real server |
| --- | --- | --- |
| Linux x64, Java 21 | Main menu, 322 loaded mods, clean exit | Test world ready, save and shutdown |
| Windows 7 SP1 x64 VM, Java 8 | Main menu, 321 loaded mods, exit 0 | Test world ready, save, exit 0 |
| Windows 10 LTSC 2021 x64 VM, Java 21 | Main menu, 322 loaded mods, exit 0 | Test world ready, save, exit 0 |
| Windows 11 x64 VM, Java 21 | Main menu; created, entered, moved in and saved a singleplayer world; exit 0 | Test world ready, save, exit 0 |

## Release identity

SHA256 of the final executables:

```text
c85959a9ea51ce239d3f14f205a58cc2ee31f795ccdb8c68d1770a14bd99ac56  gtnh-updater
2f77e5693a130c6ceffc00b8fe896b186f1b147492d269a1a9afc3b87a864040  GTNH-Updater.exe
4682131cc28d41e752fbd5a2dad94ac1f06c84d892ba18f4911f6ce0ed70ab35  GTNH-Updater-Win7.exe
```

Application sources inside those builds:

```text
6b90e23d0f71f8fcfe1ef29eb570691c79509b8b3b97bc3992f8c5d0e0dc1788  gtnh_updater.py
e5c4912a0edb4a072be1a8dc0d64079fcf49463efc34b3be381be955f1aa9a20  lib/pack.py
796f1389bfea13c0ed78f663b765baaff54a508e5483786bd6ece73c5e3e3cbe  lib/cacert.pem
```

The archive manifest repeats source/binary hashes. Release SHA256SUMS covers all
published payload files. Build timestamps and packaging metadata can differ between
local and GitHub builds; byte-for-byte reproducibility is not claimed.

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
  PyInstaller 5.13.2. Linux uses Debian 12 / glibc 2.36. A future CI build alone does
  not prove Win7 compatibility.

Full private logs stay outside the public repository. Never upload accounts.json,
VM credentials, game worlds or Windows images.
