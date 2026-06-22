$ErrorActionPreference = "Stop"

$ProjectRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$AppName = "NOXLAB SEWIZARD"
$VenvDir = Join-Path $ProjectRoot ".venv"
$Requirements = Join-Path $ProjectRoot "requirements.txt"
$Launcher = Join-Path $ProjectRoot "NOXLAB_SEWIZARD.pyw"
$IconPath = Join-Path $ProjectRoot "assets\noxlab_sewizard_wand.ico"
$PythonInstallerUrl = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Red
}

function Test-SupportedPython {
    param(
        [string]$Command,
        [string[]]$Arguments
    )

    try {
        $output = & $Command @Arguments -c "import sys; print(sys.executable); raise SystemExit(0 if sys.version_info >= (3, 10) and sys.version_info < (3, 14) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $output) {
            return [string]$output[-1]
        }
    }
    catch {
        return $null
    }
    return $null
}

function Find-SupportedPython {
    $candidates = @(
        @{ Command = "py"; Arguments = @("-3.12") },
        @{ Command = "py"; Arguments = @("-3.11") },
        @{ Command = "py"; Arguments = @("-3.10") },
        @{ Command = "python"; Arguments = @() }
    )

    foreach ($candidate in $candidates) {
        $python = Test-SupportedPython -Command $candidate.Command -Arguments $candidate.Arguments
        if ($python) {
            return @{
                Command = $candidate.Command
                Arguments = $candidate.Arguments
                Exe = $python
            }
        }
    }
    return $null
}

function Install-UserPython {
    Write-Step "Downloading Python 3.12 for this user"
    $installer = Join-Path $env:TEMP "python-3.12.10-amd64.exe"
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $PythonInstallerUrl -OutFile $installer

    Write-Step "Installing Python 3.12"
    $args = "/quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0 Shortcuts=0"
    Start-Process -FilePath $installer -ArgumentList $args -Wait

    $python = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
    if (-not (Test-Path -LiteralPath $python)) {
        throw "Python installed, but python.exe was not found at $python"
    }
    return @{
        Command = $python
        Arguments = @()
        Exe = $python
    }
}

function New-AppShortcut {
    param(
        [string]$ShortcutPath,
        [string]$TargetPath,
        [string]$Arguments,
        [string]$WorkingDirectory,
        [string]$IconLocation
    )

    if (Test-Path -LiteralPath $ShortcutPath) {
        Remove-Item -LiteralPath $ShortcutPath -Force
    }

    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($ShortcutPath)
    $shortcut.TargetPath = $TargetPath
    $shortcut.Arguments = $Arguments
    $shortcut.WorkingDirectory = $WorkingDirectory
    $shortcut.IconLocation = "$IconLocation,0"
    $shortcut.Description = "Launch NOXLAB SEWIZARD"
    $shortcut.Save()
}

Write-Step "Preparing NOXLAB SEWIZARD setup"

$pythonInfo = Find-SupportedPython
if (-not $pythonInfo) {
    $pythonInfo = Install-UserPython
}

Write-Step "Creating local virtual environment"
if (-not (Test-Path -LiteralPath $VenvDir)) {
    & $pythonInfo.Command @($pythonInfo.Arguments) -m venv $VenvDir
}

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPythonw = Join-Path $VenvDir "Scripts\pythonw.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "Virtual environment Python was not found at $VenvPython"
}
if (-not (Test-Path -LiteralPath $VenvPythonw)) {
    throw "Virtual environment pythonw.exe was not found at $VenvPythonw"
}

Write-Step "Installing required packages"
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r $Requirements

Write-Step "Checking NOXLAB icon"
if (-not (Test-Path -LiteralPath $IconPath)) {
    throw "Shortcut icon was not found at $IconPath"
}

Write-Step "Creating backup folder"
New-Item -ItemType Directory -Force (Join-Path $ProjectRoot "backups") | Out-Null

Write-Step "Creating app shortcuts"
$Desktop = [Environment]::GetFolderPath("Desktop")
$DesktopShortcut = Join-Path $Desktop "$AppName.lnk"
$FolderShortcut = Join-Path $ProjectRoot "$AppName.lnk"
$ShortcutArgs = "`"$Launcher`""

New-AppShortcut -ShortcutPath $DesktopShortcut -TargetPath $VenvPythonw -Arguments $ShortcutArgs -WorkingDirectory $ProjectRoot -IconLocation $IconPath
New-AppShortcut -ShortcutPath $FolderShortcut -TargetPath $VenvPythonw -Arguments $ShortcutArgs -WorkingDirectory $ProjectRoot -IconLocation $IconPath

Write-Host ""
Write-Host "NOXLAB SEWIZARD setup complete." -ForegroundColor Green
Write-Host "Desktop shortcut: $DesktopShortcut"
Write-Host "Folder shortcut:  $FolderShortcut"
Write-Host "The app shortcut launches with pythonw.exe, so it opens as a window without a command prompt."
