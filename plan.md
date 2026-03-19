# Plan: Inversion Gateway ↔ Transport

## Objectif

Inverser la relation de dépendance : actuellement le transport (ModbusApiClient) est la classe principale qui reçoit un RegisterMap en paramètre. On veut que la **Gateway** soit la classe principale et qu'elle **possède** son transport.

## Architecture actuelle

```
GATEWAY_INFO["modbus_atw_mbs_02"] → ModbusApiClient + AtwMbs02RegisterMap (default)
GATEWAY_INFO["modbus_hc_a_mb"]    → ModbusApiClient + HcAMbRegisterMap (via create_register_map)
```

- `ModbusApiClient` = transport TCP + business logic + register map
- `create_register_map()` = factory externe qui choisit la register map

## Architecture cible

```
GATEWAY_INFO["modbus_atw_mbs_02"] → AtwMbs02Gateway → ModbusTransport + AtwMbs02RegisterMap
GATEWAY_INFO["modbus_hc_a_mb"]    → HcAMbGateway    → ModbusTransport + HcAMbRegisterMap
```

Chaque gateway est une classe autonome qui :
1. Connaît sa register map
2. Crée et possède son transport Modbus
3. Expose l'interface `HitachiApiClient`

## Étapes

### 1. Extraire `ModbusTransport` (nouvelle classe)

Extraire de `ModbusApiClient` les opérations purement transport dans `api/modbus/transport.py` :

```python
class ModbusTransport:
    """Low-level Modbus TCP transport."""

    def __init__(self, hass, host, port, slave):
        ...

    async def connect() -> bool
    async def close() -> bool
    @property connected -> bool
    async def read_holding_registers(address, count, device_param) -> result
    async def read_input_registers(address, count, device_param) -> result
    async def write_register(address, value, device_param) -> result
    async def ensure_connection() -> bool  # retry logic
```

### 2. Créer `ModbusGateway` (base class)

Renommer/refactorer `ModbusApiClient` en `ModbusGateway` dans `api/modbus/__init__.py` :

- Supprime la logique de construction du transport (c'est le constructeur des sous-classes qui le fait)
- Reçoit un `ModbusTransport` et un `HitachiRegisterMap` (injectés par les sous-classes)
- Conserve toute la business logic (has_dhw, get_unit_mode, etc.)
- Devient une classe abstraite qui force les sous-classes à fournir transport + register map

### 3. Créer les gateways concrètes

**`api/modbus/gateways/atw_mbs_02.py`** :

```python
class AtwMbs02Gateway(ModbusGateway):
    def __init__(self, hass, name, host, port, slave):
        transport = ModbusTransport(hass, host, port, slave)
        register_map = AtwMbs02RegisterMap()
        super().__init__(hass, name, transport, register_map)
```

**`api/modbus/gateways/hc_a_mb.py`** :

```python
class HcAMbGateway(ModbusGateway):
    def __init__(self, hass, name, host, port, slave, unit_id=0):
        transport = ModbusTransport(hass, host, port, slave)
        register_map = HcAMbRegisterMap(unit_id=unit_id)
        super().__init__(hass, name, transport, register_map)
```

### 4. Mettre à jour `api/__init__.py`

```python
GATEWAY_INFO = {
    "modbus_atw_mbs_02": GatewayInfo(
        manufacturer="Hitachi",
        model="ATW-MBS-02",
        client_class=AtwMbs02Gateway,
    ),
    "modbus_hc_a_mb": GatewayInfo(
        manufacturer="Hitachi",
        model="HC-A(16/64)MB",
        client_class=HcAMbGateway,
    ),
}
```

- Supprimer `create_register_map()` (plus nécessaire)

### 5. Mettre à jour les sites d'instanciation

**`__init__.py`** (setup) et **`config_flow.py`** :

Avant :
```python
register_map = create_register_map(gateway_type, unit_id)
api_client = gateway_info.client_class(hass, name, host, port, slave, register_map=register_map)
```

Après :
```python
api_client = gateway_info.client_class(hass, name, host, port, slave)
# Pour HC-A-MB: gateway_info.client_class(hass, name, host, port, slave, unit_id=unit_id)
```

Le `unit_id` devient un paramètre spécifique à `HcAMbGateway`. On peut utiliser `**kwargs` ou un paramètre optionnel sur la signature de `GatewayInfo`.

### 6. Mettre à jour les tests

Adapter les tests existants pour la nouvelle structure.

## Structure de fichiers résultante

```
api/
├── __init__.py              # GatewayInfo, GATEWAY_INFO (simplifié)
├── base.py                  # HitachiApiClient (ABC) - inchangé
└── modbus/
    ├── __init__.py           # ModbusGateway (base, business logic)
    ├── transport.py          # ModbusTransport (TCP Modbus pur)
    ├── gateways/
    │   ├── __init__.py
    │   ├── atw_mbs_02.py    # AtwMbs02Gateway
    │   └── hc_a_mb.py       # HcAMbGateway
    └── registers/
        ├── __init__.py       # HitachiRegisterMap, RegisterDefinition - inchangé
        ├── atw_mbs_02.py     # inchangé
        └── hc_a_mb.py        # inchangé
```

## Avantages

- **Inversion de dépendance** : la gateway est le concept principal, le transport est un détail
- **Extensibilité** : ajouter un transport non-Modbus = nouvelle gateway, pas besoin de toucher ModbusGateway
- **Encapsulation** : chaque gateway sait exactement comment se configurer
- **Simplification** : plus besoin de `create_register_map()`, plus de paramètre `register_map` à passer
- **Signature propre** : `HcAMbGateway` accepte `unit_id`, `AtwMbs02Gateway` non

## Points d'attention

- Ne pas casser les tests existants
- Garder `HitachiApiClient` (ABC) inchangé - c'est le port hexagonal
- Le `register_map` reste accessible via `gateway.register_map` pour le coordinator
