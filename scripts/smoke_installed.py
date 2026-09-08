"""Install the built wheel, then execute an example outside the source tree."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
wheel = next((root / "dist").glob("*.whl"))
subprocess.run([sys.executable, "-m", "pip", "install", "--force-reinstall", "--no-deps", str(wheel)], check=True)
environment = os.environ.copy()
environment.pop("PYTHONPATH", None)
with tempfile.TemporaryDirectory(prefix="calibshift_installed_") as directory:
    subprocess.run(
        [sys.executable, "-m", "calibshift.cli", "demo", "--output", str(Path(directory) / "result")],
        cwd=directory,
        env=environment,
        check=True,
    )
