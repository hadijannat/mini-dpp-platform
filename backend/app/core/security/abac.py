"""
ABAC (Attribute-Based Access Control) implementation using OPA.
Provides policy enforcement point (PEP) for route and element-level access control.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import httpx
from fastapi import HTTPException, Request, status

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security.oidc import TokenPayload

logger = get_logger(__name__)


class PolicyEffect(str, Enum):
    """Possible effects of an ABAC policy decision."""
    ALLOW = "allow"
    DENY = "deny"
    MASK = "mask"
    HIDE = "hide"
    DECRYPT = "decrypt"


@dataclass
class PolicyDecision:
    """
    Result of an ABAC policy evaluation.

    Contains the decision effect and any applicable transformations.
    """
    effect: PolicyEffect
    policy_id: str | None = None
    reason: str | None = None
    masked_value: str | None = None

    @property
    def is_allowed(self) -> bool:
        return self.effect in (PolicyEffect.ALLOW, PolicyEffect.DECRYPT)


@dataclass
class ABACContext:
    """
    Complete context for ABAC policy evaluation.

    Includes subject (user), action, resource, and environment attributes.
    """
    subject: dict[str, Any]
    action: str
    resource: dict[str, Any]
    environment: dict[str, Any] = field(default_factory=dict)

    def to_opa_input(self) -> dict[str, Any]:
        """Convert context to OPA input format."""
        return {
            "input": {
                "subject": self.subject,
                "action": self.action,
                "resource": self.resource,
                "environment": self.environment,
            }
        }


class OPAClient:
    """
    Client for Open Policy Agent (OPA) policy decisions.

    Sends ABAC context to OPA and interprets decisions.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._policy_url = f"{self._settings.opa_url}/{self._settings.opa_policy_path}"

    async def evaluate(self, context: ABACContext) -> PolicyDecision:
        """
        Evaluate an ABAC context against OPA policies.

        Returns a PolicyDecision indicating the effect and any transformations.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self._policy_url,
                    json=context.to_opa_input(),
                    timeout=self._settings.opa_timeout,
                )
                response.raise_for_status()
                result = response.json()

            # Parse OPA result
            decision_data = result.get("result", {})

            effect_str = decision_data.get("effect", "deny")
            try:
                effect = PolicyEffect(effect_str)
            except ValueError:
                effect = PolicyEffect.DENY

            return PolicyDecision(
                effect=effect,
                policy_id=decision_data.get("policy_id"),
                reason=decision_data.get("reason"),
                masked_value=decision_data.get("masked_value"),
            )

        except httpx.TimeoutException:
            logger.error("opa_timeout", policy_url=self._policy_url)
            # Fail closed on timeout
            return PolicyDecision(
                effect=PolicyEffect.DENY,
                reason="Policy evaluation timeout",
            )
        except httpx.HTTPError as e:
            logger.error("opa_error", error=str(e))
            # Fail closed on error
            return PolicyDecision(
                effect=PolicyEffect.DENY,
                reason="Policy evaluation error",
            )


# Singleton OPA client
_opa_client = OPAClient()


def build_subject_context(user: TokenPayload) -> dict[str, Any]:
    """Build ABAC subject context from token payload."""
    return {
        "sub": user.sub,
        "email": user.email,
        "roles": user.roles,
        "bpn": user.bpn,
        "org": user.org,
        "clearance": user.clearance or "public",
        "is_publisher": user.is_publisher,
        "is_admin": user.is_admin,
    }


def build_environment_context(request: Request | None = None) -> dict[str, Any]:
    """Build ABAC environment context from request."""
    context: dict[str, Any] = {
        "time": datetime.now(timezone.utc).isoformat(),
    }

    if request:
        context.update({
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "method": request.method,
            "path": str(request.url.path),
        })

    return context


async def check_access(
    user: TokenPayload,
    action: str,
    resource: dict[str, Any],
    request: Request | None = None,
) -> PolicyDecision:
    """
    Check access for a given action on a resource.

    This is the main entry point for ABAC policy evaluation.
    """
    context = ABACContext(
        subject=build_subject_context(user),
        action=action,
        resource=resource,
        environment=build_environment_context(request),
    )

    decision = await _opa_client.evaluate(context)

    logger.debug(
        "abac_decision",
        action=action,
        resource_type=resource.get("type"),
        resource_id=resource.get("id"),
        effect=decision.effect.value,
        policy_id=decision.policy_id,
    )

    return decision


async def require_access(
    user: TokenPayload,
    action: str,
    resource: dict[str, Any],
    request: Request | None = None,
) -> PolicyDecision:
    """
    Require access for a given action, raising HTTPException on denial.

    Use this in route handlers where access must be granted to proceed.
    """
    decision = await check_access(user, action, resource, request)

    if decision.effect == PolicyEffect.DENY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=decision.reason or "Access denied by policy",
        )

    return decision


async def filter_elements(
    user: TokenPayload,
    elements: list[dict[str, Any]],
    resource_base: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Filter and transform elements based on ABAC policies.

    Applies mask/hide effects to individual elements in a collection.
    Returns a new list with filtered and transformed elements.
    """
    filtered: list[dict[str, Any]] = []

    for element in elements:
        resource = {
            **resource_base,
            "element_path": element.get("path"),
            "element_type": element.get("type"),
            "confidentiality": element.get("confidentiality", "public"),
        }

        decision = await check_access(user, "read", resource)

        if decision.effect == PolicyEffect.HIDE:
            # Skip hidden elements entirely
            continue
        elif decision.effect == PolicyEffect.MASK:
            # Include element but mask the value
            masked_element = element.copy()
            masked_element["value"] = decision.masked_value or "***"
            masked_element["_masked"] = True
            filtered.append(masked_element)
        elif decision.is_allowed:
            filtered.append(element)

    return filtered
