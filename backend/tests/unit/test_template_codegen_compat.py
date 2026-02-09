"""Optional compatibility checks for aas-submodel-template-to-py tooling.

These checks are CI-gated with RUN_TEMPLATE_CODEGEN_COMPAT=1 because they
require network access and optional third-party tooling.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.templates.catalog import list_template_keys
from app.modules.templates.service import TemplateRegistryService

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.getenv("RUN_TEMPLATE_CODEGEN_COMPAT") != "1",
        reason="Set RUN_TEMPLATE_CODEGEN_COMPAT=1 to run codegen compatibility checks",
    ),
]


def _run_codegen(input_path: Path) -> None:
    """Attempt code generation using available library/CLI entry points."""
    module = None
    for name in ("submodel_to_code", "aas_submodel_template_to_py"):
        try:
            module = importlib.import_module(name)
            break
        except ModuleNotFoundError:
            continue

    if module is not None:
        codegen_cls = getattr(module, "SubmodelCodegen", None)
        if codegen_cls is not None and hasattr(codegen_cls, "generate_from"):
            # Support both static/class method and instance method variants.
            try:
                codegen_cls.generate_from(str(input_path))
                return
            except TypeError:
                codegen_cls().generate_from(str(input_path))
                return

    # Fallback to CLI if import path is unavailable.
    completed = subprocess.run(
        ["submodel_to_code", str(input_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise AssertionError(
            "submodel-template codegen failed. "
            f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
        )


async def test_templates_are_convertible_by_codegen_tool(
    db_session: AsyncSession,
    tmp_path: Path,
) -> None:
    service = TemplateRegistryService(db_session)

    for template_key in list_template_keys(refreshable_only=True):
        template = await service.refresh_template(template_key)

        if template.template_aasx:
            source_path = tmp_path / f"{template_key}.aasx"
            source_path.write_bytes(template.template_aasx)
        else:
            source_path = tmp_path / f"{template_key}.json"
            source_path.write_text(json.dumps(template.template_json), encoding="utf-8")

        _run_codegen(source_path)
