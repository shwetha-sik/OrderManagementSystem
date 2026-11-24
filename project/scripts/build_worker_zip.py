"""
Build the SQS worker ZIP for the selected Lambda Python runtime/architecture.
Examples:
  $env:LAMBDA_PYTHON_VERSION="3.13"
  $env:LAMBDA_ARCH="x86_64"
  python scripts/build_worker_zip.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
RUNTIME = os.getenv("LAMBDA_PYTHON_VERSION", "3.13")
ARCH = os.getenv("LAMBDA_ARCH", "x86_64").lower()
ABIS = {"3.12": "cp312", "3.13": "cp313", "3.14": "cp314"}
PLATFORMS = {"x86_64": "manylinux2014_x86_64", "arm64": "manylinux2014_aarch64"}

if RUNTIME not in ABIS:
    raise SystemExit("LAMBDA_PYTHON_VERSION must be 3.12, 3.13 or 3.14.")
if ARCH not in PLATFORMS:
    raise SystemExit("LAMBDA_ARCH must be x86_64 or arm64.")

out_dir = BASE / "dist"
out_dir.mkdir(exist_ok=True)
out_file = out_dir / f"worker_lambda_py{RUNTIME}_{ARCH}.zip"

with tempfile.TemporaryDirectory(prefix="lambda-worker-build-") as temp:
    staging = Path(temp)
    cmd = [
        sys.executable, "-m", "pip", "install",
        "--disable-pip-version-check", "--upgrade", "--only-binary=:all:",
        "--platform", PLATFORMS[ARCH], "--implementation", "cp",
        "--python-version", RUNTIME, "--abi", ABIS[RUNTIME],
        "--target", str(staging), "-r", str(BASE / "requirements-worker.txt"),
    ]
    print("Installing Lambda-targeted worker dependencies:", " ".join(cmd))
    subprocess.check_call(cmd)

    shutil.copy2(BASE / "worker.py", staging / "worker.py")
    (staging / "app").mkdir(exist_ok=True)
    shutil.copy2(BASE / "app" / "store.py", staging / "app" / "store.py")
    (staging / "app" / "__init__.py").write_text("")

    metadata = {
        "runtime": f"python{RUNTIME}",
        "architecture": ARCH,
        "platform": PLATFORMS[ARCH],
        "handler": "worker.handler",
        "dependencies_file": "requirements-worker.txt",
    }
    (staging / "BUILD_INFO.json").write_text(json.dumps(metadata, indent=2))

    if out_file.exists():
        out_file.unlink()
    with zipfile.ZipFile(out_file, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(staging).as_posix())

print(f"\nCreated: {out_file}")
print(f"Target: Python {RUNTIME} / {ARCH}")
