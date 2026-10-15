# Move large local folders (datasets, offline bundle, papers) to an external drive and leave
# junctions behind, so every script keeps using the same relative paths.
# Each folder is copied with robocopy, verified (file count + total bytes), and only then is the
# original removed and replaced by a junction. Re-running skips folders that are already junctions.
# Usage (PowerShell, repo root):  .\scripts\move_to_ssd.ps1 -Dest D:\learning-algo-cvpr
param([string]$Dest = "D:\learning-algo-cvpr")
$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent

# data/ itself stays a real folder because data/README.md is tracked in git; its subfolders move.
$items = @(Get-ChildItem (Join-Path $Repo "data") -Directory | ForEach-Object { "data\" + $_.Name }) + @("wheelhouse", "papers")

function Measure-Tree($path) {
    $files = Get-ChildItem $path -Recurse -File -Force
    [pscustomobject]@{ Count = $files.Count; Bytes = ($files | Measure-Object Length -Sum).Sum }
}

foreach ($rel in $items) {
    $src = Join-Path $Repo $rel
    $dst = Join-Path $Dest $rel
    if ((Get-Item $src -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { "skip  $rel (already a junction)"; continue }
    "copy  $rel -> $dst"
    robocopy $src $dst /E /COPY:DT /DCOPY:T /R:2 /W:5 /MT:16 /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed for $rel (exit $LASTEXITCODE)" }
    $a = Measure-Tree $src; $b = Measure-Tree $dst
    if ($a.Count -ne $b.Count -or $a.Bytes -ne $b.Bytes) { throw "verify failed for ${rel}: $($a.Count)/$($a.Bytes) vs $($b.Count)/$($b.Bytes)" }
    "ok    $rel  $($a.Count) files, $([math]::Round($a.Bytes/1GB,2)) GB verified"
    Remove-Item $src -Recurse -Force
    New-Item -ItemType Junction -Path $src -Target $dst | Out-Null
    "link  $rel -> $dst"
}
"done"
exit 0
