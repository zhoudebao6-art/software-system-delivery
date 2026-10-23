$ErrorActionPreference = 'Stop'
# This entry changes only the invoking PowerShell process.
$env:TEMP='D:\codex+\temp'
$env:TMP=$env:TEMP
$env:TMPDIR=$env:TEMP
$env:PIP_CACHE_DIR='D:\codex+\cache\pip'
$env:UV_CACHE_DIR='D:\codex+\cache\uv'
$env:PYTHONPYCACHEPREFIX='D:\codex+\cache\python-pycache'
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:NPM_CONFIG_CACHE='D:\codex+\cache\npm'
$env:NODE_COMPILE_CACHE='D:\codex+\cache\node-compile-cache'
$env:YARN_CACHE_FOLDER='D:\codex+\cache\yarn'
$env:XDG_CACHE_HOME='D:\codex+\cache'
$env:PLAYWRIGHT_BROWSERS_PATH='D:\codex+\cache\ms-playwright'
$env:SSD_DELIVERY_ROOT='E:\研发自动化\交付成果'
$env:SSD_STAGING_ROOT='E:\研发自动化\.staging'
$env:SSD_WORK_ROOT='E:\研发自动化\work'
foreach($TaskDirectory in @($env:TEMP,$env:PIP_CACHE_DIR,$env:UV_CACHE_DIR,$env:PYTHONPYCACHEPREFIX,$env:NPM_CONFIG_CACHE,$env:NODE_COMPILE_CACHE)) {
  New-Item -ItemType Directory -Path $TaskDirectory -Force | Out-Null
}
$TaskRuntimeRoot=Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies'
if(-not $env:SSD_PYTHON) {
  $TaskPython=Join-Path $TaskRuntimeRoot 'python\python.exe'
  if(Test-Path -LiteralPath $TaskPython -PathType Leaf) { $env:SSD_PYTHON=$TaskPython }
  else { $env:SSD_PYTHON=(Get-Command python -ErrorAction Stop).Source }
}
if(-not $env:SSD_NODE) {
  $TaskNode=Join-Path $TaskRuntimeRoot 'node\bin\node.exe'
  if(Test-Path -LiteralPath $TaskNode -PathType Leaf) { $env:SSD_NODE=$TaskNode }
  else { $env:SSD_NODE=(Get-Command node -ErrorAction Stop).Source }
}
$env:SSD_NODE_MODULES=Join-Path $TaskRuntimeRoot 'node\node_modules'
$TaskLegacyEntry='D:\软通图表\Enter-SoftwareCaseEnvironment.ps1'
$env:SSD_LEGACY_ENTRY_EXISTS=[string](Test-Path -LiteralPath $TaskLegacyEntry -PathType Leaf)
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
