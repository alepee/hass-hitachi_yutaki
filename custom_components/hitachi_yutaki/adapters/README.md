# Adapters Layer - Architecture Hexagonale

## Vue d'ensemble

Le dossier `adapters/` contient les **implémentations concrètes** des ports définis dans le domain. Ces adapters font le pont entre la logique métier pure et l'infrastructure Home Assistant.

## Principe

Les adapters **implémentent** les interfaces (ports) du domain et **adaptent** les données entre le monde externe (HA) et le domain.

## Structure

```
adapters/
├── calculators/     # Implémentations des calculateurs
├── providers/       # Implémentations des fournisseurs de données
└── storage/         # Implémentations du stockage
```

## Calculators

### `calculators/electrical.py`
- `ElectricalPowerCalculatorAdapter` : Adapte les entités HA vers calcul électrique
- Récupère voltage/power depuis entities HA configurées
- Délègue le calcul à `domain.services.electrical.calculate_electrical_power`

### `calculators/thermal.py`
- `thermal_power_calculator_wrapper` : Wrapper pour calcul thermique
- Adapte la signature pour COPService
- Délègue à `domain.services.thermal.calculate_thermal_power`

## Providers

### `providers/coordinator.py`
- `CoordinatorDataProvider` : Adapte `HitachiYutakiDataCoordinator`
- Implémente `DataProvider` protocol
- Méthodes : `get_water_inlet_temp()`, `get_water_flow()`, etc.

### `providers/entity_state.py`
- `EntityStateProvider` : Adapte les états des entités HA
- Implémente `StateProvider` protocol
- Méthode : `get_float_from_entity(config_key)`

## Storage

### `storage/in_memory.py`
- `InMemoryStorage[T]` : Implémentation en mémoire du stockage
- Implémente `Storage[T]` protocol du domain
- Utilise `collections.deque` pour performance

## Utilisation

### Dans les entities
```python
# Créer les adapters
electrical_adapter = ElectricalPowerCalculatorAdapter(hass, config_entry, power_supply)
thermal_adapter = thermal_power_calculator_wrapper
storage = InMemoryStorage(max_len=100)

# Utiliser avec les services domain
cop_service = COPService(accumulator, thermal_adapter, electrical_adapter)
```

### Dans les tests
```python
# Mock des adapters pour tests
class MockElectricalAdapter:
    def __call__(self, current: float) -> float:
        return current * 0.1  # Mock simple

# Tester avec mocks
cop_service = COPService(accumulator, thermal_adapter, MockElectricalAdapter())
```

## Patterns utilisés

### Adapter Pattern
- Adapte l'interface HA vers l'interface domain
- Masque la complexité de HA au domain

### Strategy Pattern
- Les adapters sont injectés dans les services
- Permet de changer d'implémentation facilement

### Dependency Injection
- Les services reçoivent leurs dépendances
- Facilite les tests et la réutilisabilité

## Règles

1. **TOUJOURS** implémenter les protocols du domain
2. **JAMAIS** exposer la logique métier dans les adapters
3. **TOUJOURS** déléguer les calculs au domain
4. **TOUJOURS** gérer les erreurs HA (unknown, unavailable, etc.)
5. **TOUJOURS** documenter les paramètres d'adaptation

## Avantages

- 🔌 **Découplage** : Domain ne connaît pas HA
- 🧪 **Testabilité** : Mocks faciles à créer
- 🔄 **Réutilisabilité** : Même domain, différents adapters
- 🛠️ **Maintenabilité** : Changement d'HA sans impact domain
- 📊 **Performance** : Adapters optimisés pour leur contexte

## Exemples d'extension

### Nouveau adapter pour base de données
```python
# adapters/storage/database.py
class DatabaseStorage(Storage[T]):
    def __init__(self, connection):
        self._conn = connection
    
    def append(self, item: T) -> None:
        # Sauvegarder en base
        pass
```

### Nouveau adapter pour API externe
```python
# adapters/providers/api.py
class APIDataProvider:
    def get_water_inlet_temp(self) -> float | None:
        # Récupérer depuis API externe
        pass
```

## Migration depuis services/

Les adapters remplacent les anciens `services/` :
- `services/electrical.py` → `adapters/calculators/electrical.py`
- `services/thermal.py` → `adapters/calculators/thermal.py`
- `services/storage/` → `adapters/storage/`

**Avantage** : Séparation claire entre logique métier (domain) et infrastructure (adapters).
