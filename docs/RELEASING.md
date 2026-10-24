# Build and release

**Tests** runs source tests on Linux/Windows with Python 3.8 and 3.13.
**Build archives** is manually triggered and uploads artifacts; it does not publish
a GitHub release automatically. Repository permissions are read-only.

## Local builds

Windows 10/11 x64, Python 3.13.17:

```bat
python -m pip install -r tools\build-requirements.txt
tools\build-windows.cmd
python tools\package-release.py windows --binary dist\GTNH-Updater.exe
```

Legacy Windows, Python 3.8.10 x64:

```bat
python -m pip install -r tools\build-requirements-win7.txt
tools\build-windows.cmd --legacy
python tools\package-release.py win7 --binary dist\GTNH-Updater-Win7.exe
```

Linux x64: build on Debian 12 / glibc 2.36 with Python 3.13.17 and binutils:

```sh
python3 -m pip install -r tools/build-requirements-linux.txt
bash tools/build-linux.sh
python3 tools/package-release.py linux --binary dist/gtnh-updater
python3 tools/package-release.py source
```

Archives and individual `.sha256` files appear in `dist/release/`. Combine those
checksum files into `SHA256SUMS`. Every binary archive includes licenses and a manifest
with source/binary hashes and packaging Python version. The packager only includes
listed files. It does not build or sign executables.

## Release checks

1. Run `python -m unittest discover -s tests -p "test_*.py"`.
2. Set `GTNH_TEST_EXECUTABLE` to each new executable's absolute path and rerun tests.
   Clear it afterward. Check packaged `--help` too.
3. Extract archives into fresh directories. Check status/preview/clean-install on
   disposable instances. Test the legacy binary on Windows 7 itself.
4. Start a real client to its menu and a test server to world-ready, stop and confirm
   saves. Document missing checks; do not reuse an old result for changed binaries.
5. Review `git diff --check`, staged files and archive members. Exclude private profiles,
   tokens, worlds, VM images and Minecraft/mod files. Keep original MIT and NOTICE.
6. Update TESTING.md; review third-party licenses if build dependencies change.

Use **0.1.0**, marked **Pre-release**, for the first public release: legacy support,
unsigned binaries and limited real-world testing should be visible in the notes.

## GitHub setup

The public repository is [Vaneyk1973/GTNH-Updater](https://github.com/Vaneyk1973/GTNH-Updater).
Keep executable files and archives in Releases, not in the Git source tree.
Enable Issues and private vulnerability reporting. Repository description:

> Unofficial GTNH client/server updater with full backups, rollback and portable Prism clean installs for Linux and Windows.

Topics: `gtnh`, `gregtech`, `minecraft`, `prismlauncher`, `modpack`, `updater`, `linux`,
`windows`, `backup`.

Run both workflows on GitHub, inspect results and create a draft 0.1.0 release with
source/Linux/modern Windows/Win7 archives, the two standalone Windows EXEs,
`GTNH-Updater-licenses.zip`, SHA256SUMS and release notes. The license ZIP must
accompany standalone EXE distribution; platform archives include the notices already. Verify public
anonymous downloads before announcing. Do not distribute unreviewed PR artifacts.
