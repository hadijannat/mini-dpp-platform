"""Catena-X connector for DTR publishing with optional EDC DSP metadata."""

from app.modules.connectors.catenax.dtr_client import DTRClient, DTRConfig, ShellDescriptor
from app.modules.connectors.catenax.mapping import build_shell_descriptor
from app.modules.connectors.catenax.service import CatenaXConnectorService

__all__ = [
    "CatenaXConnectorService",
    "DTRClient",
    "DTRConfig",
    "ShellDescriptor",
    "build_shell_descriptor",
]
