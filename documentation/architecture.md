# Architecture Hitachi Yutaki Integration

## Vue d'ensemble

L'intégration Hitachi Yutaki suit une **architecture hexagonale** (Ports and Adapters) avec une organisation par **domaine métier**.

## Structure Générale

```
custom_components/hitachi_yutaki/
├── entities/                    # Domaines métier (NOUVEAU)
│   ├── base/                    # Classes de base partagées
│   ├── performance/             # COP (✅ MIGRÉ)
│   ├── thermal/                 # Production thermique (✅ MIGRÉ)
│   ├── power/                   # Consommation électrique (✅ MIGRÉ)
│   ├── gateway/                 # Passerelle (✅ MIGRÉ)
│   ├── hydraulic/               # Hydraulique (🚧 EN COURS)
│   ├── compressor/              # Compresseurs (⏳ À FAIRE)
│   ├── control_unit/            # Unité de contrôle (⏳ À FAIRE)
│   ├── circuit/                 # Circuits chauffage/refroidissement (⏳ À FAIRE)
│   ├── dhw/                     # Eau chaude sanitaire (⏳ À FAIRE)
│   └── pool/                    # Piscine (⏳ À FAIRE)
│
├── domain/                      # Logique métier pure
│   ├── models/                  # Modèles de données
│   ├── ports/                   # Interfaces (abstractions)
│   └── services/                # Services métier
│
├── adapters/                    # Implémentations d'infrastructure
│   ├── calculators/             # Calculs (COP, thermique, électrique)
│   ├── providers/               # Fournisseurs de données
│   └── storage/                 # Stockage en mémoire
│
├── api/                         # Client API Modbus
│   └── modbus/                  # Registres Modbus spécifiques
│
├── profiles/                    # Profils matériels
│
├── sensor.py                    # Plateforme HA sensor (⏳ À REFACTORER)
├── binary_sensor.py             # Plateforme HA binary_sensor (⏳ À REFACTORER)
├── switch.py                    # Plateforme HA switch (⏳ À REFACTORER)
├── number.py                    # Plateforme HA number (⏳ À REFACTORER)
├── climate.py                   # Plateforme HA climate (⏳ À REFACTORER)
└── water_heater.py              # Plateforme HA water_heater (⏳ À REFACTORER)
```

## Couches Architecturales

### 1. Domain Layer (Logique Métier)

**Emplacement** : `domain/`

**Responsabilités** :
- Modèles de données métier purs (NamedTuples, dataclasses)
- Ports (interfaces/protocols)
- Services métier avec logique pure
- **Aucune dépendance** vers Home Assistant ou Modbus

**Exemples** :
- `domain/models/cop.py` : Modèles COP, PowerMeasurement
- `domain/services/cop.py` : Calcul du COP
- `domain/services/thermal.py` : Calcul de l'énergie thermique
- `domain/ports/providers.py` : Interfaces DataProvider, StateProvider

### 2. Adapters Layer (Infrastructure)

**Emplacement** : `adapters/`

**Responsabilités** :
- Implémentations concrètes des ports
- Adaptateurs entre le domaine et l'infrastructure externe
- Stockage en mémoire
- Calculateurs (électrique, thermique)

**Exemples** :
- `adapters/providers/coordinator.py` : Fournisseur de données depuis le coordinator
- `adapters/calculators/electrical.py` : Calculateur de puissance électrique
- `adapters/storage/in_memory.py` : Stockage en mémoire

### 3. Entity Layer (Home Assistant)

**Emplacement** : `entities/`

**Responsabilités** :
- Organisation par **domaine métier**
- Builders pour créer les entités
- Descriptions d'entités (dataclasses)
- Classes d'entités Home Assistant

#### Structure d'un Domaine

Chaque domaine suit cette structure :

```
entities/<domain>/
├── __init__.py              # Exports des builders
├── sensors.py               # Sensors du domaine (si applicable)
├── binary_sensors.py        # Binary sensors du domaine (si applicable)
├── switches.py              # Switches du domaine (si applicable)
├── numbers.py               # Numbers du domaine (si applicable)
├── climate.py               # Climate du domaine (si applicable)
└── water_heater.py          # Water heater du domaine (si applicable)
```

#### Pattern des Builders

Chaque fichier expose un **builder** qui retourne une liste d'entités :

```python
def build_<domain>_<entity_type>(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
    # Paramètres spécifiques au domaine (circuit_id, compressor_id, etc.)
) -> list[Entity]:
    """Build <entity_type> entities for <domain>."""
    descriptions = _build_<domain>_<entity_type>_descriptions()
    from ..base.<entity_type> import _create_<entity_type>s
    return _create_<entity_type>s(coordinator, entry_id, descriptions, DEVICE_TYPE)
```

#### Classes de Base

**Emplacement** : `entities/base/`

**Contenu** :
- `sensor.py` : `HitachiYutakiSensor`, `HitachiYutakiSensorEntityDescription`, `_create_sensors()`
- `binary_sensor.py` : `HitachiYutakiBinarySensor`, `HitachiYutakiBinarySensorEntityDescription`, `_create_binary_sensors()`
- `switch.py` : `HitachiYutakiSwitch`, `HitachiYutakiSwitchEntityDescription`, `_create_switches()`
- `number.py` : `HitachiYutakiNumber`, `HitachiYutakiNumberEntityDescription`, `_create_numbers()`
- `climate.py` : `HitachiYutakiClimate` (⏳ À CRÉER)
- `water_heater.py` : `HitachiYutakiWaterHeater` (⏳ À CRÉER)

### 4. Platform Layer (Points d'Entrée HA)

**Emplacement** : Fichiers racine (`sensor.py`, `binary_sensor.py`, etc.)

**Responsabilités** :
- Implémentation de `async_setup_entry()` (requis par Home Assistant)
- Appel des builders depuis les domaines
- Enregistrement des entités

**Exemple** (sensor.py refactoré) :

```python
"""Sensor platform for Hitachi Yutaki integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HitachiYutakiDataCoordinator

# Import builders from domain entities
from .entities.gateway import build_gateway_sensors
from .entities.performance import build_performance_sensors
from .entities.thermal import build_thermal_sensors
from .entities.power import build_power_sensors
# ... autres imports


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator: HitachiYutakiDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = []
    
    # Gateway sensors
    entities.extend(build_gateway_sensors(coordinator, entry.entry_id))
    
    # Performance sensors (COP)
    entities.extend(build_performance_sensors(coordinator, entry.entry_id))
    
    # Thermal sensors
    entities.extend(build_thermal_sensors(coordinator, entry.entry_id))
    
    # Power sensors (electrical consumption)
    entities.extend(build_power_sensors(coordinator, entry.entry_id))
    
    # ... autres domaines
    
    # Register entities with coordinator
    coordinator.entities.extend(entities)
    
    async_add_entities(entities)
```

## Mapping Domaines → Types d'Entités

| Domaine | Sensors | Binary Sensors | Switches | Numbers | Climate | Water Heater |
|---------|---------|----------------|----------|---------|---------|--------------|
| gateway | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| hydraulic | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| compressor | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| control_unit | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| circuit | ✅ | ❌ | ✅ | ✅ | ✅ | ❌ |
| dhw | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| pool | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ |
| performance | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| thermal | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| power | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

## Principes Architecturaux

### 1. Séparation des Responsabilités (SRP)

Chaque domaine métier a sa propre responsabilité :
- **gateway** : Passerelle de communication
- **hydraulic** : Circuit hydraulique (pompes, température de l'eau)
- **compressor** : Compresseurs primaire et secondaire
- **control_unit** : Unité de contrôle (outdoor, diagnostics)
- **circuit** : Circuits de chauffage/refroidissement
- **dhw** : Eau chaude sanitaire
- **pool** : Piscine
- **performance** : Performance (COP)
- **thermal** : Énergie thermique produite
- **power** : Consommation électrique

### 2. Dependency Inversion Principle (DIP)

Les entités dépendent d'abstractions (API, coordinateur) via des callables :

```python
HitachiYutakiSensorEntityDescription(
    key="cop_heating",
    # Dépend du coordinateur (abstraction)
    condition=lambda c: (
        c.has_circuit(CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_HEATING)
        or c.has_circuit(CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_HEATING)
    ),
    # Dépend de l'API (abstraction)
    value_fn=lambda coordinator: coordinator.api_client.get_cop_heating(),
)
```

### 3. Builder Pattern

Les builders centralisent la création des entités :
- Construction dynamique basée sur la configuration
- Filtrage via `condition`
- Retour d'une liste d'entités prêtes à l'emploi

### 4. Configuration Déclarative

Les entités sont décrites via des dataclasses :

```python
@dataclass
class HitachiYutakiSensorEntityDescription(SensorEntityDescription):
    key: str
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    condition: Callable[[HitachiYutakiDataCoordinator], bool] | None = None
    value_fn: Callable[[HitachiYutakiDataCoordinator], StateType] | None = None
    # ... autres champs
```

### 5. Hexagonal Architecture

```
┌───────────────────────────────────────────────┐
│          Home Assistant (External)            │
└────────────────┬──────────────────────────────┘
                 │
        ┌────────▼────────┐
        │  Platform Files  │ sensor.py, climate.py...
        │  (Entry Points)  │
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │  Entity Layer    │ entities/ (domain-based)
        │   (Adapters)     │
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │  Domain Layer    │ domain/ (pure business logic)
        │  (Core Business) │
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │ Adapters Layer   │ adapters/ (infrastructure)
        │ (Infrastructure) │
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │    API Layer     │ api/ (Modbus communication)
        │  (External API)  │
        └──────────────────┘
```

## État de la Migration

### ✅ Complété

- [x] **Structure `entities/base/`** : Classes de base créées
- [x] **Domaine `performance/`** : Sensors COP
- [x] **Domaine `thermal/`** : Sensors énergie thermique
- [x] **Domaine `power/`** : Sensors consommation électrique
- [x] **Domaine `gateway/`** : Sensors + Binary sensors
- [x] Documentation architecture

### 🚧 En Cours

- [ ] **Domaine `hydraulic/`** : Sensors + Binary sensors
- [ ] **Domaine `compressor/`** : Sensors + Binary sensors
- [ ] **Domaine `control_unit/`** : Sensors + Binary sensors + Switches
- [ ] **Domaine `circuit/`** : Sensors + Numbers + Switches + Climate
- [ ] **Domaine `dhw/`** : Sensors + Binary sensors + Numbers + Switches + Water heater
- [ ] **Domaine `pool/`** : Sensors + Numbers + Switches

### ⏳ À Faire

- [ ] Refactorer `sensor.py` pour utiliser les builders
- [ ] Refactorer `binary_sensor.py` pour utiliser les builders
- [ ] Refactorer `switch.py` pour utiliser les builders
- [ ] Refactorer `number.py` pour utiliser les builders
- [ ] Refactorer `climate.py` pour utiliser les builders
- [ ] Refactorer `water_heater.py` pour utiliser les builders
- [ ] Supprimer anciennes structures (`sensor/`, `binary_sensor/`, `switch/`, `number/`)
- [ ] Mettre à jour `CHANGELOG.md`
- [ ] Linting complet

## Avantages de cette Architecture

1. **Modularité** : Chaque domaine est indépendant
2. **Testabilité** : Tests unitaires par domaine
3. **Maintenabilité** : Modifications localisées
4. **Compréhension** : Organisation intuitive par domaine métier
5. **Évolutivité** : Ajout de nouveaux domaines facilité
6. **Découplage** : Logique métier indépendante de Home Assistant
7. **Réutilisabilité** : Classes de base partagées
8. **Consistance** : Pattern uniforme pour tous les domaines

## Exemples Complets

Voir le fichier `/refactor-sensor-module.plan.md` pour des exemples complets d'implémentation.

