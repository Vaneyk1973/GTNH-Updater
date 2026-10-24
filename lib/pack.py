#!/usr/bin/env python3
"""Pack validation and configuration; Python 3.8+ standard library only."""
import ctypes
import datetime as dt
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import zipfile


def fail(message):
    raise ValueError(message)


NT_PREFIX = '\\\\?\\'
UNC_PREFIX = NT_PREFIX+'UNC'+chr(92)


def fs_path(value):
    path = Path(value).expanduser()
    if os.name != 'nt':
        return path
    value = os.path.abspath(str(path))
    if value.startswith(NT_PREFIX):
        return Path(value)
    if value.startswith(chr(92)*2):
        return Path(UNC_PREFIX+value[2:])
    return Path(NT_PREFIX+value)


def resolve_path(value):
    # Python 3.8 removes the NT prefix in Path.resolve(); restore it for file I/O.
    return fs_path(fs_path(value).resolve())


def display(path):
    value = str(path)
    if os.name == 'nt' and value.startswith(UNC_PREFIX):
        return chr(92)*2+value[8:]
    if os.name == 'nt' and value.startswith(NT_PREFIX):
        return value[4:]
    return value


def inside(path, root):
    try:
        resolve_path(path).relative_to(resolve_path(root))
        return True
    except ValueError:
        return False


def read_json(path):
    return json.loads(fs_path(path).read_text(encoding='utf-8-sig'))


def write_json(path, data):
    path = fs_path(path)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def contained(root, relative):
    relative = str(relative).replace('\\', '/')
    parts = PurePosixPath(relative)
    if parts.is_absolute() or '..' in parts.parts or ':' in relative or '\n' in relative or '\t' in relative:
        fail(f'Unsafe relative path: {relative!r}')
    path = fs_path(root) / relative
    if not inside(path, root):
        fail(f'Path leaves instance: {path}')
    return path


def copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink() or destination.is_file():
        destination.unlink()
    elif destination.exists():
        shutil.rmtree(destination)
    if source.is_symlink():
        fail(f'Refusing to preserve symlink: {source}')
    if source.is_dir():
        if any(path.is_symlink() for path in source.rglob('*')):
            fail(f'Refusing to preserve nested symlink: {source}')
        shutil.copytree(source, destination)
    else:
        shutil.copy2(source, destination)


def installed(path):
    path = fs_path(path)
    for name, key in [('.gtnh-updater-state.json', 'release'), ('.gtnh-bash-state.json', 'release'), ('.gtnh-build.json', 'release'),
                      ('.gtnh-nightly-state.json', 'InstalledVersion')]:
        file = Path(path) / name
        if file.exists():
            value = read_json(file).get(key)
            if value:
                return value
    for file in sorted(Path(path).glob('changelog from *'), reverse=True):
        match = re.search(r' to (\d+\.\d+\.\d+(?:[-_][\w-]+)?)\.(?:txt|md)$', file.name, re.I)
        if match:
            return match[1]
    return 'unknown'


def windows_command_uses(command, root):
    count = ctypes.c_int()
    parse = ctypes.windll.shell32.CommandLineToArgvW
    parse.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    parse.restype = ctypes.POINTER(ctypes.c_wchar_p)
    arguments = parse(command, ctypes.byref(count))
    if not arguments:
        fail('Cannot parse a running Java command line')
    try:
        # Resolve short names, junctions and dot segments before comparing paths.
        for index in range(count.value):
            for value in arguments[index].split('=', 1)[-1].split(';'):
                if Path(value).is_absolute() and inside(value, root):
                    return True
        return False
    finally:
        free = ctypes.windll.kernel32.LocalFree
        free.argtypes = [ctypes.c_void_p]
        free.restype = ctypes.c_void_p
        free(arguments)


def preflight(root, target, operation='update'):
    root = resolve_path(root)
    game = root / '.minecraft' if target == 'client' else root
    if root == root.parent or root == resolve_path(Path.home()) or not root.is_dir():
        fail(f'Not an existing GTNH {target} instance: {root}')
    if operation != 'rollback' and (not (game/'mods').is_dir() or not (game/'config').is_dir()):
        fail(f'Missing mods/config in {root}')
    if operation != 'rollback' and target == 'client' and not (root/'mmc-pack.json').is_file():
        fail(f'Prism mmc-pack.json missing: {root}')
    if os.name == 'nt':
        script = '[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-WmiObject Win32_Process | Where-Object {$_.Name -match "^javaw?\\.exe$"} | ForEach-Object {[Console]::WriteLine([string]$_.ProcessId+[char]9+[string]$_.CommandLine)}'
        result = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        if result.returncode:
            fail('Cannot inspect running Java processes; close the game/server first')
        for line in result.stdout.decode('utf-8-sig', errors='replace').splitlines():
            pid, _, command = line.partition('\t')
            normalized = command.replace('/', '\\').lower()
            jar = re.search(r'-jar\s+"?([^"\s]+)', command)
            if (display(root).lower() in normalized or not command
                    or (jar and not Path(jar[1]).is_absolute()) or windows_command_uses(command, root)):
                fail(f'Java process {pid} may be using {root}; stop the game/server first')
        return
    for process in Path('/proc').glob('[0-9]*'):
        try:
            if not (process/'comm').read_text().strip().startswith('java'):
                continue
            executable = (process/'exe').resolve().name
            if not executable.startswith('java'):
                continue
            cwd = (process/'cwd').resolve()
            arguments = (process/'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
            if inside(cwd, root) or str(root) in arguments:
                fail(f'Java process {process.name} is using {root}; stop the game/server first')
        except (FileNotFoundError, ProcessLookupError):
            continue
        except PermissionError:
            fail(f'Cannot inspect Java process {process.name}; cannot establish that the instance is stopped')


def unpack_zip(archive, destination):
    destination = fs_path(destination)
    with zipfile.ZipFile(fs_path(archive)) as pack:
        names = set()
        for entry in pack.infolist():
            name = entry.filename
            contained(destination, name)
            if "\\" in name or stat.S_ISLNK(entry.external_attr >> 16):
                fail(f'Unsafe ZIP entry: {name}')
            for part in PurePosixPath(name).parts:
                if part.endswith((' ', '.')) or re.match(r'^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)', part, re.I):
                    fail(f'Unsafe Windows ZIP name: {name}')
            key = name.rstrip('/').casefold()
            if key in names:
                fail(f'Duplicate ZIP entry: {name}')
            names.add(key)
        size = sum(entry.file_size for entry in pack.infolist())
        if size * 2 > shutil.disk_usage(destination.parent).free:
            fail('Insufficient disk space to extract and stage the archive')
        pack.extractall(destination)


def extract(archive, destination, target):
    destination = fs_path(destination)
    unpack_zip(archive, destination)
    candidates = [p.parent for p in destination.rglob('mods')
                  if p.is_dir() and (p.parent/'config').is_dir()]
    if target == 'client':
        candidates = [p.parent for p in candidates if p.name == '.minecraft' and (p.parent/'mmc-pack.json').is_file()]
    if len(candidates) != 1:
        fail(f'Expected one {target} pack root; found {len(candidates)}')
    return candidates[0]


def jar_ids(path):
    with zipfile.ZipFile(fs_path(path)) as jar:
        if jar.testzip():
            fail(f'Corrupt JAR: {path}')
        text = jar.read('mcmod.info').decode(errors='replace') if 'mcmod.info' in jar.namelist() else ''
        return set(re.findall(r'"modid"\s*:\s*"([^"$]+)"', text, re.I))


def verify(root, target, java):
    root = fs_path(root)
    game = root/'.minecraft' if target == 'client' else root
    jars = sorted((game/'mods').rglob('*.jar'))
    if len(jars) < 150:
        fail(f'Incomplete GTNH pack: {len(jars)} mods')
    seen = {}
    for jar in jars:
        for modid in jar_ids(jar):
            if modid.lower() in seen:
                fail(f'Duplicate mod ID {modid}: {seen[modid.lower()]} and {jar.name}')
            seen[modid.lower()] = jar.name
    if 'gregtech' not in seen and not any(re.search(r'gregtech|gt5', p.name, re.I) for p in jars):
        fail('GregTech is required')
    if not (game/'config').is_dir() or not any((game/'config').iterdir()):
        fail('Config directory is empty')
    if target == 'client':
        metadata = read_json(root/'mmc-pack.json')
        if not metadata.get('components'):
            fail('Prism component list is empty')
    if java == 'java17':
        if target == 'client':
            if not (root/'libraries').is_dir() or not (root/'patches').is_dir():
                fail('Prism libraries/patches are missing')
            patches = list((root/'libraries').glob('*forgePatches.jar'))
            if not patches:
                fail('Prism forgePatches JAR is missing')
            for patch in patches:
                jar_ids(patch)
        else:
            jar_ids(root/'lwjgl3ify-forgePatches.jar')
            if not (root/'java9args.txt').is_file():
                fail('Server java9args.txt is missing')
    elif target == 'server':
        forge = list(root.glob('forge-*.jar'))
        minecraft = list(root.glob('minecraft_server*.jar'))
        if not forge or not minecraft:
            fail('Java 8 server Forge/Minecraft launcher JARs are missing')
        for jar in forge+ minecraft:
            jar_ids(jar)
    print(f'Verified: {len(jars)} JARs; CRC, mod IDs and launcher files OK')


def patch_config(root, patch):
    file = contained(root, patch['FilePath'])
    text = file.read_text(encoding='utf-8-sig')
    key = patch['Key']
    section = patch.get('Section', '')
    stack, matches = [], []
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        cleaned = line.strip()
        if cleaned.startswith(('#', '//')):
            continue
        block = re.match(r'^\s*"?([^"{}]+?)"?\s*\{\s*$', line)
        if block:
            stack.append(block.group(1).strip())
        elif cleaned == '}':
            if stack:
                stack.pop()
        if (not section or section in stack or '.'.join(stack) == section) and re.match(r'^\s*'+re.escape(key)+r'\s*=', line):
            matches.append(index)
    if len(matches) != 1:
        fail(f'Patch requires exactly one key: {patch["FilePath"]}: {section}/{key}; found {len(matches)}')
    index = matches[0]
    indent = re.match(r'^\s*', lines[index]).group()
    ending = '\r\n' if lines[index].endswith('\r\n') else '\n'
    value = patch['Value']
    if isinstance(value, bool):
        value = str(value).lower()
    if not isinstance(value, (str, int, float)) or '\n' in str(value) or '\r' in str(value):
        fail(f'Patch value must fit on one line: {key}')
    lines[index] = f'{indent}{key}={value}{ending}'
    file.write_text(''.join(lines), encoding='utf-8')


def prepare(old, payload, stage, target, config_file, release_file, java):
    old, payload, stage = map(fs_path, (old, payload, stage))
    config, release = read_json(config_file), read_json(release_file)
    prefix = '.minecraft/' if target == 'client' else ''
    old_game, new_game = old/prefix, stage/prefix
    managed = [prefix+p for p in ('mods', 'config', 'resources', 'scripts')]
    if target == 'client':
        managed += ['libraries', 'patches', 'mmc-pack.json']
    else:
        managed += ['libraries', 'java9args.txt', 'lwjgl3ify-forgePatches.jar']
        for base in (old, payload):
            managed += [p.name for pattern in ('forge-*.jar', 'minecraft_server*.jar', 'startserver*.sh', 'startserver*.bat') for p in base.glob(pattern)]
    for relative in sorted(set(managed)):
        source = payload/relative
        if source.exists():
            copy(source, stage/relative)
            if relative.endswith('.sh'):
                (stage/relative).chmod((stage/relative).stat().st_mode | 0o111)
    preserved = ['config/JourneyMapServer', 'config/journeymap', 'config/NEI', 'config/shaders.properties', 'config/vendingmachine']
    for relative in preserved:
        source = contained(old_game, relative)
        if source.exists():
            copy(source, contained(new_game, relative))
    # Keep the operator's Java/memory flags; java9args.txt still comes from the new pack.
    if target == 'server':
        for source in old.glob('startserver*'):
            if source.name in managed and source.is_file():
                copy(source, stage/source.name)
    for field, override in [('Custom', False), ('Override', True)]:
        names = config.get(f'{field}{target.title()}Mods', []) or []
        for name in names:
            source = contained(old_game/'mods', name)
            if not source.is_file():
                fail(f'Configured {field.lower()} mod is missing: {source}')
            source_ids = jar_ids(source)
            for jar in list((new_game/'mods').rglob('*.jar')):
                if jar.name == source.name or source_ids & jar_ids(jar):
                    if not override:
                        fail(f'Custom mod conflicts with pack: {source.name}; mark it as an override')
                    jar.unlink()
            copy(source, contained(new_game/'mods', name))
    for patch in config.get('ConfigPatches', []) or []:
        if patch.get('Target', 'both') in (target, 'both'):
            patch_config(new_game, patch)
    verify(stage, target, java)
    release['installed_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
    write_json(new_game/'.gtnh-updater-state.json', release)
    write_json(new_game/'.gtnh-build.json', release)
    managed += [prefix+p for p in ('.gtnh-updater-state.json', '.gtnh-bash-state.json', '.gtnh-build.json', '.gtnh-nightly-state.json', '.gtnh-config-baseline.zip')]
    changes = []
    for relative in sorted(set(managed)):
        path = contained(old, relative)
        if path.is_symlink():
            fail(f'Managed path is a symlink: {path}')
        changes.append((int(path.exists()), relative))
    current_jars = {str(p.relative_to(old_game/'mods')): p for p in (old_game/'mods').rglob('*.jar')}
    new_jars = {str(p.relative_to(new_game/'mods')): p for p in (new_game/'mods').rglob('*.jar')}
    removed = sorted(current_jars.keys()-new_jars.keys())
    added = sorted(new_jars.keys()-current_jars.keys())
    changed = sorted(n for n in current_jars.keys() & new_jars.keys()
                     if hashlib.sha256(current_jars[n].read_bytes()).digest() != hashlib.sha256(new_jars[n].read_bytes()).digest())
    print(f'{target.upper()}: {installed(old_game)} -> {release["release"]}')
    print(f'Mods: +{len(added)} -{len(removed)} changed in place: {len(changed)}')
    for symbol, names in [('-', removed), ('+', added), ('~', changed)]:
        for name in names:
            print(f'  {symbol} {name}')
    return [{'existed':bool(existed), 'path':relative} for existed, relative in changes]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links += [v for k,v in attrs if k == 'href']


def select_release(file, channel, version, target, java):
    if channel == 'daily':
        releases = read_json(file)
        releases = releases if isinstance(releases, list) else [releases]
        for release in releases:
            if release.get('draft') or (version and release['tag_name'] != version):
                continue
            for asset in release.get('assets', []):
                name = asset['name']
                platform = 'server' if target == 'server' else 'mmcprism'
                if re.search(rf'-{platform}-{java}(?:-\d+)?\.zip$', name):
                    digest = asset.get('digest') or ''
                    return {'release':release['tag_name'], 'channel':channel,
                                      'url':asset['browser_download_url'], 'archive':name,
                                      'sha256':digest[7:] if digest.startswith('sha256:') else '',
                                      'source':release['html_url'], 'target':target, 'java':java}
        fail(f'No matching {target}/{java} daily archive')
    parser = Links()
    parser.feed(fs_path(file).read_text())
    candidates = []
    for link in parser.links:
        name = Path(link).name
        match = re.fullmatch(r'GT_New_Horizons_(\d+\.\d+\.\d+(?:[-_][\w-]+)?)_(Server_)?Java_(8|17)(?:-\d+)?\.zip', name)
        if not match or ('ServerPacks/' in link) != (target == 'server'):
            continue
        found = match.group(1)
        if ('java'+match.group(3)) != java or (version and found.lower() != version.lower()):
            continue
        if not version and not re.fullmatch(r'\d+\.\d+\.\d+', found):
            continue
        if target == 'client' and 'Multi_mc_downloads/' not in link:
            continue
        if not link.startswith('https://downloads.gtnewhorizons.com/'):
            fail('Unexpected download host in version history')
        candidates.append({'release':found, 'channel':channel, 'url':html.unescape(link), 'archive':name,
                           'sha256':'', 'source':'https://www.gtnewhorizons.com/version-history/', 'target':target, 'java':java})
    if not candidates:
        fail(f'No matching stable/beta {version or "latest"} archive')
    return candidates[0]


def downgrade(current, wanted):
    if current == 'unknown' or current == wanted:
        return False
    def date(value):
        return re.search(r'(\d{4}-\d{2}-\d{2})(?:\+(\d+))?', value)
    before, after = date(current), date(wanted)
    if before and after:
        return (after[1], int(after[2] or 0)) < (before[1], int(before[2] or 0))
    if before and not after:
        return True  # Release cuts cannot be ordered safely against a daily build.
    if not before and after:
        return False
    def semver(value):
        match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)(?:[-_](alpha|beta|rc)[-_]?(\d+))?', value, re.I)
        if not match:
            fail(f'Cannot order version: {value}')
        return tuple(map(int, match.group(1,2,3))) + ({'alpha':0,'beta':1,'rc':2,None:3}[match[4].lower() if match[4] else None], int(match[5] or 0))
    return semver(wanted) < semver(current)


