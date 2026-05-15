# Transfection

Extract this archive and run the appropriate install script for your platform.

## Windows (PowerShell)

```powershell
./install.ps1
```

## macOS / Linux (Bash)

```bash
bash install.sh
```

After installation, run:

Windows:

```
.uv/uv.exe run transfection slide/segment/timeseries/auc/fit/plot-timeseries/plot-auc/plot-fit ...
```

Linux / macOS:

```
.uv/uv run transfection slide/segment/timeseries/auc/fit/plot-timeseries/plot-auc/plot-fit ...
```

Generate masks before timeseries:

```
.uv/uv run transfection segment WORKSPACE --sample WORKSPACE/slide.json
```

The normal analysis order is:

```
segment -> timeseries -> plot-timeseries -> auc -> plot-auc -> fit -> plot-fit
```

Optional pipelines (Windows PowerShell, from the same directory as `install.ps1`):

```powershell
./transfection-analyze.ps1
./transfection-slide.ps1
```

Optional pipelines (after `bash install.sh`, from the same directory):

```bash
chmod +x transfection-analyze.sh transfection-slide.sh
./transfection-analyze.sh
./transfection-slide.sh
```

From a git clone (repo root), run the same helper scripts from the repository root (next to `pyproject.toml`).
