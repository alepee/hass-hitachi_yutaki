# Architecture Hitachi Yutaki Integration

## Vue d'ensemble

L'intégration Hitachi Yutaki suit une **architecture hexagonale** (Ports and Adapters) avec une organisation par **domaine métier**.

> 💡 **Note** : Pour les principes architecturaux détaillés et les patterns utilisés, voir [`entities.md`](./entities.md).

## Structure Générale

```
custom_components/hitachi_yutaki/
├── entities/                    # Domaines métier (Architecture hexagonale)
│   ├── base/                    # Classes de base partagées (✅)
│   ├── performance/             # COP (✅)
│   ├── thermal/                 # Production thermique (✅)
│   ├── power/                   # Consommation électrique (✅)
│   ├── gateway/                 # Passerelle (✅)
│   ├── hydraulic/               # Hydraulique (✅)
│   ├── compressor/              # Compresseurs (✅)
│   ├── control_unit/            # Unité de contrôle (✅)
│   ├── circuit/                 # Circuits chauffage/refroidissement (✅)
│   ├── dhw/                     # Eau chaude sanitaire (✅)
│   └── pool/                    # Piscine (✅)
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
├── sensor.py                    # Plateforme HA sensor (✅ Orchestrateur)
├── binary_sensor.py             # Plateforme HA binary_sensor (✅ Orchestrateur)
├── switch.py                    # Plateforme HA switch (✅ Orchestrateur)
├── number.py                    # Plateforme HA number (✅ Orchestrateur)
├── climate.py                   # Plateforme HA climate (✅ Orchestrateur)
├── water_heater.py              # Plateforme HA water_heater (✅ Orchestrateur)
├── select.py                    # Plateforme HA select (✅ Orchestrateur)
└── button.py                    # Plateforme HA button (✅ Orchestrateur)
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
- `sensor.py` : `HitachiYutakiSensor`, `HitachiYutakiSensorEntityDescription`, `_create_sensors()` ✅
- `binary_sensor.py` : `HitachiYutakiBinarySensor`, `HitachiYutakiBinarySensorEntityDescription`, `_create_binary_sensors()` ✅
- `switch.py` : `HitachiYutakiSwitch`, `HitachiYutakiSwitchEntityDescription`, `_create_switches()` ✅
- `number.py` : `HitachiYutakiNumber`, `HitachiYutakiNumberEntityDescription`, `_create_numbers()` ✅
- `climate.py` : `HitachiYutakiClimate`, `HitachiYutakiClimateEntityDescription` ✅
- `water_heater.py` : `HitachiYutakiWaterHeater`, `HitachiYutakiWaterHeaterEntityDescription` ✅
- `select.py` : `HitachiYutakiSelect`, `HitachiYutakiSelectEntityDescription`, `_create_selects()` ✅
- `button.py` : `HitachiYutakiButton`, `HitachiYutakiButtonEntityDescription`, `_create_buttons()` ✅

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

| Domaine | Sensors | Binary Sensors | Switches | Numbers | Climate | Water Heater | Select | Button |
|---------|---------|----------------|----------|---------|---------|--------------|--------|--------|
| gateway | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| hydraulic | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| compressor | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| control_unit | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ |
| circuit | ✅ | ❌ | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| dhw | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ |
| pool | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| performance | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| thermal | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| power | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

## Principes Architecturaux

> 📖 **Voir [`entities.md`](./entities.md)** pour le détail complet des 10 principes architecturaux et patterns utilisés.

### Domaines Métiers

Chaque domaine a une responsabilité unique et claire :

| Domaine | Responsabilité |
|---------|----------------|
| **gateway** | Passerelle de communication |
| **hydraulic** | Circuit hydraulique (pompes, température de l'eau) |
| **compressor** | Compresseurs primaire et secondaire |
| **control_unit** | Unité de contrôle (outdoor, diagnostics) |
| **circuit** | Circuits de chauffage/refroidissement |
| **dhw** | Eau chaude sanitaire |
| **pool** | Piscine |
| **performance** | Performance (COP) |
| **thermal** | Énergie thermique produite |
| **power** | Consommation électrique |

### Architecture en Couches

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

### ✅ Migration Complète (v2.0.0-beta.3)

**Infrastructure & Domain Layer**
- [x] Architecture hexagonale mise en place
- [x] `domain/` : Logique métier pure (models, ports, services)
- [x] `adapters/` : Implémentations infrastructure (calculators, providers, storage)
- [x] `entities/base/` : Classes de base pour tous les types d'entités

**Domaines Métiers**
- [x] `performance/` : Sensors COP (heating, cooling, DHW)
- [x] `thermal/` : Sensors énergie thermique
- [x] `power/` : Sensors consommation électrique
- [x] `gateway/` : Sensors + Binary sensors (connectivité)
- [x] `hydraulic/` : Sensors + Binary sensors (pompes, température)
- [x] `compressor/` : Sensors + Binary sensors (primaire, secondaire)
- [x] `control_unit/` : Sensors + Binary sensors + Switches + Selects
- [x] `circuit/` : Sensors + Numbers + Switches + Climate + Selects
- [x] `dhw/` : Sensors + Binary sensors + Numbers + Switches + Water heater + Buttons
- [x] `pool/` : Sensors + Numbers + Switches

**Plateformes Home Assistant**
- [x] `sensor.py` : Orchestrateur utilisant les builders
- [x] `binary_sensor.py` : Orchestrateur utilisant les builders
- [x] `switch.py` : Orchestrateur utilisant les builders
- [x] `number.py` : Orchestrateur utilisant les builders
- [x] `climate.py` : Orchestrateur utilisant les builders
- [x] `water_heater.py` : Orchestrateur utilisant les builders
- [x] `select.py` : Orchestrateur utilisant les builders
- [x] `button.py` : Orchestrateur utilisant les builders

**Corrections & Améliorations**
- [x] Fix import circulaire dans `entities/base/sensor.py`
- [x] Fix appels `has_circuit()` dans conditions
- [x] Fix assignation devices (DEVICE_CIRCUIT_1/2 au lieu de f"circuit{id}")
- [x] Documentation architecture complète

### 🎯 Prochaines Étapes

- [ ] Tests unitaires pour chaque domaine
- [ ] Tests d'intégration
- [ ] Mettre à jour `CHANGELOG.md` pour v2.0.0
- [ ] Cleanup: Supprimer anciens dossiers obsolètes si existants
- [ ] Linting final et optimisations

## Avantages de cette Architecture

1. **Modularité** : Chaque domaine est indépendant
2. **Testabilité** : Tests unitaires par domaine
3. **Maintenabilité** : Modifications localisées
4. **Compréhension** : Organisation intuitive par domaine métier
5. **Évolutivité** : Ajout de nouveaux domaines facilité
6. **Découplage** : Logique métier indépendante de Home Assistant
7. **Réutilisabilité** : Classes de base partagées
8. **Consistance** : Pattern uniforme pour tous les domaines

## Exemples d'Implémentation

Pour des exemples concrets et détaillés d'implémentation, consultez les fichiers suivants :

- **Patterns de base** : Voir [`entities.md`](./entities.md) (sections 2-9)
- **Domaine simple** : `entities/gateway/sensors.py` (capteurs simples)
- **Domaine complexe** : `entities/circuit/` (tous types d'entités, paramétrage par circuit)
- **Services métier** : `domain/services/cop.py` (calculs COP)
- **Adapters** : `adapters/calculators/electrical.py` (adaptateur de calcul)
