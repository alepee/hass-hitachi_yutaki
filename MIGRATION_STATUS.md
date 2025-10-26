# Migration Status : Architecture par Domaine Métier

## Vue d'ensemble

Migration vers une architecture par domaine métier avec organisation dans `entities/`.

**Date de début** : 2025-01-24
**Statut global** : 🚧 En cours (30% complété)

## ✅ Complété

### Phase 1: Structure de Base
- [x] Créer `entities/base/` avec toutes les classes de base
  - [x] `entities/base/sensor.py`
  - [x] `entities/base/binary_sensor.py`
  - [x] `entities/base/switch.py`
  - [x] `entities/base/number.py`
  - [ ] `entities/base/climate.py` (⏳ À FAIRE)
  - [ ] `entities/base/water_heater.py` (⏳ À FAIRE)
- [x] Créer `entities/__init__.py` avec exports principaux

### Phase 2: Domaines Simples (1 type d'entité)
- [x] **Domaine `performance/`** : COP sensors
  - [x] `entities/performance/__init__.py`
  - [x] `entities/performance/sensors.py` avec `build_performance_sensors()`
- [x] **Domaine `thermal/`** : Énergie thermique sensors
  - [x] `entities/thermal/__init__.py`
  - [x] `entities/thermal/sensors.py` avec `build_thermal_sensors()`
- [x] **Domaine `power/`** : Consommation électrique sensors
  - [x] `entities/power/__init__.py`
  - [x] `entities/power/sensors.py` avec `build_power_sensors()`

### Phase 3: Domaines Moyens (2-3 types d'entités)
- [x] **Domaine `gateway/`** : Passerelle
  - [x] `entities/gateway/__init__.py`
  - [x] `entities/gateway/sensors.py` avec `build_gateway_sensors()`
  - [x] `entities/gateway/binary_sensors.py` avec `build_gateway_binary_sensors()`
- [ ] **Domaine `hydraulic/`** : Hydraulique (🚧 PARTIEL)
  - [x] `entities/hydraulic/__init__.py`
  - [ ] `entities/hydraulic/sensors.py` (⏳ À FAIRE)
  - [ ] `entities/hydraulic/binary_sensors.py` (⏳ À FAIRE)

### Documentation
- [x] Créer `documentation/architecture.md` avec structure complète
- [x] Mettre à jour `documentation/entities.md` section 5

## 🚧 En Cours

### Phase 3 (suite)
- [ ] **Domaine `hydraulic/`**
  - [ ] Créer `entities/hydraulic/sensors.py`
  - [ ] Créer `entities/hydraulic/binary_sensors.py`
- [ ] **Domaine `compressor/`**
  - [ ] Créer `entities/compressor/__init__.py`
  - [ ] Créer `entities/compressor/sensors.py` avec `build_compressor_sensors(coordinator, entry_id, compressor_id, device_type)`
  - [ ] Créer `entities/compressor/binary_sensors.py` avec `build_compressor_binary_sensors(coordinator, entry_id, compressor_id, device_type)`
- [ ] **Domaine `control_unit/`**
  - [ ] Créer `entities/control_unit/__init__.py`
  - [ ] Créer `entities/control_unit/sensors.py` (outdoor + diagnostics: alarm, operation_state)
  - [ ] Créer `entities/control_unit/switches.py`
  - [ ] Créer `entities/control_unit/binary_sensors.py`

## ⏳ À Faire

### Phase 4: Domaines Complexes (4+ types d'entités)
- [ ] **Domaine `circuit/`**
  - [ ] Créer `entities/circuit/__init__.py`
  - [ ] Créer `entities/circuit/sensors.py` avec `build_circuit_sensors(coordinator, entry_id, circuit_id, device_type)`
  - [ ] Créer `entities/circuit/numbers.py` avec `build_circuit_numbers(coordinator, entry_id, circuit_id, device_type)`
  - [ ] Créer `entities/circuit/switches.py` avec `build_circuit_switches(coordinator, entry_id, circuit_id, device_type)`
  - [ ] Créer `entities/circuit/climate.py` avec `build_circuit_climate(coordinator, entry_id, circuit_id, device_type) -> HitachiYutakiClimate | None`
- [ ] **Domaine `dhw/`**
  - [ ] Créer `entities/dhw/__init__.py`
  - [ ] Créer `entities/dhw/sensors.py`
  - [ ] Créer `entities/dhw/binary_sensors.py`
  - [ ] Créer `entities/dhw/numbers.py`
  - [ ] Créer `entities/dhw/switches.py`
  - [ ] Créer `entities/dhw/water_heater.py` avec `build_dhw_water_heater(coordinator, entry_id) -> HitachiYutakiWaterHeater | None`
- [ ] **Domaine `pool/`**
  - [ ] Créer `entities/pool/__init__.py`
  - [ ] Créer `entities/pool/sensors.py`
  - [ ] Créer `entities/pool/numbers.py`
  - [ ] Créer `entities/pool/switches.py`

### Phase 5: Mise à Jour des Plateformes HA
- [ ] Refactorer `sensor.py` pour utiliser les builders de tous les domaines
- [ ] Refactorer `binary_sensor.py` pour utiliser les builders
- [ ] Refactorer `switch.py` pour utiliser les builders
- [ ] Refactorer `number.py` pour utiliser les builders
- [ ] Refactorer `climate.py` pour utiliser `build_circuit_climate()`
- [ ] Refactorer `water_heater.py` pour utiliser `build_dhw_water_heater()`

### Phase 6: Nettoyage et Finalisation
- [ ] Supprimer `sensor/` (après vérification)
- [ ] Supprimer `binary_sensor/` (après vérification)
- [ ] Supprimer `switch/` (après vérification)
- [ ] Supprimer `number/` (après vérification)
- [ ] Déplacer `sensor/adapters.py` vers `entities/base/` si nécessaire
- [ ] Linting complet (`ruff format` + `ruff check`)
- [ ] Vérifier imports circulaires
- [ ] Tester import de l'intégration
- [ ] Mettre à jour `CHANGELOG.md`

## Notes Techniques

### Pattern des Builders

Chaque domaine expose des fonctions builder :

```python
def build_<domain>_<entity_type>(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
    # Paramètres spécifiques (circuit_id, compressor_id, etc.)
) -> list[Entity]:
    """Build <entity_type> entities for <domain>."""
    from ..base.<entity_type> import _create_<entity_type>s

    descriptions = _build_<domain>_<entity_type>_descriptions()
    return _create_<entity_type>s(coordinator, entry_id, descriptions, DEVICE_TYPE)
```

### Domaines avec Paramètres

Certains domaines nécessitent des paramètres spécifiques :

- **compressor** : `compressor_id` (1 ou 2), `device_type`
- **circuit** : `circuit_id` (1 ou 2), `device_type`

Exemple :
```python
entities.extend(
    build_compressor_sensors(
        coordinator,
        entry.entry_id,
        compressor_id=1,
        device_type=DEVICE_PRIMARY_COMPRESSOR,
    )
)
```

### Fusion de Domaines

- **control_unit** fusionne :
  - `sensor/outdoor.py` (températures extérieures)
  - `sensor/diagnostics.py` (alarm, operation_state uniquement)
  - `switch/control_unit.py` (power)
  - `binary_sensor/control_unit.py` (defrost, solar, boiler, etc.)

- **power** extrait de :
  - `sensor/diagnostics.py` (power_consumption uniquement)

## Prochaines Étapes

1. Compléter `entities/hydraulic/`
2. Créer `entities/compressor/`
3. Créer `entities/control_unit/`
4. Créer `entities/circuit/` (domaine complexe)
5. Créer `entities/dhw/` (domaine complexe)
6. Créer `entities/pool/`
7. Refactorer toutes les plateformes HA
8. Nettoyage et tests

## Temps Estimé Restant

- Domaines moyens : ~2h
- Domaines complexes : ~4h
- Refactoring plateformes : ~2h
- Nettoyage et tests : ~1h

**Total estimé** : ~9h de travail restant
