## 🏗️ Principes Architecturaux des Entités

### 1. **Séparation des Responsabilités (SRP)**

**Principe** : Chaque entité a une responsabilité unique et bien définie.

```python
# ✅ Chaque entité a un rôle spécifique
class HitachiYutakiSwitch(SwitchEntity):      # Gestion des switches
class HitachiYutakiSensor(SensorEntity):      # Gestion des capteurs
class HitachiYutakiBinarySensor(BinarySensorEntity):  # Gestion des capteurs binaires
```

**Avantages** :
- **Maintenabilité** : Modifications isolées
- **Testabilité** : Tests unitaires ciblés
- **Évolutivité** : Ajout de nouvelles entités sans impact

### 2. **Configuration par Description (Configuration Pattern)**

**Principe** : Les entités sont configurées via des descriptions déclaratives.

```python
@dataclass
class HitachiYutakiSwitchEntityDescription:
    key: str                                    # Identifiant unique
    name: str                                   # Nom affiché
    get_fn: Callable[[Any, int | None], bool | None]  # Fonction de lecture
    set_fn: Callable[[Any, int | None, bool], bool]  # Fonction d'écriture
    icon: str | None = None                    # Icône optionnelle
    condition: Callable[[HitachiYutakiDataCoordinator], bool] | None = None  # Condition d'affichage
```

**Avantages** :
- **Déclaratif** : Configuration claire et lisible
- **Flexibilité** : Conditions dynamiques
- **Réutilisabilité** : Descriptions partagées

### 3. **Builder Pattern pour les Descriptions**

**Principe** : Construction dynamique des descriptions selon le contexte.

```python
def _build_circuit_switch_description(circuit_id: CIRCUIT_IDS) -> tuple[...]:
    """Build circuit switch descriptions for a specific circuit ID."""
    return (
        HitachiYutakiSwitchEntityDescription(
            key="thermostat",
            name="Thermostat",
            condition=lambda c: c.data.get(f"circuit{circuit_id}_thermostat_available", False),
            get_fn=lambda api, circuit_id: api.get_circuit_thermostat(circuit_id),
            set_fn=lambda api, circuit_id, enabled: api.set_circuit_thermostat(circuit_id, enabled),
        ),
    )
```

**Avantages** :
- **Contextuel** : Descriptions adaptées au contexte
- **Paramétrable** : Fonctions avec paramètres
- **Cohérent** : Pattern uniforme

### 4. **Inversion de Dépendance (DIP)**

**Principe** : Les entités dépendent d'abstractions, pas d'implémentations concrètes.

```python
# ✅ L'entité dépend d'une interface (API)
class HitachiYutakiSwitch:
    def is_on(self) -> bool | None:
        return self._description.get_fn(self._coordinator.api_client, circuit_id)
    
    async def async_turn_on(self):
        await self._description.set_fn(self._coordinator.api_client, circuit_id, True)
```

**Avantages** :
- **Testabilité** : Mocking facile
- **Flexibilité** : Changement d'implémentation
- **Découplage** : Entités indépendantes de l'API

### 5. **Modularité par Domaine**

**Principe** : Organisation par domaine métier dans `entities/`, plateformes HA à la racine.

```
entities/                # Organisation par domaine métier
├── base/                # Classes de base partagées
├── circuit/             # Domaine : circuits chauffage/refroidissement
├── compressor/          # Domaine : compresseurs
├── control_unit/        # Domaine : unité de contrôle
├── dhw/                 # Domaine : eau chaude sanitaire
├── gateway/             # Domaine : passerelle
├── hydraulic/           # Domaine : hydraulique
├── performance/         # Domaine : COP
├── pool/                # Domaine : piscine
├── power/               # Domaine : consommation électrique
└── thermal/             # Domaine : production thermique

sensor.py                # Plateforme HA : appelle les builders
binary_sensor.py         # Plateforme HA : appelle les builders
switch.py                # Plateforme HA : appelle les builders
number.py                # Plateforme HA : appelle les builders
climate.py               # Plateforme HA : appelle les builders
water_heater.py          # Plateforme HA : appelle les builders
```

**Avantages** :
- **Cohésion maximale** : Tout un domaine au même endroit
- **Vue holistique** : Voir tous les types d'entités d'un domaine
- **Maintenabilité** : Modifications localisées par domaine
- **Compréhension** : Structure intuitive par domaine métier
- **Plateformes simples** : Fichiers racine délèguent aux builders

### 6. **Factory Pattern pour la Création**

**Principe** : Création centralisée des entités via des factories.

```python
def _create_switches(
    coordinator: HitachiYutakiDataCoordinator,
    entry_id: str,
    descriptions: tuple[HitachiYutakiSwitchEntityDescription, ...],
    device_type: DEVICE_TYPES,
    register_prefix: str | None = None,
) -> list[HitachiYutakiSwitch]:
    """Create switch entities for a specific device type."""
    entities = []
    for description in descriptions:
        if description.condition is not None and not description.condition(coordinator):
            continue
        entities.append(HitachiYutakiSwitch(...))
    return entities
```

**Avantages** :
- **Centralisation** : Logique de création unique
- **Consistance** : Même processus pour toutes les entités
- **Filtrage** : Conditions appliquées automatiquement

### 7. **Conditions Dynamiques**

**Principe** : Affichage conditionnel basé sur les capacités du système.

```python
# Exemple : Thermostat disponible seulement si configuré
condition=lambda c: c.data.get(f"circuit{circuit_id}_thermostat_available", False)

# Exemple : DHW disponible seulement si configuré
condition=lambda c: c.has_dhw()

# Exemple : Pool disponible seulement si configuré
condition=lambda c: c.has_pool()
```

**Avantages** :
- **Adaptabilité** : Interface adaptée au matériel
- **Simplicité** : Pas de configuration manuelle
- **Robustesse** : Pas d'entités inutiles

### 8. **API Dédiée (Interface Segregation)**

**Principe** : Utilisation de méthodes API spécialisées plutôt que génériques.

```python
# ✅ Méthodes dédiées
get_fn=lambda api, circuit_id: api.get_circuit_thermostat(circuit_id)
set_fn=lambda api, circuit_id, enabled: api.set_circuit_thermostat(circuit_id, enabled)

# ❌ Méthodes génériques (évitées)
# coordinator.data.get(register_key)
# coordinator.api_client.set_register(register_key, value)
```

**Avantages** :
- **Spécialisation** : Logique métier dans l'API
- **Maintenabilité** : Modifications centralisées
- **Sécurité** : Validation dans l'API

### 9. **Gestion des Identifiants**

**Principe** : Identifiants uniques et cohérents pour chaque entité.

```python
def __init__(self, coordinator, description, device_info, register_prefix=None):
    entry_id = coordinator.config_entry.entry_id
    if register_prefix:
        self._attr_unique_id = f"{entry_id}_{register_prefix}_{description.key}"
    else:
        self._attr_unique_id = f"{entry_id}_{description.key}"
```

**Avantages** :
- **Unicité** : Pas de conflits d'identifiants
- **Traçabilité** : Identification claire
- **Persistance** : Entités reconnues après redémarrage

### 10. **Architecture Hexagonale**

**Principe** : Séparation claire entre domaine, adapters et entités.

```
Domain Layer (Business Logic)
├── models/          # Modèles métier
├── ports/           # Interfaces (abstractions)
└── services/        # Logique métier

Adapters Layer (Infrastructure)
├── calculators/     # Implémentations des calculs
├── providers/        # Implémentations des données
└── storage/         # Implémentations du stockage

Entity Layer (Home Assistant)
├── sensor/          # Capteurs
├── switch/          # Interrupteurs
├── binary_sensor/   # Capteurs binaires
└── number/          # Nombres
```

**Avantages** :
- **Testabilité** : Tests unitaires du domaine
- **Flexibilité** : Changement d'infrastructure
- **Maintenabilité** : Logique métier isolée

## 🎯 Bénéfices de cette Architecture

1. **SOLID Principles** : Respect des principes SOLID
2. **Hexagonal Architecture** : Séparation claire des responsabilités
3. **Domain-Driven Design** : Organisation par domaine métier
4. **Testabilité** : Tests unitaires facilités
5. **Maintenabilité** : Modifications localisées
6. **Évolutivité** : Ajout de nouvelles entités simplifié
7. **Robustesse** : Gestion d'erreurs centralisée
8. **Performance** : Optimisations ciblées

Cette architecture garantit un code maintenable, testable et évolutif ! 🚀