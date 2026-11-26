"""Translate API circuit observations into a domain activity verdict."""

from ..api import HitachiApiClient
from ..const import CIRCUIT_IDS
from ..domain.models.circuit import CircuitActivity, CircuitActivityInput
from ..domain.services.circuit import resolve_circuit_activity
from .providers.operation_mode import resolve_operation_mode


def get_circuit_activity(
    api_client: HitachiApiClient, circuit_id: CIRCUIT_IDS
) -> CircuitActivity:
    """Normalize the API's operation state and evaluate circuit activity."""
    operation_state = api_client.get_operation_state()
    return resolve_circuit_activity(
        CircuitActivityInput(
            powered=api_client.get_circuit_power(circuit_id),
            compressor_running=api_client.is_compressor_running,
            defrosting=api_client.is_defrosting,
            operation_mode=resolve_operation_mode(operation_state),
            operation_state_available=operation_state
            not in (None, "operation_state_unknown"),
        )
    )
