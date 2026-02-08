"""Asset ID discovery service — re-exports from service module.

The ``DiscoveryService`` lives in ``service.py`` alongside the registry
service to share common helpers. This module re-exports it for
convenience and to match the expected file layout.
"""

from __future__ import annotations

from app.modules.registry.service import DiscoveryService

__all__ = ["DiscoveryService"]
