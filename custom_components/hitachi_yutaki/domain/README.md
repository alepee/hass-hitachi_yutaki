# Domain Layer - Architecture Hexagonale

## Vue d'ensemble

Le dossier `domain/` contient la **logique métier pure** de l'intégration Hitachi Yutaki. Cette couche est complètement indépendante de Home Assistant et peut être testée sans aucune dépendance externe.

## Principes

- ✅ **Aucune dépendance externe** : Seule la stdlib Python est autorisée
- ✅ **Logique métier pure** : Calculs, algorithmes, règles métier
- ✅ **Testabilité maximale** : Tests unitaires sans mock
- ✅ **Réutilisabilité** : Peut être utilisé par sensor, climate, water_heater, etc.

## Structure

```
domain/
├── models/          # Modèles de données purs (dataclasses)
├── ports/           # Interfaces (Protocols) - contrats
└── services/        # Services métier - logique pure
```

## Models

### `models/cop.py`
- `COPInput` : Données d'entrée pour calcul COP
- `COPQuality` : Indicateur de qualité des mesures
- `PowerMeasurement` : Mesure de puissance avec timestamp

### `models/thermal.py`
- `ThermalPowerInput` : Données d'entrée pour calcul thermique
- `ThermalEnergyResult` : Résultat complet des calculs thermiques

### `models/timing.py`
- `CompressorTimingResult` : Résultats des calculs de timing compresseur

### `models/electrical.py`
- `ElectricalPowerInput` : Données d'entrée pour calcul électrique

## Ports (Interfaces)

### `ports/calculators.py`
- `ThermalPowerCalculator` : Protocol pour calcul de puissance thermique
- `ElectricalPowerCalculator` : Protocol pour calcul de puissance électrique

### `ports/providers.py`
- `DataProvider` : Protocol pour accès aux données de la pompe à chaleur
- `StateProvider` : Protocol pour accès aux états des entités HA

### `ports/storage.py`
- `Storage[T]` : Interface générique pour stockage de données

## Services

### `services/cop.py`
- `COPService` : Service principal pour calcul du COP
- `EnergyAccumulator` : Accumulateur d'énergie pour calculs

### `services/thermal.py`
- `ThermalPowerService` : Service pour calculs thermiques
- `ThermalEnergyAccumulator` : Accumulateur d'énergie thermique
- `calculate_thermal_power()` : Fonction pure de calcul

### `services/timing.py`
- `CompressorTimingService` : Service pour timing compresseur
- `CompressorHistory` : Historique des états compresseur

### `services/electrical.py`
- `calculate_electrical_power()` : Fonction pure de calcul électrique

## Utilisation

### Dans les tests
```python
# Test pur sans dépendance HA
from domain.services.cop import COPService, EnergyAccumulator
from domain.services.thermal import ThermalPowerService

# Créer les services avec des mocks
cop_service = COPService(accumulator, thermal_calc, electrical_calc)
thermal_service = ThermalPowerService(accumulator)

# Tester la logique métier
result = cop_service.get_value()
```

### Dans les adapters
```python
# Les adapters implémentent les ports
from domain.ports.calculators import ElectricalPowerCalculator
from domain.services.electrical import calculate_electrical_power

class MyElectricalAdapter:
    def __call__(self, current: float) -> float:
        return calculate_electrical_power(ElectricalPowerInput(current=current))
```

## Règles strictes

1. **JAMAIS** importer `homeassistant.*`
2. **JAMAIS** importer `adapters.*` ou `entities.*`
3. **JAMAIS** importer des modules externes (sauf stdlib)
4. **TOUJOURS** utiliser des Protocols pour les dépendances
5. **TOUJOURS** documenter les fonctions publiques

## Avantages

- 🧪 **Tests unitaires purs** : Pas de mock HA nécessaire
- 🔄 **Réutilisabilité** : Même logique pour sensor, climate, etc.
- 🐛 **Debugging facile** : Logique isolée et testable
- 📈 **Évolutivité** : Nouveaux services sans impact
- 🏗️ **Architecture propre** : Séparation claire des responsabilités
