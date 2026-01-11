from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _venv_paths(venv_dir: Path) -> tuple[Path, Path]:
    if os.name == "nt":
        bin_dir = venv_dir / "Scripts"
        python = bin_dir / "python.exe"
    else:
        bin_dir = venv_dir / "bin"
        python = bin_dir / "python"
    return python, bin_dir


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=sys.stderr, stderr=sys.stderr)


def main() -> None:
    backend_dir = Path(__file__).resolve().parents[2]
    venv_dir = backend_dir / ".venv-compliance"
    python, bin_dir = _venv_paths(venv_dir)
    exe = bin_dir / "aas-compliance-check"

    if not python.exists():
        _run([sys.executable, "-m", "venv", str(venv_dir)])

    needs_install = not exe.exists()
    if not needs_install:
        try:
            _run(
                [
                    str(python),
                    "-c",
                    "import aas_compliance_tool; import basyx.aas.compliance_tool",
                ]
            )
        except subprocess.CalledProcessError:
            needs_install = True

    if needs_install:
        _run([str(python), "-m", "pip", "install", "--upgrade", "pip"])
        _run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "basyx-python-sdk==1.0.0",
                "git+https://github.com/rwth-iat/aas-compliance-tool@v1.0.0",
            ]
        )

    print(exe)


if __name__ == "__main__":
    main()
