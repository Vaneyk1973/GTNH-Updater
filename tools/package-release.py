"""Package reviewed sources or an already-built executable; never include user data."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
COMMON = ['README.md', 'README.ru.md', 'CHANGELOG.md', 'LICENSE', 'NOTICE', 'gtnh-updater.example.json']
SOURCE = ['.gitignore', '.gitattributes', 'gtnh_updater.py', 'Update-GTNH.sh', 'Launch-GTNHUpdater.sh',
          'Update-GTNH.cmd', 'Launch-GTNHUpdater.bat', 'CONTRIBUTING.md', 'SECURITY.md',
          '.github/ISSUE_TEMPLATE/bug_report.yml',
          'lib/__init__.py', 'lib/pack.py', 'lib/cacert.pem',
          'tests/test_updater.py', 'tests/test_packaging.py',
          'tests/GuardSleep.java', 'tests/GuardSleep.class',
          'tools/build-linux.sh', 'tools/build-windows.cmd',
          'tools/build-requirements.txt', 'tools/build-requirements-win7.txt',
          'tools/build-requirements-linux.txt', 'tools/package-release.py',
          '.github/workflows/tests.yml', '.github/workflows/build.yml']
NAMES = {'source': 'GTNH-Updater-source', 'linux': 'GTNH-Updater-linux-x64',
         'windows': 'GTNH-Updater-windows10-11-x64', 'win7': 'GTNH-Updater-windows7-x64'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package(kind, binary, output):
    if kind != 'source' and (binary is None or not binary.is_file()):
        raise ValueError('Binary packaging requires --binary FILE')
    output.mkdir(parents=True, exist_ok=True)
    name = NAMES[kind]
    with tempfile.TemporaryDirectory(prefix='gtnh-package-') as temporary:
        stage = Path(temporary)/name
        stage.mkdir()
        files = COMMON + (SOURCE if kind == 'source' else [])
        # Only public documentation/license files, never arbitrary directory copies.
        files += [p.relative_to(ROOT).as_posix() for folder, pattern in
                  [('LICENSES', '*.txt'), ('LICENSES', '*.rst'), ('docs', '*.md')]
                  for p in sorted((ROOT/folder).glob(pattern))]
        for relative in files:
            source = ROOT/relative
            if source.is_symlink() or not source.is_file():
                raise ValueError('Missing or symlinked public file: '+relative)
            target = stage/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        info = {'source_sha256': {p: digest(ROOT/p) for p in
                ['gtnh_updater.py', 'lib/pack.py', 'lib/cacert.pem']},
                'packaging_python': platform.python_version()}
        if kind != 'source':
            executable = 'gtnh-updater' if kind == 'linux' else (
                'GTNH-Updater-Win7.exe' if kind == 'win7' else 'GTNH-Updater.exe')
            shutil.copy2(binary, stage/executable)
            if kind == 'linux':
                (stage/executable).chmod(0o755)
            info['binary_sha256'] = digest(stage/executable)
            for wrapper in (['Update-GTNH.sh', 'Launch-GTNHUpdater.sh'] if kind == 'linux'
                            else ['Update-GTNH.cmd', 'Launch-GTNHUpdater.bat']):
                shutil.copy2(ROOT/wrapper, stage/wrapper)
        (stage/'build-info.json').write_text(json.dumps(info, indent=2)+'\n', encoding='utf-8')
        archive = output/(name+('.tar.gz' if kind == 'linux' else '.zip'))
        if kind == 'linux':
            def executable_modes(member):
                if member.name == name+'/gtnh-updater' or member.name.endswith('.sh'):
                    member.mode = 0o755
                return member
            with tarfile.open(archive, 'w:gz') as target:
                target.add(stage, arcname=name, filter=executable_modes)
        else:
            with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as target:
                for file in sorted(stage.rglob('*')):
                    if file.is_file():
                        target.write(file, file.relative_to(stage.parent).as_posix())
            with zipfile.ZipFile(archive) as target:
                if target.testzip() is not None:
                    raise ValueError('Archive verification failed')
    archive.with_name(archive.name+'.sha256').write_text(
        digest(archive)+'  '+archive.name+'\n', encoding='ascii')
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('platform', choices=NAMES)
    parser.add_argument('--binary', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT/'dist/release')
    args = parser.parse_args()
    print(package(args.platform, args.binary, args.output))
