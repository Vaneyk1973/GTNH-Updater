"""The release allowlist must not pick up profiles, caches or credentials."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_packager', ROOT/'tools/package-release.py')
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


class PackagingTests(unittest.TestCase):
    def test_source_allowlist_and_binary_licenses(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            public = base/'source'
            public.mkdir()
            for relative in packager.COMMON+packager.SOURCE:
                destination = public/relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT/relative, destination)
            for folder in ['docs', 'LICENSES']:
                shutil.copytree(ROOT/folder, public/folder)
            secret = ('PRIVATE-'+base.name).encode('utf-8')
            for relative in ['gtnh-updater.json', 'accounts.json', 'cache/mod.jar',
                             'backups/world.tar', 'tests/secret.txt', 'lib/credentials.json']:
                path = public/relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(secret)
            binary = base/'binary'
            binary.write_bytes(b'test executable')
            with patch.object(packager, 'ROOT', public):
                for kind in packager.NAMES:
                    archive = packager.package(kind, binary, base/'out')
                    checksum = archive.with_name(archive.name+'.sha256').read_text().split()[0]
                    self.assertEqual(checksum, hashlib.sha256(archive.read_bytes()).hexdigest())
                    if kind == 'linux':
                        with tarfile.open(archive) as packed:
                            members = {m.name: packed.extractfile(m).read() for m in packed.getmembers() if m.isfile()}
                            executable = next(m for m in packed.getmembers() if m.name.endswith('/gtnh-updater'))
                            self.assertTrue(executable.mode & 0o111)
                    else:
                        with zipfile.ZipFile(archive) as packed:
                            members = {name: packed.read(name) for name in packed.namelist()}
                    self.assertFalse(any(secret in data for data in members.values()))
                    self.assertTrue(any(name.endswith('/LICENSE') for name in members))
                    self.assertTrue(any('/LICENSES/Python-' in name for name in members))
                    self.assertTrue(any(name.endswith('/LICENSES/Python-3.13-third-party.rst') for name in members))
                    info = json.loads(next(data for name, data in members.items() if name.endswith('/build-info.json')))
                    self.assertEqual(info['source_sha256']['lib/pack.py'], packager.digest(public/'lib/pack.py'))
                    if kind != 'source':
                        self.assertEqual(info['binary_sha256'], packager.digest(binary))
