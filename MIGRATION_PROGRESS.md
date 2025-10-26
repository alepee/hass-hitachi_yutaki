# Progression de la Migration - État Actuel

**Date**: 2025-01-24  
**Statut**: 🚧 En cours (environ 40% complété)

## ✅ Complété

### Infrastructure de Base
- ✅ `entities/base/sensor.py` - Classe de base pour sensors
- ✅ `entities/base/binary_sensor.py` - Classe de base pour binary sensors
- ✅ `entities/base/switch.py` - Classe de base pour switches
- ✅ `entities/base/number.py` - Classe de base pour numbers
- ✅ `entities/base/__init__.py` - Exports
- ✅ `entities/__init__.py` - Exports principaux

### Domaines Migrés (100%)
1. ✅ **performance/** - COP sensors (4 sensors)
2. ✅ **thermal/** - Production thermique (3 sensors)
3. ✅ **power/** - Consommation électrique (1 sensor)
4. ✅ **gateway/** - Passerelle (1 sensor + 1 binary_sensor)
5. ✅ **hydraulic/** - Hydraulique (5 sensors + 3 binary_sensors)

### Documentation
- ✅ `documentation/architecture.md` - Architecture complète
- ✅ `documentation/entities.md` - Mise à jour section 5
- ✅ `MIGRATION_STATUS.md` - Tracker détaillé
- ✅ `MIGRATION_PROGRESS.md` - Ce fichier

## 🚧 En Cours

### 6. compressor/ (⏳ Démarré)
- ✅ `entities/compressor/__init__.py`
- ⏳ `entities/compressor/sensors.py` - À CRÉER
- ⏳ `entities/compressor/binary_sensors.py` - À CRÉER

**Source**: `sensor/compressor.py` (PRIMARY + SECONDARY sensors), `binary_sensor/compressor.py`

**Spécificité**: Paramètre `compressor_id` (1 ou 2) et `device_type`

## ⏳ À Faire (Ordre de priorité)

### 7. control_unit/
Fusion de outdoor + diagnostics (alarm, operation_state) + switches + binary_sensors

**Sources**:
- `sensor/outdoor.py` (1 sensor: outdoor_temp)
- `sensor/diagnostics.py` (2 sensors: alarm, operation_state)  
  *Note: power_consumption déjà migré vers power/*
- `switch/control_unit.py` (1 switch: power)
- `binary_sensor/control_unit.py` (5 binary_sensors: defrost, solar, boiler, compressor, smart_function)

**Fichiers à créer**:
- `entities/control_unit/__init__.py`
- `entities/control_unit/sensors.py` - outdoor + alarm + operation_state
- `entities/control_unit/switches.py`
- `entities/control_unit/binary_sensors.py`

### 8. circuit/ (Domaine complexe)
**Sources**:
- Pas de sensors spécifiques (températures circuit dans hydraulic)
- `number/circuit.py` (numbers avec circuit_id)
- `switch/circuit.py` (switches avec circuit_id)
- `climate.py` (extraction logique circuit)

**Fichiers à créer**:
- `entities/circuit/__init__.py`
- `entities/circuit/sensors.py` (vide ou minimal)
- `entities/circuit/numbers.py` - avec paramètre circuit_id
- `entities/circuit/switches.py` - avec paramètre circuit_id  
- `entities/circuit/climate.py` - build_circuit_climate()
- `entities/base/climate.py` - Classe HitachiYutakiClimate (à extraire de climate.py)

### 9. dhw/ (Domaine complexe)
**Sources**:
- `sensor/dhw.py`
- `binary_sensor/dhw.py`
- `number/dhw.py`
- `switch/dhw.py`
- `water_heater.py`

**Fichiers à créer**:
- `entities/dhw/__init__.py`
- `entities/dhw/sensors.py`
- `entities/dhw/binary_sensors.py`
- `entities/dhw/numbers.py`
- `entities/dhw/switches.py`
- `entities/dhw/water_heater.py` - build_dhw_water_heater()
- `entities/base/water_heater.py` - Classe HitachiYutakiWaterHeater (à extraire)

### 10. pool/
**Sources**:
- `sensor/pool.py`
- `number/pool.py`
- `switch/pool.py`

**Fichiers à créer**:
- `entities/pool/__init__.py`
- `entities/pool/sensors.py`
- `entities/pool/numbers.py`
- `entities/pool/switches.py`

## 📝 Plateformes HA à Refactorer

Après migration de tous les domaines :

1. ⏳ `sensor.py` - Importer et appeler tous les `build_*_sensors()`
2. ⏳ `binary_sensor.py` - Importer et appeler tous les `build_*_binary_sensors()`
3. ⏳ `switch.py` - Importer et appeler tous les `build_*_switches()`
4. ⏳ `number.py` - Importer et appeler tous les `build_*_numbers()`
5. ⏳ `climate.py` - Utiliser `build_circuit_climate()`
6. ⏳ `water_heater.py` - Utiliser `build_dhw_water_heater()`

## 🧹 Nettoyage Final

1. ⏳ Supprimer `sensor/` (vérifier que sensor/adapters.py est bien géré)
2. ⏳ Supprimer `binary_sensor/`
3. ⏳ Supprimer `switch/`
4. ⏳ Supprimer `number/`
5. ⏳ Linting complet (`ruff format` + `ruff check`)
6. ⏳ Vérifier imports circulaires
7. ⏳ Tester l'intégration
8. ⏳ Mettre à jour `CHANGELOG.md`

## 🔧 Guide Rapide pour Continuer

### Pattern pour un Domaine Simple

```python
# entities/<domain>/__init__.py
"""<Domain> domain entities."""

from .sensors import build_<domain>_sensors

__all__ = ["build_<domain>_sensors"]
```

```python
# entities/<domain>/sensors.py
"""<Domain> sensor descriptions and builders."""

from __future__ import annotations
from typing import TYPE_CHECKING
from ..base.sensor import HitachiYutakiSensor, HitachiYutakiSensorEntityDescription
from ...const import DEVICE_<TYPE>

if TYPE_CHECKING:
    from ...coordinator import HitachiYutakiDataCoordinator

def build_<domain>_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
) -> list[HitachiYutakiSensor]:
    """Build <domain> sensor entities."""
    from ..base.sensor import _create_sensors
    
    descriptions = _build_<domain>_sensor_descriptions()
    return _create_sensors(coordinator, entry_id, descriptions, DEVICE_<TYPE>)

def _build_<domain>_sensor_descriptions() -> tuple[HitachiYutakiSensorEntityDescription, ...]:
    """Build <domain> sensor descriptions."""
    return (
        # Copier les descriptions depuis sensor/<domain>.py
    )
```

### Pattern pour un Domaine avec Paramètre (ex: compressor)

```python
def build_compressor_sensors(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
    compressor_id: int,  # PARAMÈTRE SPÉCIFIQUE
    device_type: DEVICE_TYPES,
) -> list[HitachiYutakiSensor]:
    """Build compressor sensor entities."""
    from ..base.sensor import _create_sensors
    
    descriptions = _build_compressor_sensor_descriptions(compressor_id)  # PASSER LE PARAMÈTRE
    return _create_sensors(coordinator, entry_id, descriptions, device_type)

def _build_compressor_sensor_descriptions(
    compressor_id: int,  # UTILISER POUR GÉNÉRER LES DESCRIPTIONS
) -> tuple[HitachiYutakiSensorEntityDescription, ...]:
    """Build compressor sensor descriptions."""
    prefix = "primary" if compressor_id == 1 else "secondary"
    
    return (
        HitachiYutakiSensorEntityDescription(
            key=f"{prefix}_compressor_frequency",
            # ... utiliser prefix dans les clés
        ),
    )
```

## 📊 Statistiques

- **Domaines totaux**: 10
- **Domaines migrés**: 5 (50%)
- **Fichiers créés**: ~25
- **Fichiers restants**: ~35
- **Temps estimé restant**: 6-8h

## 🎯 Prochaine Action

Terminer `entities/compressor/` (sensors.py + binary_sensors.py) en suivant le pattern avec paramètre `compressor_id`.

