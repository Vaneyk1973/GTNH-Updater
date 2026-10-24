"""Integration tests: run the real CLI; never use the user's game directories."""
from pathlib import Path
import hashlib
import io
import sys
import time
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import unittest
import zipfile

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO/'gtnh_updater.py'
CLI = [os.environ['GTNH_TEST_EXECUTABLE']] if os.environ.get('GTNH_TEST_EXECUTABLE') else [sys.executable,str(SCRIPT)]
sys.path.insert(0,str(REPO))
import gtnh_updater as updater
OLD = 'daily-2026-10-23+799'
NEW = 'daily-2026-10-24+800'


def jar(modid, version='1'):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr(zipfile.ZipInfo('mcmod.info',(2026,1,1,0,0,0)), json.dumps([{'modid':modid,'version':version}]))
        archive.writestr(zipfile.ZipInfo('example.class',(2026,1,1,0,0,0)), b'test fixture')
    return buffer.getvalue()


def tree(path):
    return {str(p.relative_to(path)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in path.rglob('*') if p.is_file()}


def make_pack(path, target='client', version='1'):
    game = path/'.minecraft' if target == 'client' else path
    (game/'mods').mkdir(parents=True)
    (game/'config').mkdir()
    for i in range(150):
        name = f'mod{i:03d}' if i else 'gregtech'
        (game/'mods'/f'{name}.jar').write_bytes(jar(name, version if not i else '1'))
    (game/'config/test.cfg').write_text('general {\n    B:flag=true\n}\nother {\n    B:flag=true\n}\n')
    (path/'libraries').mkdir()
    if target == 'client':
        (path/'patches').mkdir()
        (path/'libraries/lwjgl3ify-forgePatches.jar').write_bytes(jar('earlyclasspath', version))
        (path/'patches/launch.json').write_text(json.dumps({'version':version}))
        (path/'mmc-pack.json').write_text(json.dumps({'components':[{'uid':'net.minecraft','version':'1.7.10'}]}))
        (path/'instance.cfg').write_text('InstanceType=OneSix\nname=User instance\n[UI]\nexample=preserved\n')
    else:
        (path/'lwjgl3ify-forgePatches.jar').write_bytes(jar('earlyclasspath', version))
        (path/'java9args.txt').write_text(f'args-{version}')
        (path/'startserver-java9.sh').write_text('#!/bin/bash\njava -Xmx8G custom-args\n')
    return game


def archive_pack(source, destination):
    with zipfile.ZipFile(destination, 'w') as archive:
        for file in source.rglob('*'):
            if file.is_file():
                archive.write(file, 'GTNH Pack/'+file.relative_to(source).as_posix())


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gtnh-bash-test-')
        self.base = Path(self.temp.name)
        self.instance = self.base/'instance Пример with spaces'
        self.game = make_pack(self.instance)
        (self.game/'.gtnh-build.json').write_text(json.dumps({'release':OLD}))
        (self.game/'saves/World').mkdir(parents=True)
        (self.game/'saves/World/level.dat').write_bytes(b'irreplaceable world')
        (self.game/'options.txt').write_text('user options')
        (self.game/'config/NEI').mkdir()
        (self.game/'config/NEI/bookmarks.ini').write_text('my bookmarks')
        self.payload = self.base/'payload'
        make_pack(self.payload, version='2')
        self.archive = self.base/'new pack.zip'
        archive_pack(self.payload, self.archive)
        self.config = self.base/'profile.json'
        self.data = {'ClientInstancePath':str(self.game),'ServerPath':'','DefaultChannel':'daily',
                     'JavaVersion':'java17','BackupDir':str(self.base/'backups')}
        self.save_config()

    def tearDown(self):
        self.temp.cleanup()

    def save_config(self):
        self.config.write_text(json.dumps(self.data))

    def run_cli(self, command, *options, ok=True, env=None):
        args = [*CLI,command,'--config',str(self.config),'--target','client',*options]
        if command in ('update','preview'):
            args += ['--archive',str(self.archive),'--version',NEW]
        result = subprocess.run(args, text=True, encoding='utf-8', capture_output=True, env=env, timeout=30)
        if ok:
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        else:
            self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
        return result

    def test_bad_configure_input_cannot_corrupt_the_profile(self):
        before=self.config.read_bytes()
        result=subprocess.run([*CLI,'configure','--config',str(self.config)],input='\n\nbad-channel\n',
                              text=True,encoding='utf-8',capture_output=True,timeout=30)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('stable or daily',result.stderr)
        self.assertEqual(self.config.read_bytes(),before)

    @unittest.skipUnless(os.name == 'nt','Windows extended paths')
    def test_update_and_rollback_with_paths_beyond_max_path(self):
        parent=updater.pack.fs_path(self.base/('a'*90))
        root=parent/('b'*90)/'instance'
        game=make_pack(root)
        (game/'.gtnh-build.json').write_text(json.dumps({'release':OLD}))
        before=tree(root)
        try:
            self.run_cli('preview','--path',updater.pack.display(root))
            self.run_cli('update','--path',updater.pack.display(root),'--yes')
            self.assertEqual(updater.pack.installed(game),NEW)
            self.run_cli('rollback','--path',updater.pack.display(root),'--yes')
            self.assertEqual(tree(root),before)
        finally:
            shutil.rmtree(parent)

    def test_preview_leaves_instance_unchanged(self):
        before = tree(self.instance)
        result = self.run_cli('preview')
        self.assertIn(NEW,result.stdout)
        self.assertEqual(tree(self.instance),before)
        self.assertFalse((self.base/'backups').exists())

    def test_update_backup_preservation_patch_and_exact_rollback(self):
        (self.game/'mods/extra.jar').write_bytes(jar('extra'))
        self.data['CustomClientMods']=['extra.jar']
        self.data['ConfigPatches']=[{'FilePath':'config/test.cfg','Key':'B:flag','Value':False,'Section':'general','Target':'client'}]
        self.save_config()
        before = tree(self.instance)
        self.run_cli('update','--yes')
        self.assertEqual(json.loads((self.game/'.gtnh-updater-state.json').read_text())['release'],NEW)
        self.assertTrue((self.game/'mods/extra.jar').is_file())
        self.assertEqual((self.game/'saves/World/level.dat').read_bytes(),b'irreplaceable world')
        self.assertEqual((self.game/'config/NEI/bookmarks.ini').read_text(),'my bookmarks')
        self.assertIn('general {\n    B:flag=false', (self.game/'config/test.cfg').read_text())
        self.assertIn('other {\n    B:flag=true', (self.game/'config/test.cfg').read_text())
        with tarfile.open(next((self.base/'backups').glob('*.tar'))) as backup:
            self.assertEqual(backup.extractfile('./.minecraft/saves/World/level.dat').read(),b'irreplaceable world')
        self.run_cli('rollback','--yes')
        self.assertEqual(tree(self.instance),before)

    def test_failed_second_update_keeps_previous_rollback_snapshot(self):
        before=tree(self.instance)
        self.run_cli('update','--yes')
        with self.assertRaisesRegex(OSError,'simulated'):
            self.fail_replace('update')
        self.run_cli('rollback','--yes')
        self.assertEqual(tree(self.instance),before)

    def test_override_replaces_official_mod_by_id(self):
        (self.game/'mods/gregtech.jar').unlink()
        override = self.game/'mods/my-custom-gt.jar'
        override.write_bytes(jar('gregtech','custom'))
        self.data['OverrideClientMods']=['my-custom-gt.jar']
        self.save_config()
        self.run_cli('update','--yes')
        self.assertEqual(override.read_bytes(),jar('gregtech','custom'))
        self.assertFalse((self.game/'mods/gregtech.jar').exists())

    def test_bad_jar_aborts_before_replacing_files(self):
        (self.payload/'.minecraft/mods/mod010.jar').write_bytes(b'not a jar')
        archive_pack(self.payload,self.archive)
        before=tree(self.instance)
        result=self.run_cli('update','--yes',ok=False)
        self.assertIn('not a zip file',result.stderr)
        self.assertEqual(tree(self.instance),before)

    def test_missing_patch_key_aborts_before_replacing_files(self):
        self.data['ConfigPatches']=[{'FilePath':'config/test.cfg','Key':'B:missing','Value':'false'}]
        self.save_config()
        before=tree(self.instance)
        result=self.run_cli('update','--yes',ok=False)
        self.assertIn('Patch requires exactly one key',result.stderr)
        self.assertEqual(tree(self.instance),before)

    def test_zip_traversal_is_rejected(self):
        with zipfile.ZipFile(self.archive,'a') as archive:
            archive.writestr('../escape.txt','escape')
        before=tree(self.instance)
        result=self.run_cli('update','--yes',ok=False)
        self.assertIn('Unsafe relative path',result.stderr)
        self.assertEqual(tree(self.instance),before)
        self.assertFalse((self.base/'escape.txt').exists())

    def fail_replace(self, operation, kill=False):
        original = Path.replace
        failed = []
        def replace(source,destination):
            if source.as_posix().endswith('/new/.minecraft/mods') and not failed:
                failed.append(True)
                if kill:
                    os._exit(74)
                raise OSError('simulated replacement failure')
            return original(source,destination)
        arguments = [operation,'--config',str(self.config),'--target','client','--yes',
                     '--archive',str(self.archive),'--version',NEW]
        with patch.object(Path,'replace',replace):
            updater.run(arguments)

    def test_failed_replacement_automatically_restores_every_file(self):
        before=tree(self.instance)
        with self.assertRaisesRegex(OSError,'simulated'):
            self.fail_replace('update')
        self.assertEqual(tree(self.instance),before)
        self.assertFalse(list(self.base.glob('*.gtnh-pending')))

    def test_process_kill_recovers_even_when_mods_are_missing(self):
        before=tree(self.instance)
        code = "import sys;sys.path.insert(0,sys.argv[1]);from pathlib import Path;import gtnh_updater as u; old=Path.replace;failed=[]\ndef replace(p,d):\n if p.as_posix().endswith('/new/.minecraft/mods') and not failed:\n  import os;os._exit(74)\n return old(p,d)\nPath.replace=replace\nu.run(sys.argv[2:])"
        result=subprocess.run([sys.executable,'-c',code,str(REPO),'update','--yes','--config',str(self.config),
                               '--target','client','--archive',str(self.archive),'--version',NEW],capture_output=True,timeout=30)
        self.assertEqual(result.returncode,74,result.stdout+result.stderr)
        self.assertFalse((self.game/'mods').exists())
        self.run_cli('rollback','--yes')
        self.assertEqual(tree(self.instance),before)

    def test_running_java_blocks_update(self):
        if os.name == 'nt':
            executable=os.environ.get('GTNH_TEST_JAVA') or shutil.which('java')
            if not executable:
                self.skipTest('Set GTNH_TEST_JAVA to a Java executable for the process-safety test')
            alias = self.base/'guard-path-alias'
            alias.mkdir()
            command=[str(executable),'-cp',str(REPO/'tests'),'GuardSleep',str(alias/'..'/self.instance.name)]
        else:
            executable=self.base/'java'
            shutil.copy2('/usr/bin/sleep',executable)
            command=[str(executable),'30']
        process=subprocess.Popen(command,cwd=self.instance,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            time.sleep(.2)
            self.assertIsNone(process.poll(),'Java test process did not start')
            before=tree(self.instance)
            with self.subTest(command=command, canonical_root=str(self.instance.resolve())):
                result=self.run_cli('update','--yes',ok=False)
                self.assertIn('Java process',result.stderr)
                self.assertEqual(tree(self.instance),before)
        finally:
            if os.name == 'nt':
                subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            else:
                process.terminate()
            process.wait()
            process.stdout.close();process.stderr.close()

    def test_downgrade_needs_separate_opt_in(self):
        (self.game/'.gtnh-build.json').write_text(json.dumps({'release':'daily-2026-10-25+801'}))
        result=self.run_cli('update','--yes',ok=False)
        self.assertIn('--allow-downgrade',result.stderr)

    def test_lock_blocks_a_second_updater(self):
        with updater.InstanceLock(self.instance):
            result=self.run_cli('update','--yes',ok=False)
        self.assertIn('Another updater',result.stderr)

    def test_both_targets_are_restored_if_second_commit_fails(self):
        server=self.base/'server'
        make_pack(server,target='server')
        (server/'.gtnh-build.json').write_text(json.dumps({'release':OLD}))
        payload_server=self.base/'payload-server'
        make_pack(payload_server,target='server',version='2')
        server_zip=self.base/'server.zip'
        archive_pack(payload_server,server_zip)
        self.data['ServerPath']=str(server)
        self.save_config()
        catalog=[]
        assets=[]
        for target, archive in [('server',server_zip),('mmcprism',self.archive)]:
            assets.append({'name':f'GTNH-{NEW}-{target}-java17-26.zip','browser_download_url':f'https://fixture/{target}.zip',
                           'digest':'sha256:'+hashlib.sha256(archive.read_bytes()).hexdigest()})
        catalog.append({'tag_name':NEW,'html_url':'https://fixture/release','assets':assets})
        (self.base/'catalog.json').write_text(json.dumps(catalog))
        original = Path.replace
        failed=[]
        def replace(source,destination):
            if source.as_posix().endswith('/new/.minecraft/mods') and not failed:
                failed.append(True)
                raise OSError('second commit failure')
            return original(source,destination)
        def download(url,destination,digest=''):
            source = self.base/('catalog.json' if 'api.github.com' in url else ('server.zip' if url.endswith('/server.zip') else 'new pack.zip'))
            Path(destination).parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,destination)
            return Path(destination)
        before_client,before_server=tree(self.instance),tree(server)
        with patch.object(Path,'replace',replace), patch.object(updater,'download',download), patch.object(updater,'official',lambda *a:None):
            with self.assertRaisesRegex(OSError,'second commit'):
                updater.run(['update','--yes','--config',str(self.config),'--target','both','--cache',str(self.base/'cache')])
        self.assertEqual(tree(self.instance),before_client)
        self.assertEqual(tree(server),before_server)

    def test_atomic_clean_install_cannot_replace_a_new_empty_directory(self):
        stage=self.base/'stage';stage.mkdir();(stage/'new.txt').write_text('new')
        destination=self.base/'destination';destination.mkdir()
        with self.assertRaises(OSError):
            updater.commit_install(stage,destination)
        self.assertEqual(list(destination.iterdir()),[])
        self.assertTrue((stage/'new.txt').exists())

    def test_clean_install_refuses_existing_directory(self):
        result=self.run_cli('clean-install','--destination',str(self.instance),'--yes',ok=False)
        self.assertIn('destination already exists',result.stderr)

    def test_clean_install_uses_official_prism_and_keeps_profile(self):
        prism=self.base/'prism.zip'
        with zipfile.ZipFile(prism,'w') as archive:
            archive.writestr('prismlauncher.exe',b'fixture executable')
        asset={'name':'PrismLauncher-Windows-MinGW-w64-Portable-test.zip','browser_download_url':'https://github.com/PrismLauncher/PrismLauncher/releases/download/test/prism.zip'}
        destination=self.base/'clean with spaces'
        before=self.config.read_bytes()
        with patch.object(updater.platform,'system',return_value='Windows'), patch.object(updater.platform,'machine',return_value='AMD64'), \
             patch.object(updater.sys,'getwindowsversion',create=True,return_value=type('Version',(),{'major':10})()), \
             patch.object(updater,'prism_asset',return_value=(asset,'')), patch.object(updater,'cached',return_value=prism):
            updater.run(['clean-install','--destination',str(destination),'--yes','--archive',str(self.archive),
                         '--version',NEW,'--config',str(self.config)])
        self.assertEqual(self.config.read_bytes(),before)
        profile=json.loads((destination/'gtnh-updater.json').read_text())
        installed=Path(profile['ClientInstancePath'])
        self.assertTrue((installed/'.minecraft/mods/gregtech.jar').exists())
        self.assertTrue((destination/'Start-Prism.cmd').exists())
        import configparser
        cfg=configparser.ConfigParser();cfg.read(str(installed/'instance.cfg'))
        self.assertEqual(cfg['General']['InstanceType'],'OneSix')
        self.assertEqual(cfg['UI']['example'],'preserved')
        self.assertIn('AutomaticJavaDownload=true',(destination/'PrismLauncher/data/prismlauncher.cfg').read_text())
        self.assertEqual(json.loads((installed/'.minecraft/.gtnh-updater-state.json').read_text())['release'],NEW)

    def test_legacy_prism_uses_x86_runtime_with_java8(self):
        prism=self.base/'legacy-prism.zip'
        with zipfile.ZipFile(prism,'w') as archive:
            archive.writestr('prismlauncher.exe',b'32-bit legacy Prism fixture')
        redist=self.base/'redist.exe';redist.write_bytes(b'x86 runtime fixture')
        destination=self.base/'legacy install'
        requested=[]
        def cached(url,*args):
            requested.append(url)
            return redist if 'aka.ms' in url else prism
        def java(destination,*args):
            (destination/'bin').mkdir(parents=True)
            executable=destination/'bin/java.exe';executable.write_bytes(b'Java x64 fixture')
            return executable
        asset={'name':'legacy.zip','browser_download_url':'https://github.com/PrismLauncher/PrismLauncher/releases/download/7.2/legacy.zip'}
        with patch.object(updater.platform,'system',return_value='Windows'), patch.object(updater.platform,'machine',return_value='AMD64'), \
             patch.object(updater.sys,'getwindowsversion',create=True,return_value=type('Version',(),{'major':6})()), \
             patch.object(updater,'prism_asset',return_value=(asset,'')), patch.object(updater,'cached',side_effect=cached), \
             patch.object(updater,'java_runtime',side_effect=java):
            updater.run(['clean-install','--destination',str(destination),'--yes','--archive',str(self.archive),
                         '--version',NEW,'--config',str(self.config)])
        self.assertIn('https://aka.ms/vs/16/release/vc_redist.x86.exe',requested)
        self.assertIn('vc_redist.x86.exe',(destination/'Start-Prism.cmd').read_text())
        self.assertIn('"%errorlevel%"=="3010"',(destination/'Start-Prism.cmd').read_text())
        self.assertIn('exit /b 3010',(destination/'Start-Prism.cmd').read_text())
        self.assertEqual(json.loads((destination/'gtnh-updater.json').read_text())['JavaVersion'],'java8')
        self.assertTrue((destination/'runtime/bin/java.exe').exists())

    def test_clean_install_failure_leaves_no_partial_destination(self):
        destination=self.base/'new install'
        with patch.object(updater,'prism_asset',side_effect=ValueError('network failed')):
            with self.assertRaisesRegex(ValueError,'network failed'):
                updater.run(['clean-install','--destination',str(destination),'--yes','--archive',str(self.archive),
                             '--version',NEW,'--config',str(self.config)])
        self.assertFalse(destination.exists())
        self.assertFalse(list(self.base.glob('.gtnh-install-*')))

    def test_windows_case_collision_and_reserved_names_rejected(self):
        for bad in ['CON.txt','file.txt']:
            with zipfile.ZipFile(self.archive,'w') as archive:
                archive.writestr('FILE.TXT',b'a')
                archive.writestr(bad,b'b')
            self.run_cli('preview',ok=False)

    def test_truncated_download_never_replaces_an_existing_file(self):
        destination=self.base/'existing.zip';destination.write_bytes(b'previous good file')
        class Opener:
            def open(self,*args,**kwargs):
                result=io.BytesIO(b'short')
                result.headers={'Content-Length':'100'}
                return result
        with patch.object(updater,'build_opener',return_value=Opener()), patch.object(updater.time,'sleep'):
            with self.assertRaisesRegex(ValueError,'Truncated'):
                updater.download('https://example.test/pack.zip',destination)
        self.assertEqual(destination.read_bytes(),b'previous good file')
        self.assertFalse(list(self.base.glob('.download-*')))

    def test_large_download_ranges_are_reassembled_and_hash_checked(self):
        content=b'0123456789abcdef'*(3*1024*1024)
        class Opener:
            def open(self,request,**kwargs):
                header=request.get_header('Range')
                if header:
                    start,end=map(int,header[6:].split('-'))
                    result=io.BytesIO(content[start:end+1]);result.status=206
                    result.headers={'Content-Range':'bytes {}-{}/{}'.format(start,end,len(content))}
                else:
                    result=io.BytesIO();result.headers={'Content-Length':str(len(content)),'Accept-Ranges':'bytes'}
                return result
        destination=self.base/'download.zip'
        with patch.object(updater,'build_opener',return_value=Opener()):
            updater.download('https://example.test/pack.zip',destination,hashlib.sha256(content).hexdigest())
        self.assertEqual(updater.sha256(destination),hashlib.sha256(content).hexdigest())

    def test_java8_client_also_requires_valid_prism_components(self):
        (self.payload/'mmc-pack.json').write_text('{"components":[]}')
        with self.assertRaisesRegex(ValueError,'component list'):
            updater.pack.verify(self.payload,'client','java8')

    def test_java8_server_requires_launcher_jars(self):
        root=self.base/'java8-server';make_pack(root,target='server')
        with self.assertRaisesRegex(ValueError,'Forge/Minecraft'):
            updater.pack.verify(root,'server','java8')
        (root/'forge-test.jar').write_bytes(jar('forge'))
        (root/'minecraft_server.1.7.10.jar').write_bytes(jar('minecraft'))
        updater.pack.verify(root,'server','java8')

    def test_unofficial_download_source_rejected(self):
        with self.assertRaisesRegex(ValueError,'Unexpected'):
            updater.official('https://evil.example/PrismLauncher.zip','prism')



if __name__=='__main__':
    unittest.main()
