"""Transport metadata and legacy identity compatibility of config providers."""

import pytest

from custom_components.hitachi_yutaki.api.config_providers.atw_mbs_02 import (
    AtwMbs02ConfigProvider,
)
from custom_components.hitachi_yutaki.api.config_providers.hc_a_mb import (
    HcAMbConfigProvider,
)


@pytest.mark.parametrize(
    ("provider", "unit_data", "suffix"),
    [
        (AtwMbs02ConfigProvider(), {}, "0"),
        (HcAMbConfigProvider(), {"unit_id": 3}, "3"),
        (
            HcAMbConfigProvider(),
            {"unit_id": 3, "outdoor_cycle": 5, "indoor_address": 6},
            "c5_i6",
        ),
    ],
)
def test_provider_preserves_legacy_fallback_and_owns_transport_metadata(
    provider, unit_data, suffix
) -> None:
    """Shared callers can preserve identities and register devices without host access."""
    config = {
        "modbus_host": "192.0.2.1",
        "modbus_device_id": 7,
        "modbus_port": 502,
        **unit_data,
    }
    assert provider.fallback_unique_id(config) == f"192.0.2.1_7_{suffix}"
    assert provider.configuration_url(config) == "http://192.0.2.1"
    assert provider.sensitive_config_keys == {"modbus_host"}
    assert provider.same_gateway(config, dict(config))
    assert not provider.same_gateway(config, {**config, "modbus_host": "192.0.2.2"})
    assert not provider.same_gateway(config, {**config, "modbus_port": 503})
