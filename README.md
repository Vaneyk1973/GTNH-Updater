# GTNH Updater

[![Tests](https://github.com/Vaneyk1973/GTNH-Updater/actions/workflows/tests.yml/badge.svg)](https://github.com/Vaneyk1973/GTNH-Updater/actions/workflows/tests.yml)
[Releases](https://github.com/Vaneyk1973/GTNH-Updater/releases) · [Changelog](CHANGELOG.md) · [Build instructions](docs/RELEASING.md)

[Русская инструкция](README.ru.md)

Update GT New Horizons clients and servers together, or install portable Prism
Launcher and GTNH from official downloads. This is an unofficial community tool.

Ready-made Linux and Windows builds include their runtime: **no Python installation,
PowerShell 7, WSL or Git Bash is required**. The interface is a terminal menu/CLI;
the application core is Python, and the executables are not a native GUI.

## Download

Get an archive from the [Releases page](https://github.com/Vaneyk1973/GTNH-Updater/releases), verify its `SHA256SUMS`,
extract the whole archive and keep the license files alongside the executable.
Standalone Windows EXEs are also available; keep `GTNH-Updater-licenses.zip` with them.
The complete platform archives already contain all required notices.

| System | Run | Requirements |
| --- | --- | --- |
| Linux x64 | `./gtnh-updater` | glibc 2.36+ (Debian 12 / Ubuntu 24.04 or newer) |
| Windows 10/11 x64 | `GTNH-Updater.exe` | Binaries are unsigned |
| Windows 7 SP1 x64 | `GTNH-Updater-Win7.exe` | [KB3063858](https://www.microsoft.com/en-us/download/details.aspx?id=47442) or an equivalent AddDllDirectory update |
| Source | `python3 gtnh_updater.py` | Python 3.8+, standard library only |

Windows 7 clean-install uses legacy Prism 7.2 Qt5 x86, GTNH Java 8 and Temurin 8 x64.
`Start-Prism.cmd` installs the official VC++ 2015–2019 x86 runtime, including Universal
CRT, when needed. If it requests a restart, reboot and run it again. Windows 7 and
Prism 7.2 are no longer supported upstream; future login/download compatibility is
uncertain. Minecraft needs a legitimate account and an OpenGL 3.3 core driver.

## Update

Close the game and server. The same commands work on Windows with the EXE name:

```sh
./gtnh-updater configure
./gtnh-updater status
./gtnh-updater check
./gtnh-updater changelog
./gtnh-updater preview --target both
./gtnh-updater update --target both
./gtnh-updater rollback --target both
```

The default target is both configured installations. `--target client|server` selects
one; a client path may be the Prism instance or its `.minecraft`. `--path` overrides
one target for this run. Choose `--channel daily|stable`, `--version EXACT_VERSION`
and `--java java17|java8`. Daily builds are experimental. The updater retains an
existing instance's Java and memory settings.

Before replacement, the updater validates the archive and makes a full TAR backup,
including hidden files and worlds. It checks Java processes and locks the instance.
Failed replacement restores previous managed files; if interruption leaves a pending
operation, run `rollback` before playing. Rollback includes Prism metadata/libraries.
**World changes after updating require restoring the full backup**, rather than only
rolling back mods. Backups are never automatically deleted.

Worlds, resource packs, options, JourneyMap data and NEI bookmarks are retained. Other
managed configuration comes from the new pack. Declare additional JARs in
`CustomClientMods` / `CustomServerMods`, replacements in `OverrideClientMods` /
`OverrideServerMods`, and specific edits in `ConfigPatches`. Unlisted extra mods are
removed by an update, but remain in the full backup. See
[`gtnh-updater.example.json`](gtnh-updater.example.json).

The local profile is `gtnh-updater.json`; `--config FILE` selects another. If absent,
the default profile falls back to the old Bash or PowerShell profile without
overwriting it. Allow space for downloads, staging and the full backup.

## Clean install

```sh
./gtnh-updater clean-install --destination "/games/New GTNH" --channel daily
```

The destination must not exist. Installation is staged beside it and appears when
complete. It contains portable Prism, separate launcher data, GTNH and its own
profile. Open `Start-Prism.sh` / `.cmd`. Modern Prism manages Java downloads.
`--target server` creates a server with local Temurin; `--target both` installs both.
The Minecraft EULA is not accepted automatically. Existing profiles are left alone.

```bat
GTNH-Updater.exe update --config "D:\Games\New GTNH\gtnh-updater.json" --target client
```

## Sources and trust

Downloads come from [GTNH daily](https://github.com/GTNewHorizons/GTNH-Daily-Builds/releases),
[GTNH stable](https://www.gtnewhorizons.com/version-history/),
[Prism](https://github.com/PrismLauncher/PrismLauncher/releases),
[Temurin](https://adoptium.net/) and, for legacy Prism,
[Microsoft VC++ 2019 x86](https://aka.ms/vs/16/release/vc_redist.x86.exe).
HTTPS uses a bundled Mozilla CA store. Upstream SHA256 is checked when published;
ZIP/JAR CRC, safe paths, duplicate mod IDs and launcher files are also verified.
CRC detects corruption; it does not replace a cryptographic upstream digest.
The system certificate store is not changed.

`--archive FILE --version VERSION --target client|server` supports a local ZIP;
its SHA256 is recorded, but the user is responsible for its origin. No Minecraft
files, mod JARs, accounts or Windows images are bundled with the updater.

## Development and license

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
```

See [build/release instructions](docs/RELEASING.md) and [actual tests and limits](docs/TESTING.md).
Updater source is [MIT](LICENSE); the original copyright/provenance is retained in
[NOTICE](NOTICE). Bundled runtimes keep their own licenses in `LICENSES/`.
Downloaded Prism, Java, Minecraft and mods retain their upstream licenses.
This is not an official product of the original author, GTNH, Prism or Mojang/Microsoft.
