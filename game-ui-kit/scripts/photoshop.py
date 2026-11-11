"""Discover local Photoshop installs and run JSX in the explicitly selected executable."""
from __future__ import annotations

import json
import os
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
        [PSCustomObject]@{path=$file.FullName; label=$file.Directory.Name; version=$file.VersionInfo.ProductVersion}
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


def run_photoshop(jsx: Path, timeout: int, selected: dict) -> dict:
    """Launch this exe only; verify app.path before evaluating any document operations."""
    exe = Path(selected['path']).resolve()
    if not exe.is_file():
        return {'ok': False, 'error': 'Bản Photoshop đã chọn không còn ở đường dẫn đã lưu. Chọn lại trong form export.'}
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
