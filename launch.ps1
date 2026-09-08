param(
    [switch]$CheckOnly,
    [switch]$InstallOnly,
    [switch]$Offline,
    [switch]$Headless,
    [ValidateRange(1024,65535)][int]$Port = 8501,
    [string]$PythonExecutable = ''
)
$ErrorActionPreference = 'Stop'
$projectRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$environmentPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
Set-Location -LiteralPath $projectRoot
function Invoke-CheckedPython {
    param([string]$Executable, [string[]]$Arguments, [string]$Failure)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw $Failure }
}
try {
    foreach ($requiredFile in @('pyproject.toml','constraints.txt','app.py')) {
        if (-not (Test-Path -LiteralPath (Join-Path $projectRoot $requiredFile))) { throw "Missing $requiredFile. Extract the complete project ZIP first." }
    }
    $hashProvider = [System.Security.Cryptography.SHA256]::Create()
    try {
        $projectDigest = [BitConverter]::ToString($hashProvider.ComputeHash([System.IO.File]::ReadAllBytes((Join-Path $projectRoot 'pyproject.toml')))).Replace('-','')
        $constraintsDigest = [BitConverter]::ToString($hashProvider.ComputeHash([System.IO.File]::ReadAllBytes((Join-Path $projectRoot 'constraints.txt')))).Replace('-','')
    } finally { $hashProvider.Dispose() }
    $expectedMarker = "$projectDigest/$constraintsDigest"
    $readyFile = Join-Path $projectRoot '.venv\setup-complete.txt'
    if (Test-Path -LiteralPath (Join-Path $projectRoot '.venv')) {
        if (-not (Test-Path -LiteralPath $environmentPython)) {
            throw 'The existing .venv is incomplete. Rename that folder to .venv.previous, then rerun; your input and output files are preserved.'
        }
        Invoke-CheckedPython -Executable $environmentPython -Arguments @('-c','import sys; sys.exit(0 if (3,12) <= sys.version_info[:2] < (3,15) else 1)') -Failure 'The existing .venv uses an unsupported or broken Python. Rename it to .venv.previous and rerun.'
    } elseif ($CheckOnly -or $Offline) {
        throw 'No usable project environment exists. Run START_WINDOWS.cmd once while connected to install dependencies.'
    } else {
        $candidateCommand = $null
        $candidateArguments = @()
        $candidates = @()
        if ($PythonExecutable) {
            $candidates += @{Command=$PythonExecutable; Prefix=@()}
        } else {
            foreach ($pythonTag in @('-3.14','-3.13','-3.12','')) {
                $candidates += @{Command='py'; Prefix=@($pythonTag) | Where-Object { $_ -ne '' }}
            }
            $candidates += @{Command='python'; Prefix=@()}
            $candidates += @{Command='python3'; Prefix=@()}
        }
        foreach ($candidate in $candidates) {
            if (Get-Command $candidate.Command -ErrorAction SilentlyContinue) {
                $argsForProbe = @($candidate.Prefix) + @('-c','import sys; sys.exit(0 if (3,12) <= sys.version_info[:2] < (3,15) else 1)')
                $oldPreference = $ErrorActionPreference
                $ErrorActionPreference = 'Continue'
                & $candidate.Command @argsForProbe 2>$null
                $probeExit = $LASTEXITCODE
                $ErrorActionPreference = $oldPreference
                if ($probeExit -eq 0) {
                    $candidateCommand = $candidate.Command
                    $candidateArguments = @($candidate.Prefix)
                    break
                }
            }
        }
        if (-not $candidateCommand) {
            throw 'Python 3.12 through 3.14 was not found. Install from https://www.python.org/downloads/ and rerun START_WINDOWS.cmd. No system setting was changed.'
        }
        Write-Host 'Creating a project-local Python environment. First installation needs internet access.'
        Invoke-CheckedPython -Executable $candidateCommand -Arguments ($candidateArguments + @('-m','venv',(Join-Path $projectRoot '.venv'))) -Failure 'Could not create .venv. Check available disk space and write access to this project folder.'
    }
    $installedMarker = if (Test-Path -LiteralPath $readyFile) { (Get-Content -LiteralPath $readyFile -Raw).Trim() } else { '' }
    if ($installedMarker -ne $expectedMarker) {
        if ($Offline -or $CheckOnly) {
            throw 'Installation is incomplete or requirements changed. Run the launcher online once; the previous setup marker is not sufficient.'
        }
        Invoke-CheckedPython -Executable $environmentPython -Arguments @('-m','pip','install','-c','constraints.txt','-e','.') -Failure 'Dependency installation failed or was interrupted. Check your connection and rerun; no completion marker was written.'
    }
    Invoke-CheckedPython -Executable $environmentPython -Arguments @('-m','pip','check') -Failure 'Installed dependencies conflict. Re-run installation in a fresh .venv; do not use this environment for analysis.'
    Invoke-CheckedPython -Executable $environmentPython -Arguments @('-c','import calibshift, streamlit, numpy, pandas, scipy; from calibshift.cli import example_path; assert example_path().is_file(); print(calibshift.__version__)') -Failure 'A required library or packaged example is missing. Rename .venv to .venv.previous and rerun online.'
    Set-Content -LiteralPath $readyFile -Value $expectedMarker -Encoding ascii
    if ($CheckOnly -or $InstallOnly) {
        Write-Output 'PASS: Python, installed dependencies and packaged example resources were checked. No browser analysis was performed.'
        exit 0
    }
    $portProbe = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback,$Port)
    try { $portProbe.Start() } catch { throw "Port $Port is already in use. Stop the other app or run launch.ps1 -Port 8502 (choose a free port)." } finally { $portProbe.Stop() }
    Write-Host "Opening http://127.0.0.1:$Port . Keep this window open; press Ctrl+C to stop."
    $headlessValue = if ($Headless) { 'true' } else { 'false' }
    & $environmentPython -m streamlit run app.py --server.address=127.0.0.1 --server.port=$Port --server.headless=$headlessValue --browser.gatherUsageStats=false
    exit $LASTEXITCODE
} catch {
    Write-Host ('Setup problem: ' + $_.Exception.Message)
    exit 1
}
