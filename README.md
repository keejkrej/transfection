# Delivery

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
.uv/uv.exe run delivery ...
```

Linux / macOS:
```
.uv/uv run delivery ...
```

Optional pipelines (Windows PowerShell, from the same directory as `install.ps1`):
```powershell
./delivery-expression-analyze.ps1
./delivery-slide-wizard.ps1
```

Optional pipelines (after `bash install.sh`, from the same directory):
```bash
chmod +x delivery-expression-analyze.sh delivery-slide-wizard.sh
./delivery-expression-analyze.sh
./delivery-slide-wizard.sh
```

From a git clone (repo root), you can instead run:
```bash
bash scripts/delivery-expression-analyze.sh
bash scripts/delivery-slide-wizard.sh
```
