"""Single capability catalog used by the API and frontend."""
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from core.config import Settings, get_settings
from core.feature_flags import write_block_reason


class CapabilityState(StrEnum):
    UNAVAILABLE = "UNAVAILABLE"
    DISABLED = "DISABLED"
    INTERNAL_ONLY = "INTERNAL_ONLY"
    CONFIGURATION_REQUIRED = "CONFIGURATION_REQUIRED"
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    BLOCKED_AUTH = "BLOCKED_AUTH"
    BLOCKED_MAPPING = "BLOCKED_MAPPING"
    BLOCKED_DEVICE = "BLOCKED_DEVICE"
    FAILED_CERTIFICATION = "FAILED_CERTIFICATION"


@dataclass(frozen=True)
class CapabilityContext:
    role: str
    installations: frozenset[str] = frozenset()
    healthy_installations: frozenset[str] = frozenset()
    reported_capabilities: frozenset[str] = frozenset()
    mapped_capabilities: frozenset[str] = frozenset()
    certification_levels: Mapping[str, int] = field(default_factory=dict)
    certification_versions: Mapping[str, str] = field(default_factory=dict)
    overrides: tuple[Mapping[str, Any], ...] = ()
    firm_id: str = ""
    client_id: str = ""


@dataclass(frozen=True)
class Capability:
    capability_key: str
    state: CapabilityState
    implementation_version: str = "v1"
    environment: str = "production"
    reason_code: str = ""
    reason_message: str = ""
    required_user_action: str = ""
    last_probe_at: str | None = None
    last_success_at: str | None = None
    certification_version: str | None = None
    certification_level: int = 0
    feature_flag: str = ""


def evaluate_capabilities(
    context: CapabilityContext,
    config: Settings | None = None,
) -> list[Capability]:
    """Evaluate every supported operation without exposing an enable endpoint."""
    settings = config or get_settings()
    return [
        _document_upload(settings),
        _extraction(settings),
        *[_connector_read(key, "ZOHO_BOOKS", context, settings) for key in (
            "zoho.connection.oauth", "zoho.read.organizations", "zoho.read.contacts",
            "zoho.read.accounts", "zoho.read.items", "zoho.read.taxes",
            "zoho.read.purchase_bills", "zoho.read.sales_invoices", "zoho.read.object")],
        _connector_write("zoho.write.purchase_bill.create", "ZOHO_BOOKS", context, settings),
        _connector_write("zoho.verify.purchase_bill", "ZOHO_BOOKS", context, settings),
        _connector_write("zoho.write.sales_invoice.create", "ZOHO_BOOKS", context, settings),
        _connector_write("zoho.verify.sales_invoice", "ZOHO_BOOKS", context, settings),
        *[_connector_read(key, "TALLY_PRIME", context, settings) for key in (
            "tally.device.pair", "tally.read.companies", "tally.read.ledgers", "tally.read.vouchers")],
        _connector_write("tally.write.purchase_voucher.create", "TALLY_PRIME", context, settings),
        _connector_write("tally.verify.purchase_voucher", "TALLY_PRIME", context, settings),
        _connector_write("tally.write.sales_voucher.create", "TALLY_PRIME", context, settings),
        _connector_write("tally.verify.sales_voucher", "TALLY_PRIME", context, settings),
        Capability("gst.manual_filing", CapabilityState.AVAILABLE, environment=settings.firmos_environment),
        Capability("whatsapp.inbound", CapabilityState.DISABLED, environment=settings.firmos_environment,
                   reason_code="NOT_IMPLEMENTED", reason_message="WhatsApp inbound automation is disabled.",
                   required_user_action="Use the web application.", feature_flag="whatsapp.inbound"),
        Capability("decision.email_delivery", CapabilityState.DISABLED, environment=settings.firmos_environment,
                   reason_code="MANUAL_REVIEW_REQUIRED", reason_message="Decision emails are not sent in V1.",
                   required_user_action="Record the reviewed response in firmOS.", feature_flag="decision.email_delivery"),
    ]


def _document_upload(settings: Settings) -> Capability:
    enabled = bool(settings.supabase_url and settings.supabase_service_key) or settings.local_storage_allowed
    return Capability(
        "documents.upload",
        CapabilityState.AVAILABLE if enabled else CapabilityState.CONFIGURATION_REQUIRED,
        environment=settings.firmos_environment,
        reason_code="" if enabled else "PRIVATE_STORAGE_UNAVAILABLE",
        required_user_action="Configure private object storage." if not enabled else "",
    )


def _extraction(settings: Settings) -> Capability:
    has_key = bool(settings.sarvam_api_key or settings.gemini_api_key)
    return Capability(
        "documents.extract.invoice",
        CapabilityState.AVAILABLE if has_key else CapabilityState.CONFIGURATION_REQUIRED,
        environment=settings.firmos_environment,
        reason_code="" if has_key else "EXTRACTOR_CREDENTIALS_MISSING",
        required_user_action="Configure a supported extraction provider." if not has_key else "",
    )


def _connector_read(key: str, provider: str, context: CapabilityContext, settings: Settings) -> Capability:
    installed = provider in context.installations
    healthy = provider in context.healthy_installations
    reported = key in context.reported_capabilities
    return Capability(
        key,
        CapabilityState.AVAILABLE if installed and healthy and reported else (
            CapabilityState.BLOCKED_AUTH if installed and healthy else (
                CapabilityState.DEGRADED if installed else CapabilityState.CONFIGURATION_REQUIRED
            )
        ),
        environment=settings.firmos_environment,
        reason_code="" if installed and healthy and reported else (
            "MISSING_OAUTH_SCOPE" if installed and healthy else
            ("INSTALLATION_UNHEALTHY" if installed else "CONNECTOR_NOT_INSTALLED")),
        required_user_action=("Reconnect and approve the required provider access." if installed and healthy else
                              ("Run connector health checks." if installed else
                               "Connect and authenticate the provider.")),
    )


def _connector_write(key: str, provider: str, context: CapabilityContext, settings: Settings) -> Capability:
    if context.role.upper() not in {"OWNER", "ADMIN"}:
        return Capability(key, CapabilityState.DISABLED, environment=settings.firmos_environment,
                          reason_code="ROLE_REQUIRED", required_user_action="Ask a firm owner to approve writes.")
    if provider not in context.installations:
        return Capability(key, CapabilityState.CONFIGURATION_REQUIRED, environment=settings.firmos_environment,
                          reason_code="CONNECTOR_NOT_INSTALLED", required_user_action="Connect and authenticate the provider.")
    if provider not in context.healthy_installations:
        return Capability(key, CapabilityState.DEGRADED, environment=settings.firmos_environment,
                          reason_code="INSTALLATION_UNHEALTHY", required_user_action="Restore connector health.")
    if key not in context.reported_capabilities:
        return Capability(key, CapabilityState.BLOCKED_AUTH, environment=settings.firmos_environment,
                          reason_code="MISSING_OAUTH_SCOPE",
                          required_user_action="Reconnect and approve the required provider access.")
    if ".write." in key and key not in context.mapped_capabilities:
        return Capability(key, CapabilityState.BLOCKED_MAPPING, environment=settings.firmos_environment,
                          reason_code="MAPPINGS_REQUIRED", required_user_action=(
                              "Confirm the Tally company and ledger identities." if provider == "TALLY_PRIME"
                              else "Approve contact, ledger, and tax mappings."))
    level = int(context.certification_levels.get(key, 0))
    if level < 5:
        return Capability(key, CapabilityState.FAILED_CERTIFICATION, environment=settings.firmos_environment,
                          reason_code="CERTIFICATION_L5_REQUIRED",
                          reason_message=f"Connector certification is L{level}; production writes require L5.",
                          required_user_action="Complete the controlled pilot certification.",
                          certification_level=level,
                          certification_version=context.certification_versions.get(key))
    reason = write_block_reason(provider, firm_id=context.firm_id, client_id=context.client_id,
                                capability_key=key, overrides=context.overrides, config=settings)
    return Capability(
        key,
        CapabilityState.AVAILABLE if reason is None else CapabilityState.DISABLED,
        environment=settings.firmos_environment,
        reason_code=reason or "",
        reason_message="Provider writes are disabled by a safety control." if reason else "",
        required_user_action="Enable the approved write control after review." if reason else "",
        certification_version=context.certification_versions.get(key),
        certification_level=level,
        feature_flag="provider_writes_enabled",
    )
