param(
    [string]$Python = "3.11",
    [string]$EnvironmentPath = ".venv-model"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$environment = Join-Path $root $EnvironmentPath
$uvCache = Join-Path $root "data\local\uv-cache"
$env:UV_CACHE_DIR = $uvCache

Set-Location $root
if (-not (Test-Path -LiteralPath (Join-Path $environment "Scripts\python.exe"))) {
    uv venv $environment --python $Python
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the local-model Python environment"
    }
}

$modelPython = Join-Path $environment "Scripts\python.exe"

# RTX 50-series/Blackwell support requires a recent CUDA build. Keep this
# explicit instead of allowing a generic requirements install to choose CPU.
uv pip install --python $modelPython torch==2.12.1 `
    --index-url https://download.pytorch.org/whl/cu130
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install the pinned CUDA PyTorch runtime"
}

uv pip install --python $modelPython -r requirements-model.txt
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install local-model dependencies"
}

& $modelPython -c "import torch, transformers, peft, bitsandbytes; print({'torch': torch.__version__, 'cuda': torch.version.cuda, 'cuda_available': torch.cuda.is_available(), 'transformers': transformers.__version__, 'peft': peft.__version__, 'bitsandbytes': bitsandbytes.__version__})"
if ($LASTEXITCODE -ne 0) {
    throw "Local-model runtime import verification failed"
}
