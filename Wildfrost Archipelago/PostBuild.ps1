param(
    [Parameter(Mandatory)] [string]$SolutionDir,
    [Parameter(Mandatory)] [string]$TargetPath,
    [Parameter(Mandatory)] [string]$IconPath,
    [Parameter(Mandatory)] [string]$LibDir,
    [Parameter(Mandatory)] [string]$ModRoot
)

$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force -Path $ModRoot | Out-Null

# Copy to a temp file and rename it over the old DLL rather than overwriting in place. A running
# game has the old DLL memory-mapped and reads method bodies from it lazily, so rewriting that same
# file makes any not-yet-JIT'd method (typically Harmony prefixes) fail with "BadImageFormatException:
# Method has zero rva". Renaming swaps in a new file and leaves the mapped one intact.
$dllDest = Join-Path $ModRoot (Split-Path $TargetPath -Leaf)
$dllTemp = "$dllDest.tmp"
Copy-Item -Path $TargetPath -Destination $dllTemp -Force
Move-Item -Path $dllTemp -Destination $dllDest -Force

Copy-Item -Path $IconPath -Destination $ModRoot -Force

# Runtime dependencies (Archipelago.MultiClient.Net). The game's mod Bootstrap resolves a mod's
# references by assembly name from the DLLs sitting in mod folders, so they just ride along here.
Get-ChildItem -Path $LibDir -Filter *.dll | ForEach-Object {
    $libDest = Join-Path $ModRoot $_.Name
    Copy-Item -Path $_.FullName -Destination "$libDest.tmp" -Force
    Move-Item -Path "$libDest.tmp" -Destination $libDest -Force
}

# The notices for what the mod ships that isn't this project's own (the client library, the icon's
# artwork), so they travel with the files they cover.
Copy-Item -Path (Join-Path $SolutionDir "NOTICE.md") -Destination $ModRoot -Force
$licensesDest = Join-Path $ModRoot "licenses"
New-Item -ItemType Directory -Force -Path $licensesDest | Out-Null
Copy-Item -Path (Join-Path $SolutionDir "licenses/*") -Destination $licensesDest -Force

# Mirrors the whole solution (.sln plus the project folder) into the mod's Source
# subfolder so it always matches what was just built, without bin/obj/.vs churn or
# stale files left over from earlier ad-hoc copies.
$sourceDest = Join-Path $ModRoot "Source"
# dist is left out because its .apworld is copied to the mod root below.
$excludedDirectories = @("bin", "obj", ".vs", ".git", "dist")
if (Test-Path $sourceDest) {
    Remove-Item $sourceDest -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $sourceDest | Out-Null
Get-ChildItem -Path $SolutionDir -Force | Where-Object {
    $_.Name -notin $excludedDirectories
} | Copy-Item -Destination $sourceDest -Recurse -Force
if (-not (Test-Path $sourceDest)) {
    throw "Failed to mirror source to $sourceDest"
}
# The project's own bin/obj sit one level down, so the excluded names (and Python caches) are
# removed at every depth too.
Get-ChildItem -Path $sourceDest -Recurse -Directory -Force |
    Where-Object { $_.Name -in ($excludedDirectories + "__pycache__") } |
    Sort-Object { $_.FullName.Length } -Descending |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# The apworld ships with the mod, so players who get the mod have what they need to generate.
Get-ChildItem -Path (Join-Path $SolutionDir "dist") -Filter *.apworld -ErrorAction SilentlyContinue | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination $ModRoot -Force
}
