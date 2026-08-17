param(
    [Parameter(Mandatory = $true)] [string]$Deck,
    [string]$OutputDir = "rendered",
    [string]$Image = "xiaopu-ppt-render:mini"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$deckPath = (Resolve-Path (Join-Path $root $Deck)).Path
$deckDir = Split-Path $deckPath -Parent
$deckName = [IO.Path]::GetFileNameWithoutExtension($deckPath)
$outPath = Join-Path $deckDir $OutputDir
New-Item -ItemType Directory -Force $outPath | Out-Null

docker run --rm -v "${deckDir}:/work" -w /work --entrypoint soffice $Image `
    --headless --convert-to pdf --outdir "/work/$OutputDir" "/work/$([IO.Path]::GetFileName($deckPath))"
docker run --rm -v "${deckDir}:/work" -w /work --entrypoint pdftoppm $Image `
    -png -r 120 "/work/$OutputDir/$deckName.pdf" "/work/$OutputDir/slide"

Get-ChildItem $outPath -File | Select-Object Name, Length
