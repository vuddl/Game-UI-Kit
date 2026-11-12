"""Discover local Photoshop installs and run JSX in the explicitly selected executable."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


DISCOVER = r"""
$paths = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
function Add-Photoshop($value) {
    if (-not $value) { return }
    $value = [Environment]::ExpandEnvironmentVariables(([string]$value).Trim('"'))
    if (Test-Path -LiteralPath $value -PathType Container) { $value = Join-Path $value 'Photoshop.exe' }
    if ((Split-Path $value -Leaf) -ieq 'Photoshop.exe' -and (Test-Path -LiteralPath $value -PathType Leaf)) {
        [void]$paths.Add((Get-Item -LiteralPath $value).FullName)
    }
}
Get-Process Photoshop -ErrorAction SilentlyContinue | ForEach-Object { Add-Photoshop $_.Path }
foreach ($hive in @([Microsoft.Win32.RegistryHive]::LocalMachine, [Microsoft.Win32.RegistryHive]::CurrentUser)) {
    foreach ($view in @([Microsoft.Win32.RegistryView]::Registry64, [Microsoft.Win32.RegistryView]::Registry32)) {
        $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey($hive, $view)
        $key = $base.OpenSubKey('SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Photoshop.exe')
        if ($key) { Add-Photoshop $key.GetValue(''); $key.Dispose() }
        $key = $base.OpenSubKey('SOFTWARE\Adobe\Photoshop')
        if ($key) {
            foreach ($name in $key.GetSubKeyNames()) {
                $sub = $key.OpenSubKey($name)
                if ($sub) { Add-Photoshop $sub.GetValue('ApplicationPath'); $sub.Dispose() }
            }
            $key.Dispose()
        }
        $key = $base.OpenSubKey('SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall')
        if ($key) {
            foreach ($name in $key.GetSubKeyNames()) {
                $sub = $key.OpenSubKey($name)
                if (-not $sub) { continue }
                if ($sub.GetValue('DisplayName') -match 'Photoshop') {
                    Add-Photoshop $sub.GetValue('InstallLocation')
                    $icon = [string]$sub.GetValue('DisplayIcon')
                    Add-Photoshop ($icon -replace ',\s*-?\d+$', '')
                }
                $sub.Dispose()
            }
            $key.Dispose()
        }
        $base.Dispose()
    }
}
$roots = @($env:ProgramFiles, ${env:ProgramFiles(x86)}, "$env:LOCALAPPDATA\Programs")
Get-PSDrive -PSProvider FileSystem | ForEach-Object {
    foreach ($folder in @('Program Files', 'Program Files (x86)', 'Adobe')) { $roots += Join-Path $_.Root $folder }
}
foreach ($root in ($roots | Select-Object -Unique)) {
    if (-not $root -or -not (Test-Path -LiteralPath $root -PathType Container)) { continue }
    foreach ($parent in @($root, (Join-Path $root 'Adobe'))) {
        Get-ChildItem -LiteralPath $parent -Directory -ErrorAction SilentlyContinue |
            Where-Object Name -Match 'Photoshop' | ForEach-Object { Add-Photoshop $_.FullName }
    }
}
$shell = New-Object -ComObject WScript.Shell
foreach ($folder in @("$env:APPDATA\Microsoft\Windows\Start Menu", "$env:ProgramData\Microsoft\Windows\Start Menu",
                       [Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('CommonDesktopDirectory'))) {
    Get-ChildItem -LiteralPath $folder -Filter '*.lnk' -Recurse -ErrorAction SilentlyContinue |
        ForEach-Object { Add-Photoshop ($shell.CreateShortcut($_.FullName).TargetPath) }
}
@($paths | ForEach-Object { Get-PhotoshopDetails $_ }) | ConvertTo-Json -Depth 3 -Compress
"""

DETAILS = r"""
function Get-PhotoshopDetails($path) {
    $file = Get-Item -LiteralPath $path -ErrorAction SilentlyContinue
    if ($file -and $file.Name -ieq 'Photoshop.exe' -and $file.VersionInfo.ProductName -match 'Photoshop') {
        [PSCustomObject]@{path=$file.FullName; label=$file.Directory.Name; version=$file.VersionInfo.ProductVersion; product_name=$file.VersionInfo.ProductName}
    }
}
"""


def powershell_json(script: str, env=None):
    done = subprocess.run(
        ['powershell', '-NoProfile', '-NonInteractive', '-Command',
         "[Console]::OutputEncoding=[Text.Encoding]::UTF8;" + DETAILS + script],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), env=env)
    if done.returncode:
        raise OSError(done.stderr.strip() or 'Không đọc được thông tin Photoshop trên máy.')
    return json.loads(done.stdout.strip()) if done.stdout.strip() else None


def discover_photoshop() -> list[dict]:
    if sys.platform != 'win32':
        return []
    found = powershell_json(DISCOVER) or []
    if isinstance(found, dict):
        found = [found]
    unique = {os.path.normcase(str(Path(item['path']).resolve())): item for item in found}
    return sorted(unique.values(), key=lambda item: (item['label'].casefold(), item['path'].casefold()))


def inspect_photoshop(path: str) -> dict:
    if sys.platform != 'win32':
        raise ValueError('Chọn Photoshop hiện chỉ được hỗ trợ trên Windows.')
    exe = Path(path).expanduser()
    if not exe.is_absolute() or exe.name.lower() != 'photoshop.exe' or not exe.is_file():
        raise ValueError('Chọn đường dẫn đầy đủ tới Photoshop.exe đang có trên máy.')
    try:
        info = powershell_json('Get-PhotoshopDetails $env:GUI_PHOTOSHOP_EXE | ConvertTo-Json -Compress',
                               env={**os.environ, 'GUI_PHOTOSHOP_EXE': str(exe.resolve())})
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f'Không kiểm tra được bản Photoshop đã chọn: {exc}') from exc
    if not info:
        raise ValueError('File đã chọn không có thông tin sản phẩm Photoshop hợp lệ.')
    return info


def script_config_path(selected: dict) -> Path:
    """Resolve preferences for this selected installation, including before its first launch."""
    appdata = os.environ.get('APPDATA')
    if not appdata:
        raise ValueError('Không tìm thấy APPDATA để cấu hình Photoshop.')
    label = selected.get('label') or Path(selected['path']).parent.name
    if 'beta' in label.casefold():
        folder = 'Adobe Photoshop (Beta)'
    else:
        product = selected.get('product_name') or ''
        year = re.search(r'Adobe Photoshop(?: CC)? (20\d{2})\b', product)
        version = re.match(r'(\d+)\.', selected.get('version') or '')
        if year:
            folder = 'Adobe Photoshop ' + year.group(1)
        elif version and int(version.group(1)) >= 20:
            folder = 'Adobe Photoshop ' + str(int(version.group(1)) + 1999)
        else:
            raise ValueError('Không xác định được thư mục Settings của bản Photoshop đã chọn; chưa chạy script.')
    return Path(appdata) / 'Adobe' / folder / (folder + ' Settings') / 'PSUserConfig.txt'


def disable_script_warning(config: Path) -> bool:
    """Set one flag, preserving other preferences, encoding and an original backup."""
    original = config.read_bytes() if config.exists() else b''
    bom, encoding = b'', 'utf-8'
    for prefix, codec in ((b'\xff\xfe', 'utf-16-le'), (b'\xfe\xff', 'utf-16-be'), (b'\xef\xbb\xbf', 'utf-8')):
        if original.startswith(prefix):
            bom, encoding = prefix, codec
            break
    try:
        text = original[len(bom):].decode(encoding)
    except UnicodeDecodeError:
        encoding = 'latin-1'  # preserve arbitrary legacy bytes while editing an ASCII flag
        text = original.decode(encoding)
    updated, count = re.subn(r'(?im)^([ \t]*WarnRunningScripts[ \t]+)\S+', r'\g<1>0', text)
    if not count:
        newline = '\r\n' if '\r\n' in text else '\n'
        updated = text + (newline if text and not text.endswith(('\n', '\r')) else '') + 'WarnRunningScripts 0' + newline
    content = bom + updated.encode(encoding)
    if content == original:
        return False
    config.parent.mkdir(parents=True, exist_ok=True)
    backup = config.with_name(config.name + '.game-ui-kit.bak')
    if config.exists() and not backup.exists():
        shutil.copy2(config, backup)
    pending = None
    try:
        with tempfile.NamedTemporaryFile(dir=config.parent, prefix='ps-config-', delete=False) as stream:
            pending = Path(stream.name)
            stream.write(content)
        os.replace(pending, config)
    finally:
        if pending is not None:
            pending.unlink(missing_ok=True)
    return True


def selected_process_starts(selected: dict) -> list[float]:
    """Check launch times without running JSX or invoking any Photoshop COM server."""
    records = powershell_json(r'''
$processes = @(Get-CimInstance Win32_Process -Filter "Name='Photoshop.exe'" -ErrorAction Stop)
if (@($processes | Where-Object { -not $_.ExecutablePath }).Count) {
    throw 'Không đọc được đường dẫn Photoshop đang chạy. Hãy đóng Photoshop rồi thử lại.'
}
@($processes | Where-Object { $_.ExecutablePath -ieq $env:GUI_PHOTOSHOP_EXE } | ForEach-Object {
    ([DateTimeOffset]$_.CreationDate).ToUnixTimeMilliseconds() / 1000.0
}) | ConvertTo-Json -Compress
''', env={**os.environ, 'GUI_PHOTOSHOP_EXE': str(Path(selected['path']).resolve())})
    return records if isinstance(records, list) else ([records] if records is not None else [])


def prepare_script_preferences(selected: dict) -> dict:
    """Configure before -r, and stop before a warning if a running app needs a restart."""
    try:
        config = script_config_path(selected)
        changed = disable_script_warning(config)
        started = selected_process_starts(selected)
        if any(timestamp < config.stat().st_mtime for timestamp in started):
            return {'ok': False, 'code': 'PHOTOSHOP_RESTART_REQUIRED', 'config': str(config),
                    'error': 'Đã cấu hình tắt cảnh báo script. Lưu công việc rồi đóng và mở lại bản Photoshop đã chọn một lần để áp dụng; chưa gửi script.'}
        return {'ok': True, 'config': str(config), 'changed': changed}
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return {'ok': False, 'code': 'PHOTOSHOP_SCRIPT_CONFIG_FAILED', 'error': str(exc)}


def run_photoshop(jsx: Path, timeout: int, selected: dict) -> dict:
    """Launch this exe only; verify app.path before evaluating any document operations."""
    exe = Path(selected['path']).resolve()
    if not exe.is_file():
        return {'ok': False, 'error': 'Bản Photoshop đã chọn không còn ở đường dẫn đã lưu. Chọn lại trong form export.'}
    preferences = prepare_script_preferences(selected)
    if not preferences['ok']:
        return preferences
    deadline = time.time() + timeout
    with tempfile.TemporaryDirectory(prefix='game-ui-kit-ps-') as temp:
        result_file = Path(temp) / 'result.json'
        wrapper = Path(temp) / 'run.jsx'
        wrapper.write_text(
            'var expected = new Folder(' + json.dumps(exe.parent.as_posix()) + ').fsName.toLowerCase();\n'
            'var output;\ntry {\n'
            'if (app.path.fsName.toLowerCase() !== expected) throw new Error("Wrong Photoshop installation; export stopped");\n'
            'if (new Date().getTime() > ' + str(int(deadline * 1000)) + ') throw new Error("Export request expired");\n'
            'output = $.evalFile(new File(' + json.dumps(jsx.resolve().as_posix()) + '));\n'
            '} catch (err) { output = \'{"ok":false,"error":"\' + String(err).replace(/[\\r\\n"\\\\]/g, " ") + \'"}\'; }\n'
            'var report = new File(' + json.dumps(result_file.as_posix()) + ');\n'
            'report.encoding = "UTF8"; report.open("w"); report.write(output); report.close();\n', encoding='utf-8')
        try:
            subprocess.Popen([str(exe), '-r', str(wrapper)], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            while time.time() < deadline:
                if result_file.exists():
                    try:
                        result = json.loads(result_file.read_text(encoding='utf-8-sig'))
                        if isinstance(result, dict) and isinstance(result.get('ok'), bool):
                            return result
                    except (OSError, ValueError):
                        pass  # the script may still be writing the result
                time.sleep(0.25)
        except OSError as exc:
            return {'ok': False, 'error': str(exc)}
    return {'ok': False, 'error': 'Hết thời gian chờ bản Photoshop đã chọn. Không tự chuyển sang bản khác.'}


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(discover_photoshop(), indent=2, ensure_ascii=False))
