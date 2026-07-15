"""Capability state and provider-write safety controls."""
import base64
import logging

from core.config import Settings
from core.feature_flags import write_block_reason
from core.redaction import redact, redact_sentry_event
from connectors.platform.capabilities import CapabilityContext, CapabilityState, evaluate_capabilities


def _settings(**changes) -> Settings:
    values = {
        "database_url": "postgresql://test:test@localhost/test",
        "supabase_jwt_secret": "test-secret",
        "token_enc_key": base64.b64encode(b"0" * 32).decode(),
        "firmos_environment": "production",
        "provider_writes_enabled": True,
        "zoho_writes_enabled": True,
        "tally_writes_enabled": True,
    }
    values.update(changes)
    return Settings(**values)


def _state(items, key: str):
    return next(item for item in items if item.capability_key == key)


def test_write_capability_requires_role_installation_and_certification():
    config = _settings()
    key = "zoho.write.purchase_bill.create"
    viewer = CapabilityContext(role="VIEWER", installations=frozenset({"ZOHO_BOOKS"}), healthy_installations=frozenset({"ZOHO_BOOKS"}), reported_capabilities=frozenset({key}), certification_levels={key: 5})
    assert _state(evaluate_capabilities(viewer, config), key).reason_code == "ROLE_REQUIRED"

    missing_certification = CapabilityContext(role="OWNER", installations=frozenset({"ZOHO_BOOKS"}), healthy_installations=frozenset({"ZOHO_BOOKS"}), reported_capabilities=frozenset({key}), mapped_capabilities=frozenset({key}))
    assert _state(evaluate_capabilities(missing_certification, config), key).state == CapabilityState.FAILED_CERTIFICATION


def test_write_capability_obeys_global_and_scoped_kill_switches():
    context = CapabilityContext(
        role="OWNER", firm_id="firm-1", client_id="client-1", installations=frozenset({"ZOHO_BOOKS"}),
        healthy_installations=frozenset({"ZOHO_BOOKS"}), mapped_capabilities=frozenset({"zoho.write.purchase_bill.create"}),
        reported_capabilities=frozenset({"zoho.write.purchase_bill.create"}),
        certification_levels={"zoho.write.purchase_bill.create": 5},
    )
    disabled = _state(evaluate_capabilities(context, _settings(provider_writes_enabled=False)), "zoho.write.purchase_bill.create")
    assert disabled.reason_code == "PROVIDER_WRITES_DISABLED"

    killed = CapabilityContext(**{**context.__dict__, "overrides": ({"firm_id": "firm-1", "client_id": "client-1", "is_enabled": False},)})
    assert _state(evaluate_capabilities(killed, _settings()), "zoho.write.purchase_bill.create").reason_code == "CAPABILITY_DISABLED"


def test_override_cannot_enable_a_globally_disabled_provider():
    assert write_block_reason(
        "ZOHO_BOOKS", overrides=({"provider": "ZOHO_BOOKS", "is_enabled": True},), config=_settings(provider_writes_enabled=False),
    ) == "PROVIDER_WRITES_DISABLED"


def test_write_capability_is_available_only_at_l5():
    key = "zoho.write.purchase_bill.create"
    base = dict(role="OWNER", installations=frozenset({"ZOHO_BOOKS"}),
                healthy_installations=frozenset({"ZOHO_BOOKS"}), reported_capabilities=frozenset({key}),
                mapped_capabilities=frozenset({key}))
    for level in range(5):
        capability = _state(evaluate_capabilities(
            CapabilityContext(**base, certification_levels={key: level}), _settings(),
        ), key)
        assert capability.state == CapabilityState.FAILED_CERTIFICATION
        assert capability.certification_level == level
    available = _state(evaluate_capabilities(
        CapabilityContext(**base, certification_levels={key: 5},
                          certification_versions={key: "v3"}), _settings(),
    ), key)
    assert available.state == CapabilityState.AVAILABLE
    assert available.certification_version == "v3"


def test_capability_requires_its_exact_oauth_scope():
    context = CapabilityContext(
        role="OWNER", installations=frozenset({"ZOHO_BOOKS"}),
        healthy_installations=frozenset({"ZOHO_BOOKS"}),
        reported_capabilities=frozenset({"zoho.read.contacts"}),
    )
    items = evaluate_capabilities(context, _settings())
    assert _state(items, "zoho.read.contacts").state == CapabilityState.AVAILABLE
    assert _state(items, "zoho.read.purchase_bills").state == CapabilityState.BLOCKED_AUTH


def test_redaction_removes_tokens_pan_bank_and_provider_payloads():
    secret = ".".join(("test-header", "test-payload", "test-signature"))
    safe = redact({"authorization": f"Bearer {secret}", "pan": "ABCDE1234F", "bank_account": "123456789", "provider_payload": {"invoice": "raw"}})
    assert secret not in str(safe)
    assert "ABCDE1234F" not in str(safe)
    assert "123456789" not in str(safe)
    sentry = redact_sentry_event({"extra": {"token": secret, "message": "PAN ABCDE1234F"}}, {})
    assert secret not in str(sentry)
    assert "ABCDE1234F" not in str(sentry)


def test_standard_log_filter_redacts_rendered_messages():
    record = logging.LogRecord("test", logging.INFO, "", 0, "token=%s PAN=%s", ("secret-value", "ABCDE1234F"), None)
    from core.redaction import RedactingFilter
    RedactingFilter().filter(record)
    assert "secret-value" not in record.getMessage()
    assert "ABCDE1234F" not in record.getMessage()
