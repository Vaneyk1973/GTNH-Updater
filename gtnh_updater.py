#!/usr/bin/env python3
"""GTNH updater and portable clean installer. Python 3.8+; standard library only."""
import argparse
import configparser
import ctypes
from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import ssl
import subprocess
import sys
import tarfile
import tempfile
import time
from urllib.parse import quote, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler, HTTPSHandler
from lib import pack

BASE = pack.resolve_path(sys.executable).parent if getattr(sys,'frozen',False) else pack.resolve_path(__file__).parent
DAILY = 'https://api.github.com/repos/GTNewHorizons/GTNH-Daily-Builds/releases'
PRISM = 'https://api.github.com/repos/PrismLauncher/PrismLauncher/releases'


class HTTPSRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        if urlparse(newurl).scheme != 'https':
            pack.fail('Refusing a non-HTTPS redirect')
        return super().redirect_request(request, fp, code, message, headers, newurl)


def https_opener():
    # Bundled Mozilla roots keep TLS verification working on legacy Windows.
    certificates = Path(pack.__file__).with_name('cacert.pem')
    context = ssl.create_default_context(cafile=str(certificates) if certificates.exists() else None)
    return build_opener(HTTPSRedirect(), HTTPSHandler(context=context))


def sha256(path):
    digest = hashlib.sha256()
    with pack.fs_path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            digest.update(chunk)
    return digest.hexdigest()


def download(url, destination, digest=''):
    if urlparse(url).scheme != 'https':
        pack.fail('Downloads require HTTPS')
    destination = pack.fs_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    headers = {'User-Agent':'GTNH-Updater/1.0', 'Accept':'application/vnd.github+json' if 'api.github.com' in url else '*/*'}
    for attempt in range(3):
        try:
            with tempfile.TemporaryDirectory(prefix='.download-',dir=str(destination.parent)) as folder:
                partial = Path(folder)/'complete'
                opener = https_opener()
                with opener.open(Request(url,headers=headers),timeout=60) as response:
                    length = int(response.headers.get('Content-Length','0'))
                    ranged = length > 32*1024*1024 and response.headers.get('Accept-Ranges') == 'bytes'
                    if not ranged:
                        with partial.open('wb') as output:
                            shutil.copyfileobj(response,output,1024*1024)
                if ranged:
                    def fetch_range(index):
                        start, end = length*index//8, length*(index+1)//8-1
                        request = Request(url,headers=dict(headers,Range='bytes={}-{}'.format(start,end)))
                        piece = Path(folder)/str(index)
                        with https_opener().open(request,timeout=60) as response, piece.open('wb') as output:
                            if response.status != 206 or response.headers.get('Content-Range') != 'bytes {}-{}/{}'.format(start,end,length):
                                pack.fail('Server returned an invalid download range')
                            shutil.copyfileobj(response,output,1024*1024)
                        if piece.stat().st_size != end-start+1:
                            pack.fail('Truncated download range')
                        return piece
                    with ThreadPoolExecutor(max_workers=8) as pool:
                        pieces = list(pool.map(fetch_range,range(8)))
                    with partial.open('wb') as output:
                        for piece in pieces:
                            with piece.open('rb') as stream:
                                shutil.copyfileobj(stream,output,1024*1024)
                if length and partial.stat().st_size != length:
                    pack.fail('Truncated download: '+url)
                if digest and sha256(partial).lower() != digest.lower():
                    pack.fail('SHA256 mismatch: '+url)
                partial.replace(destination)
                return destination
        except (OSError, ValueError):
            if attempt == 2:
                raise
            time.sleep(1+attempt)


def cached(url, cache, digest=''):
    cache = pack.fs_path(cache)
    name = hashlib.sha256(url.encode()).hexdigest()[:16]+'-'+Path(urlparse(url).path).name
    destination = cache/name
    if destination.is_file() and (not digest or sha256(destination) == digest):
        return destination
    print('Downloading: '+url, flush=True)
    return download(url, destination, digest)


def metadata(url, work):
    return download(url, Path(work)/'metadata.json')


def official(url, service):
    parsed = urlparse(url)
    prefixes = {'gtnh':['https://github.com/GTNewHorizons/GTNH-Daily-Builds/releases/download/',
                         'https://downloads.gtnewhorizons.com/'],
                'prism':['https://github.com/PrismLauncher/PrismLauncher/releases/download/'],
                'java':['https://github.com/adoptium/temurin8-binaries/releases/download/',
                        'https://github.com/adoptium/temurin21-binaries/releases/download/']}[service]
    if parsed.scheme != 'https' or not any(url.startswith(prefix) for prefix in prefixes):
        pack.fail('Unexpected '+service+' download source: '+url)
    return url


def release_for(args, target, work):
    if args.archive:
        return {'release':args.version, 'channel':args.channel, 'archive':Path(args.archive).name,
                'target':target, 'java':args.java, 'source':'local archive', 'sha256':''}
    url = (DAILY+('/tags/'+quote(args.version, safe='') if args.version else '?per_page=20')
           if args.channel == 'daily' else 'https://www.gtnewhorizons.com/version-history/')
    result = pack.select_release(metadata(url, work), args.channel, args.version or '', target, args.java)
    official(result['url'], 'gtnh')
    args.version = result['release']  # Both selected targets use exactly the same release.
    return result


def profile(args):
    path = pack.resolve_path(args.config if args.config else BASE/'gtnh-updater.json')
    source = path
    if not args.config and not source.exists():
        source = next((p for p in [BASE/'gtnh-updater-bash.json', BASE/'gtnh-updater-config.json'] if p.exists()), path)
    data = pack.read_json(source) if source.exists() else {}
    if not isinstance(data, dict):
        pack.fail('Config must be a JSON object')
    args.channel = args.channel or data.get('DefaultChannel', 'daily')
    args.java = args.java or data.get('JavaVersion', 'java17')
    if args.channel not in ('daily','stable') or args.java not in ('java8','java17'):
        pack.fail('Invalid channel or JavaVersion in profile')
    args.cache = pack.resolve_path(args.cache or data.get('CacheDir', BASE/'cache'))
    return path, data


def selected(args, data):
    targets = []
    for target, field in [('server','ServerPath'), ('client','ClientInstancePath')]:
        if args.target not in (target,'both'):
            continue
        value = args.path or data.get(field)
        if not value:
            continue
        root = pack.resolve_path(value)
        if target == 'client' and root.name == '.minecraft':
            root = root.parent
        if not root.is_dir():
            pack.fail('Instance does not exist: '+str(root))
        if any(pack.inside(root, other) or pack.inside(other, root) for _,other in targets):
            pack.fail('Selected instance directories overlap')
        targets.append((target,root))
    if not targets:
        pack.fail('No instances selected; run configure or supply --target and --path')
    return targets


def game(root, target):
    return root/'.minecraft' if target == 'client' else root


def marker(root, suffix):
    root = pack.fs_path(root)
    return root.parent/('.'+root.name+'.gtnh-'+suffix)


class InstanceLock:
    def __init__(self, root):
        self.root = pack.fs_path(root)
    def __enter__(self):
        self.stream = marker(self.root, 'lock').open('a+b')
        if os.fstat(self.stream.fileno()).st_size == 0:
            self.stream.write(b'0'); self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stream.close()
            pack.fail('Another updater is using '+pack.display(self.root))
        return self
    def __exit__(self, *exc):
        self.stream.close()


def remove(path):
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def snapshot(root):
    pointer = marker(root, 'pending') if marker(root,'pending').exists() else marker(root,'last')
    if not pointer.exists():
        pack.fail('No snapshot for '+pack.display(root))
    txn = pack.resolve_path(pack.read_json(pointer)['transaction'])
    if txn.parent != root.parent or not txn.name.startswith('.'+root.name+'.gtnh-stage-'):
        pack.fail('Invalid snapshot pointer')
    plan = pack.read_json(txn/'plan.json')
    if plan['root'] != str(root):
        pack.fail('Snapshot belongs to another instance')
    return txn, plan


def restore(root, txn, plan):
    for entry in reversed(plan['paths']):
        relative = entry['path']
        destination, old, new = [pack.contained(base, relative) for base in (root,txn/'old',txn/'new')]
        if old.exists() or old.is_symlink():
            remove(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            old.replace(destination)
        elif not entry['existed'] and not new.exists():
            remove(destination)
    marker(root,'pending').unlink(missing_ok=True)
    if marker(root,'last').exists() and pack.read_json(marker(root,'last')).get('transaction') == str(txn):
        marker(root,'last').unlink()


def confirm(args, message):
    if args.yes:
        return True
    if not sys.stdin.isatty():
        pack.fail('Confirmation requires a terminal; use --yes for unattended runs')
    return input(message+' [y/N] ').strip().lower() == 'y'


def backup(root, target, directory):
    directory = pack.fs_path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if pack.inside(directory, root):
        pack.fail('Backup directory must be outside the instance')
    name = 'gtnh-'+target+'-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'-'+str(os.getpid())+'.tar'
    destination = directory/name
    partial = destination.with_suffix('.tar.part')
    print('Full backup (including dotfiles): '+pack.display(destination), flush=True)
    try:
        with tarfile.open(partial, 'w') as archive:
            archive.add(root, arcname='.', recursive=True)
        with tarfile.open(partial) as archive:
            required = './.minecraft/mods' if target == 'client' else './mods'
            if required not in archive.getnames():
                pack.fail('Backup has no mods directory')
        partial.replace(destination)
    finally:
        partial.unlink(missing_ok=True)


def update(args, data, targets, work):
    transactions = []
    applying = False
    try:
        config = Path(work)/'config.json'; pack.write_json(config, data)
        for target,root in targets:
            pack.preflight(root, target)
            if marker(root,'pending').exists():
                pack.fail('Interrupted update; run rollback first: '+pack.display(root))
            if marker(root,'last').exists():
                snapshot(root)
            txn = Path(tempfile.mkdtemp(prefix='.'+root.name+'.gtnh-stage-', dir=str(root.parent)))
            transactions.append((target,root,txn))
            for name in ('new','old','extract'):
                (txn/name).mkdir()
            release = release_for(args, target, work)
            if pack.downgrade(pack.installed(game(root,target)), release['release']) and not args.allow_downgrade:
                pack.fail('Downgrade/channel cut requires --allow-downgrade')
            archive = pack.fs_path(args.archive) if args.archive else cached(release['url'], args.cache, release['sha256'])
            release['sha256'] = sha256(archive)
            release_file = txn/'release.json'; pack.write_json(release_file,release)
            payload = pack.extract(archive, txn/'extract', target)
            paths = pack.prepare(root,payload,txn/'new',target,config,release_file,args.java)
            pack.write_json(txn/'plan.json',{'root':str(root), 'paths':paths})
            shutil.rmtree(txn/'extract')
        if args.command == 'preview' or not confirm(args,'Create full backups and apply these changes?'):
            return
        for target,root,txn in transactions:
            pack.preflight(root,target)
            backup(root,target,pack.resolve_path(data.get('BackupDir', BASE/'backups')))
        for target,root,txn in transactions:
            pack.preflight(root,target)
        applying = True
        for target,root,txn in transactions:
            pack.write_json(marker(root,'pending'), {'transaction':str(txn)})
            for entry in pack.read_json(txn/'plan.json')['paths']:
                relative = entry['path']
                destination, old, new = [pack.contained(base,relative) for base in (root,txn/'old',txn/'new')]
                if destination.exists():
                    old.parent.mkdir(parents=True, exist_ok=True)
                    destination.replace(old)
                if new.exists():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    new.replace(destination)
            pack.verify(root,target,args.java)
        for target,root,txn in transactions:
            previous = Path(pack.read_json(marker(root,'last'))['transaction']) if marker(root,'last').exists() else None
            if previous and (previous.parent != root.parent or not previous.name.startswith('.'+root.name+'.gtnh-stage-')):
                pack.fail('Invalid previous snapshot pointer')
            pack.write_json(marker(root,'last'), {'transaction':str(txn)})
            marker(root,'pending').unlink()
            (txn/'committed').touch()
            if previous and previous != txn:
                shutil.rmtree(previous)
            print('Updated '+target+' to '+args.version+'. Snapshot: '+pack.display(txn))
        applying = False
    except BaseException:
        if applying:
            for target,root,txn in reversed(transactions):
                if marker(root,'pending').exists():
                    print('Restoring '+target+' after failure...',file=sys.stderr)
                    try:
                        restore(root,txn,pack.read_json(txn/'plan.json'))
                    except Exception as error:
                        print('RECOVERY REQUIRED: '+str(txn)+'; '+str(error),file=sys.stderr)
        raise
    finally:
        for _,root,txn in transactions:
            if not (txn/'committed').exists() and not marker(root,'pending').exists():
                shutil.rmtree(txn,ignore_errors=True)


def prism_asset(system, legacy, architecture, work):
    release = pack.read_json(metadata(PRISM+('/tags/7.2' if legacy else '/latest'),work))
    if system == 'Windows':
        name = 'PrismLauncher-Windows-MSVC-Legacy-Portable-7.2.zip' if legacy else 'PrismLauncher-Windows-MinGW-w64-Portable-'+release['tag_name']+'.zip'
    else:
        name = 'PrismLauncher-Linux-'+('aarch64' if architecture in ('aarch64','arm64') else 'x86_64')+'.AppImage'
    asset = next((a for a in release['assets'] if a['name'] == name),None)
    if not asset:
        pack.fail('Official Prism portable asset unavailable: '+name)
    official(asset['browser_download_url'],'prism')
    digest = asset.get('digest') or ''
    return asset, digest[7:] if digest.startswith('sha256:') else ''


def java_runtime(destination, args, system, architecture, work):
    major = 8 if args.java == 'java8' else 21
    os_name = 'windows' if system == 'Windows' else 'linux'
    arch = 'aarch64' if architecture in ('aarch64','arm64') else 'x64'
    url = 'https://api.adoptium.net/v3/assets/latest/{}/hotspot?architecture={}&image_type=jre&os={}&vendor=eclipse'.format(major,arch,os_name)
    releases = pack.read_json(metadata(url,work))
    asset = releases[0]['binary']['package']
    official(asset['link'],'java')
    archive = cached(asset['link'],args.cache,asset['checksum'])
    extracted = pack.fs_path(Path(work)/('java-'+os_name)); extracted.mkdir()
    if os_name == 'windows':
        pack.unpack_zip(archive,extracted)
    else:
        with tarfile.open(archive) as tar:
            members = tar.getmembers()
            for entry in members:
                path = pack.contained(extracted, entry.name)
                if entry.isdev() or entry.isfifo():
                    pack.fail('Unsafe Java TAR entry: '+entry.name)
                if entry.issym() or entry.islnk():
                    link = (path.parent/entry.linkname if entry.issym() else extracted/entry.linkname).resolve()
                    if not pack.inside(link,extracted):
                        pack.fail('Java TAR link leaves archive')
            tar.extractall(extracted)
    executable = next(extracted.rglob('java.exe' if system == 'Windows' else 'java'))
    shutil.copytree(executable.parent.parent,destination,symlinks=True)
    return destination/'bin'/executable.name


def commit_install(stage, destination):
    if os.name == 'nt':
        stage.rename(destination)
        return
    libc = ctypes.CDLL(None,use_errno=True)
    if not hasattr(libc,'renameat2'):
        pack.fail('Atomic clean-install requires Linux libc with renameat2')
    rename = libc.renameat2
    rename.argtypes = [ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
    # AT_FDCWD, RENAME_NOREPLACE: an existing empty directory must also survive.
    if rename(-100,os.fsencode(stage),-100,os.fsencode(destination),1):
        error = ctypes.get_errno()
        raise OSError(error,os.strerror(error),str(destination))


def clean_install(args, data, work):
    if not args.destination:
        pack.fail('clean-install requires --destination NEW_DIRECTORY')
    destination = pack.resolve_path(args.destination)
    if destination.exists() or destination.is_symlink():
        pack.fail('Clean install requires a new directory; destination already exists')
    if not destination.parent.is_dir():
        pack.fail('Destination parent does not exist')
    system, architecture = platform.system(), platform.machine().lower()
    if system not in ('Windows','Linux') or (system == 'Windows' and architecture not in ('amd64','x86_64')):
        pack.fail('Supported: Windows x64 and Linux x86_64/aarch64')
    legacy = system == 'Windows' and sys.getwindowsversion().major < 10
    if legacy:
        args.java = 'java8'
        print('Windows 7/8 compatibility: Prism 7.2 Qt5 and Java 8 (legacy, unsupported upstream)')
    if args.target == 'both' and args.archive:
        pack.fail('--archive requires one target')
    if not confirm(args,'Install official Prism/GTNH into '+pack.display(destination)+'?'):
        return
    stage = Path(tempfile.mkdtemp(prefix='.gtnh-install-',dir=str(destination.parent)))
    try:
        result = {'DefaultChannel':args.channel,'JavaVersion':args.java,'ServerPath':'','ClientInstancePath':''}
        runtime = None
        for target in ('server','client'):
            if args.target not in (target,'both'):
                continue
            release = release_for(args,target,work)
            archive = pack.fs_path(args.archive) if args.archive else cached(release['url'],args.cache,release['sha256'])
            extracted = Path(work)/('pack-'+target); extracted.mkdir()
            payload = pack.extract(archive,extracted,target)
            pack.verify(payload,target,args.java)
            if target == 'client':
                launcher = stage/'PrismLauncher'; launcher.mkdir()
                asset,digest = prism_asset(system,legacy,architecture,work)
                prism = cached(asset['browser_download_url'],args.cache,digest)
                if system == 'Windows':
                    pack.unpack_zip(prism,launcher)
                    executable = 'prismlauncher.exe'
                    if not (launcher/executable).is_file():
                        pack.fail('Prism executable missing in portable archive')
                else:
                    executable = 'PrismLauncher.AppImage'
                    shutil.copy2(prism,launcher/executable); (launcher/executable).chmod(0o755)
                instance = launcher/'data/instances'/('GTNH-'+release['release'].replace('+','_'))
                instance.parent.mkdir(parents=True)
                shutil.copytree(payload,instance)
                for script in instance.rglob('*.sh'):
                    script.chmod(script.stat().st_mode | 0o111)
                settings = '[General]\nMaxMemAlloc=6144\nMinMemAlloc=1024\nAutomaticJavaDownload=true\nAutomaticJavaSwitch=true\n'
                cfg = configparser.ConfigParser(interpolation=None, strict=False)
                cfg.optionxform = str
                if (instance/'instance.cfg').exists():
                    cfg.read_string('[General]\n'+(instance/'instance.cfg').read_text(encoding='utf-8-sig'))
                if not cfg.has_section('General'):
                    cfg.add_section('General')
                for key in ('JavaPath','OverrideJavaLocation','OverrideJavaArgs','JvmArgs','JavaArchitecture','JavaVersion'):
                    cfg.remove_option('General',key)
                if legacy:
                    runtime = runtime or java_runtime(stage/'runtime',args,system,architecture,work)
                    final_java = destination/runtime.relative_to(stage)
                    settings += 'JavaPath='+pack.display(final_java).replace('\\','/')+'\n'
                    cfg['General']['OverrideJavaLocation'] = 'true'
                    cfg['General']['JavaPath'] = pack.display(final_java).replace('\\','/')
                    redist = cached('https://aka.ms/vs/16/release/vc_redist.x86.exe',args.cache)
                    shutil.copy2(redist,stage/'vc_redist.x86.exe')
                else:
                    cfg['General']['OverrideJavaLocation'] = 'false'
                    cfg['General']['AutomaticJava'] = 'true'
                (launcher/'data/prismlauncher.cfg').write_text(settings,encoding='utf-8')
                with (instance/'instance.cfg').open('w',encoding='utf-8') as output:
                    cfg.write(output, space_around_delimiters=False)
                if system == 'Windows':
                    (stage/'Start-Prism.cmd').write_text('@echo off\r\ncd /d "%~dp0"\r\n'+('start /wait "" "%~dp0vc_redist.x86.exe" /install /passive /norestart\r\nif "%errorlevel%"=="3010" (\r\n  echo Restart Windows to finish installing the Prism runtime, then run this file again.\r\n  pause\r\n  exit /b 3010\r\n)\r\nif errorlevel 1 if not "%errorlevel%"=="1638" (\r\n  echo Prism runtime installation failed.\r\n  pause\r\n  exit /b 1\r\n)\r\n' if legacy else '')+'start "" "%~dp0PrismLauncher\\'+executable+'" --dir "%~dp0PrismLauncher\\data"\r\n',encoding='utf-8')
                else:
                    (stage/'Start-Prism.sh').write_text('#!/usr/bin/env bash\nset -e\ncd -- "$(dirname -- "$0")"\nAPPIMAGE_EXTRACT_AND_RUN=1 exec ./PrismLauncher/'+executable+' --dir "$PWD/PrismLauncher/data" "$@"\n')
                    (stage/'Start-Prism.sh').chmod(0o755)
                root = instance
                result['ClientInstancePath'] = pack.display(destination/instance.relative_to(stage))
                result['PrismVersion'] = '7.2' if legacy else asset['name']
            else:
                root = stage/'server'; shutil.copytree(payload,root)
                runtime = runtime or java_runtime(stage/'runtime',args,system,architecture,work)
                script = 'startserver-java9.bat' if args.java == 'java17' else 'startserver.bat'
                if system == 'Windows':
                    (stage/'Start-Server.cmd').write_text('@echo off\r\nset "JAVA_HOME=%~dp0runtime"\r\nset "PATH=%JAVA_HOME%\\bin;%PATH%"\r\ncd /d "%~dp0server"\r\ncall "'+script+'"\r\n',encoding='utf-8')
                else:
                    script = 'startserver-java9.sh' if args.java == 'java17' else 'startserver.sh'
                    (stage/'Start-Server.sh').write_text('#!/usr/bin/env bash\nset -e\ncd -- "$(dirname -- "$0")"\nexport JAVA_HOME="$PWD/runtime"\nexport PATH="$JAVA_HOME/bin:$PATH"\ncd server\nexec bash '+script+'\n')
                    (stage/'Start-Server.sh').chmod(0o755)
                result['ServerPath'] = pack.display(destination/'server')
            release['sha256'] = sha256(archive)
            release['installed_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
            pack.write_json(game(root,target)/'.gtnh-updater-state.json',release)
        pack.write_json(stage/'gtnh-updater.json',result)
        commit_install(stage,destination)
        print('Installed: '+pack.display(destination))
        print('Profile: '+pack.display(destination/'gtnh-updater.json'))
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def run(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',nargs='?',default='status',choices=['status','check','preview','update','rollback','changelog','configure','clean-install'])
    parser.add_argument('--target',choices=['server','client','both'])
    parser.add_argument('--channel',choices=['daily','stable'])
    parser.add_argument('--java',choices=['java17','java8'])
    for option in ('version','config','path','archive','cache','destination'):
        parser.add_argument('--'+option)
    parser.add_argument('--yes',action='store_true')
    parser.add_argument('--allow-downgrade',action='store_true')
    args = parser.parse_args(argv)
    args.target = args.target or ('client' if args.command == 'clean-install' else 'both')
    if args.path and args.target == 'both':
        pack.fail('--path requires one target')
    if args.archive and (not args.version or args.target == 'both'):
        pack.fail('--archive requires --version and one target')
    config,data = profile(args)
    if args.command == 'configure':
        for field,label in [('ServerPath','Server directory'),('ClientInstancePath','Prism instance or .minecraft')]:
            value = input(label+' ['+data.get(field,'')+'] (empty keeps, - disables): ').strip().strip(chr(34))
            if value:
                data[field] = '' if value == '-' else value
        channel = input('Channel ['+args.channel+']: ').strip() or args.channel
        if channel not in ('stable','daily'):
            pack.fail('Use stable or daily')
        data['DefaultChannel'] = channel
        data['JavaVersion'] = args.java
        config.parent.mkdir(parents=True,exist_ok=True)
        pack.write_json(config,data)
        print('Saved: '+pack.display(config)); return
    if args.command == 'clean-install':
        with tempfile.TemporaryDirectory(prefix='gtnh-install-',dir=str(pack.fs_path(tempfile.gettempdir()))) as work:
            clean_install(args,data,work)
        return
    targets = selected(args,data)
    if args.command == 'status':
        for target,root in targets:
            print(target+': '+pack.installed(game(root,target))+'\n  '+pack.display(root))
            if marker(root,'pending').exists():
                print('  Interrupted update: run rollback before launching the game')
        return
    with tempfile.TemporaryDirectory(prefix='gtnh-updater-',dir=str(pack.fs_path(tempfile.gettempdir()))) as work:
        if args.command in ('check','changelog'):
            for target,root in targets:
                release = release_for(args,target,work)
                current = pack.installed(game(root,target)); latest = release['release']
                print(target+': '+current+' -> '+latest+'\n'+release['source'])
                if args.command == 'changelog' and current != latest:
                    before,after = re.search(r'\+(\d+)$',current),re.search(r'\+(\d+)$',latest)
                    if before and after and int(after[1]) > int(before[1]):
                        for number in range(int(before[1]),int(after[1])):
                            name = 'changelog from daily {} to {}.md'.format(number,number+1)
                            url = 'https://raw.githubusercontent.com/GTNewHorizons/DreamAssemblerXXL/master/releases/changelogs/daily%20builds/'+quote(name)
                            print(download(url,Path(work)/'changelog.md').read_text(encoding='utf-8'))
                    else:
                        print('See the release link for changelog details')
            return
        with ExitStack() as locks:
            for target,root in sorted(targets,key=lambda item:str(item[1])):
                locks.enter_context(InstanceLock(root))
                pack.preflight(root,target,args.command)
            if args.command == 'rollback':
                plans = [(target,root,*snapshot(root)) for target,root in targets]
                if confirm(args,'Restore previous managed files?'):
                    for target,root,txn,plan in plans:
                        restore(root,txn,plan); shutil.rmtree(txn)
                        print('Restored '+target+': '+pack.installed(game(root,target)))
            else:
                update(args,data,targets,work)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8',errors='backslashreplace')
    sys.stderr.reconfigure(encoding='utf-8',errors='backslashreplace')
    def interrupted(signum,frame):
        raise KeyboardInterrupt('Interrupted by signal '+str(signum))
    signal.signal(signal.SIGTERM,interrupted)
    interactive = len(sys.argv) == 1 and sys.stdin.isatty()
    try:
        if interactive:
            while True:
                print('\nGTNH Updater\n1 Status  2 Check  3 Preview  4 Update  5 Rollback  6 Changelog  7 Configure  8 Clean install  Q Quit')
                choice = input('> ').strip().lower()
                if choice == 'q':
                    break
                commands = {'1':'status','2':'check','3':'preview','4':'update','5':'rollback','6':'changelog','7':'configure','8':'clean-install'}
                if choice not in commands:
                    continue
                arguments = [commands[choice]]
                if choice == '8':
                    arguments += ['--destination',input('New installation directory: ').strip().strip('"')]
                try:
                    run(arguments)
                except Exception as error:
                    print('ERROR: '+str(error),file=sys.stderr)
        else:
            run()
    except (Exception, KeyboardInterrupt) as error:
        print('ERROR: '+str(error),file=sys.stderr)
        sys.exit(1)
