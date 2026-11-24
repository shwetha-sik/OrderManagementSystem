"""
Build a Lambda-compatible ZIP for the FastAPI + Mangum API.

Examples (PowerShell):
  # Match these values to the EXISTING Lambda function's Runtime and Architecture.
  $env:LAMBDA_PYTHON_VERSION="3.13"
  $env:LAMBDA_ARCH="x86_64"
  python scripts/build_lambda_zip.py

Supported targets: Python 3.12/3.13/3.14; x86_64/arm64.
The script downloads Linux wheels for the selected Lambda ABI/architecture,
then verifies that Pydantic Core's compiled extension is present before zipping.
Never upload a ZIP built for a different Python minor version or architecture.
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
PYTHON_ABI = {"3.12": "cp312", "3.13": "cp313", "3.14": "cp314"}
PLATFORM = {"x86_64": "manylinux2014_x86_64", "arm64": "manylinux2014_aarch64"}

if RUNTIME not in PYTHON_ABI:
    raise SystemExit("LAMBDA_PYTHON_VERSION must be 3.12, 3.13 or 3.14.")
if ARCH not in PLATFORM:
    raise SystemExit("LAMBDA_ARCH must be x86_64 or arm64.")

out_dir = BASE / "dist"
out_dir.mkdir(exist_ok=True)
out_file = out_dir / f"order_api_lambda_py{RUNTIME}_{ARCH}.zip"

with tempfile.TemporaryDirectory(prefix="lambda-api-build-") as temp:
    staging = Path(temp)

    # Cross-platform pip download/install: select wheels matching Lambda's
    # Python ABI, architecture and Amazon Linux-compatible manylinux baseline.
    cmd = [
        sys.executable, "-m", "pip", "install",
        "--disable-pip-version-check", "--upgrade",
        "--only-binary=:all:",
        "--no-compile",
        "--platform", PLATFORM[ARCH],
        "--implementation", "cp",
        "--python-version", RUNTIME,
        "--abi", PYTHON_ABI[RUNTIME],
        "--target", str(staging),
        "-r", str(BASE / "requirements-lambda.txt"),
    ]
    print("Installing Lambda-targeted wheels:", " ".join(cmd))
    subprocess.check_call(cmd)

    shutil.copytree(BASE / "app", staging / "app",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(BASE / "lambda_handler.py", staging / "lambda_handler.py")

    # Fail early rather than creating a ZIP that will fail during Lambda init.
    core_dir = staging / "pydantic_core"
    native_extensions = list(core_dir.glob("_pydantic_core*.so")) + list(core_dir.glob("_pydantic_core*.pyd"))
    if not native_extensions:
        raise SystemExit(
            "ERROR: pydantic_core native extension was not installed. "
            "Check internet/pip output and rebuild with a supported runtime/architecture."
        )

    expected_arch_token = "x86_64" if ARCH == "x86_64" else "aarch64"
    extension_name = native_extensions[0].name
    if expected_arch_token not in extension_name:
        raise SystemExit(
            f"ERROR: Pydantic Core extension '{extension_name}' does not match {ARCH}. "
            "Rebuild using the Lambda function's configured architecture."
        )
    expected_abi_token = f"cpython-{RUNTIME.replace('.', '')}"
    if expected_abi_token not in extension_name:
        raise SystemExit(
            f"ERROR: Pydantic Core extension '{extension_name}' does not match Python {RUNTIME}. "
            "Rebuild using the Lambda function's configured runtime."
        )

    metadata = {
        "runtime": f"python{RUNTIME}",
        "architecture": ARCH,
        "platform": PLATFORM[ARCH],
        "handler": "lambda_handler.handler",
        "dependencies_file": "requirements-lambda.txt",
    }
    (staging / "BUILD_INFO.json").write_text(json.dumps(metadata, indent=2))

    if out_file.exists():
        out_file.unlink()
    with zipfile.ZipFile(out_file, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(staging.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                archive.write(path, path.relative_to(staging).as_posix())

# Verify the finished archive has the handler and compiled Pydantic Core module.
with zipfile.ZipFile(out_file) as archive:
    names = archive.namelist()
    assert "lambda_handler.py" in names, "ZIP is missing lambda_handler.py at its root"
    assert any(n.startswith("app/main.py") for n in names), "ZIP is missing app/main.py"
    assert any(n.startswith("pydantic_core/_pydantic_core") and n.endswith(".so") for n in names),         "ZIP is missing Pydantic Core's Linux shared library"
    assert not any("__pycache__/" in n or n.endswith(".pyc") for n in names),         "ZIP unexpectedly contains Python bytecode/cache files"

print(f"\nCreated and inspected: {out_file}")
print(f"Target: Python {RUNTIME} / {ARCH}")
print(f"Pydantic Core extension: {extension_name}")
print("IMPORTANT: Upload only to a Lambda function with the exact same runtime and architecture.")
