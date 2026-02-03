# Investigation: Refactoring Détection & Profils

**Date**: 2026-01-27
**Issues liées**: #176, #177, #81, #137, #77
**Statut**: ✅ Clos (2026-02-03)

---

## Contexte

Le système actuel de détection de profil présente plusieurs problèmes:
1. Mapping `unit_model` incorrect (valeurs 1-5 au lieu de 0-3)
2. Yutampo R32 traité comme valeur distincte alors que c'est un S Combi DHW-only
3. Profils ne surchargent pas les capacités (ex: `supports_circuit2` default `True`)
4. `system_config` non utilisé pour valider les features

---

## Architecture cible

### Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────────────┐
│  DOMAIN (pur Python, aucune dépendance)                             │
├─────────────────────────────────────────────────────────────────────┤
│  profiles/                                                          │
│    - Définition des capacités hardware                              │
│    - "Cette machine PEUT avoir DHW jusqu'à 55°C"                    │
│    - "Cette machine PEUT avoir max 1 circuit"                       │
│    - Pas de connaissance Modbus                                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  INFRASTRUCTURE (API/Modbus)                                        │
├─────────────────────────────────────────────────────────────────────┤
│  api/modbus/                                                        │
│    - Lit les registres                                              │
│    - Décode system_config → {has_dhw, has_circuit1, has_cooling...} │
│    - Décode unit_model → int (0-3)                                  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  ORCHESTRATION (Home Assistant)                                     │
├─────────────────────────────────────────────────────────────────────┤
│  config_flow                                                        │
│    - Appelle API → récupère unit_model + config décodée             │
│    - Suggère profil (unit_model + config → profil)                  │
│    - Utilisateur confirme (dernier mot)                             │
│                                                                     │
│  coordinator / __init__                                             │
│    - Charge profil (domain)                                         │
│    - Récupère config décodée (API)                                  │
│    - Intersection: profile.can_X AND config.has_X → features        │
│    - Crée les entités                                               │
└─────────────────────────────────────────────────────────────────────┘
```

### Séparation des responsabilités

| Composant | Connaît | Ne connaît pas |
|-----------|---------|----------------|
| **Profile** (domain) | Capacités hardware | Modbus, HA, config actuelle |
| **API** (infra) | Registres, décodage | Profiles, HA |
| **config_flow/coordinator** (HA) | Profile + API | Détails Modbus internes |

### Flux de configuration

```
CONFIGURATION (config_flow)
│
├─ Lire unit_model + system_config (via API/infra)
├─ Suggérer profil basé sur unit_model + system_config
│    ex: unit_model=1 + DHW only → Yutampo R32
│    ex: unit_model=1 + circuits → Yutaki S Combi
├─ Proposer le profil détecté à l'utilisateur
└─ Utilisateur confirme/corrige → stocké dans config_entry
```

### Flux de démarrage

```
DÉMARRAGE (coordinator/__init__)
│
├─ Charger le profil depuis config_entry
├─ Lire system_config actuel (via API)
├─ Calculer features actives = profil ∩ system_config
└─ Créer entités selon features actives
```

### Logique de création d'entités

```
Profil (statique)         →  Ce que la machine PEUT faire (hardware)
system_config (dynamique) →  Ce qui EST configuré sur cette installation
Entités créées = intersection des deux
```

**Principe retenu**: Le profil définit les limites, system_config active/désactive.
- Permet de détecter des configurations incohérentes (log warning)
- Protège contre des bugs de la gateway
- Documente clairement les capacités de chaque modèle

---

## Registre unit_model (1219) - Mapping corrigé

```
0: Yutaki S
1: Yutaki S Combi
2: Yutaki S80
3: Yutaki M
```

**Cas particulier Yutampo R32**: `unit_model = 1` (S Combi) + DHW seul (pas de circuits chauffage/refroidissement)

---

## Spécificités hardware par modèle

### Tableau récapitulatif

| Propriété | S | S Combi | S80 | M | Yutampo R32 |
|-----------|---|---------|-----|---|-------------|
| **unit_model (reg 1219)** | 0 | 1 | 2 | 3 | 1 (+ DHW only) |
| **DHW intégré** | ❌ | ✅ (220L) | ✅ | ❌ | ✅ (190/270L) |
| **DHW max temp** | - | 55°C | 80°C | - | 55°C (75°C élec) |
| **Max circuits** | 2 | 1 | 2 | 2 | 0 |
| **Cooling possible** | ✅ (kit) | ✅ (kit) | ❌ | ✅ | ❌ |
| **Max sortie eau** | 60°C | 60°C | 80°C | 60°C | - |
| **Compresseur secondaire** | ❌ | ❌ | ✅ (R134a) | ❌ | ❌ |
| **Haute température** | ❌ | ❌ | ✅ | ❌ | ❌ |
| **Boiler backup** | ✅ | ✅ | ❌ | ✅ | ❌ |
| **Pool** | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Type** | Split | Split | Split | Monobloc | Split |

### Détails par modèle

#### Yutaki S
- **Type**: Split (unité intérieure + extérieure)
- **Circuits**: 2 (Circuit 1 direct haute temp, Circuit 2 mixing)
- **DHW**: Non intégré, accessoire optionnel (tank DHWT-200/300S)
- **Cooling**: Avec kit cooling (ATW-CK-01)
- **Température sortie eau**: jusqu'à 60°C
- **Plage fonctionnement**: -25°C à +46°C extérieur

#### Yutaki S Combi
- **Type**: Split avec ballon DHW intégré 220L
- **Circuits**: 1 (option 2nd zone mixing kit ATW-2KT-03)
- **DHW**: Intégré, max 55°C recommandé (57°C absolu par PAC, 60°C avec résistance)
- **Cooling**: Avec kit cooling
- **Température sortie eau**: jusqu'à 60°C
- **Plage fonctionnement**: -25°C à +46°C extérieur

#### Yutaki S80
- **Type**: Split haute température
- **Circuits**: 2
- **DHW**: Intégré ou externe (200L/260L options)
- **DHW max**: 80°C (sans résistance électrique)
- **Cooling**: Non (chauffage uniquement)
- **Température sortie eau**: jusqu'à 80°C même à -20°C extérieur
- **Compresseur**: Cascade R410A + R134a (boost 45°C → 80°C)
- **Usage**: Remplacement chaudière fioul, radiateurs haute temp
- **Bornes de température (manuel S80, PMFR0648 rev.0 - 03/2023, §4.2)**:
  - **Circuit 1/2 (chauffage)**: température de sortie d’eau ≈ **20–80 °C** (plage continue sur le graphe)
  - **DHW**: température ballon ≈ **30–75 °C** (plage continue sur le graphe)
  - **Pool**: température eau piscine **24–33 °C** (plage continue sur le graphe)

#### Yutaki M
- **Type**: Monobloc (unité extérieure uniquement)
- **Circuits**: 2
- **DHW**: Non intégré, ballon externe compatible
- **Cooling**: Oui (natif)
- **Température sortie eau**: jusqu'à 60°C
- **Plage fonctionnement**: -25°C à +46°C extérieur
- **Technologie**: Twin-rotary compressor avec injection vapeur

#### Yutampo R32
- **Type**: Split DHW dédié
- **Circuits**: 0 (pas de chauffage/refroidissement)
- **DHW**: Intégré 190L ou 270L inox
- **DHW max**: 55°C par PAC, 75°C avec résistance électrique
- **Cooling**: Non
- **Détection**: unit_model=1 (S Combi) + system_config sans circuits
- **Temps chauffe**: 3h (190L), 3.5h (270L)

### Limites de détection

**Le registre `system_config` est la seule source pour détecter les options installées.**

Conséquences:
- On ne peut pas distinguer "DHW intégré" vs "DHW accessoire" → si system_config reporte DHW, on le crée
- On ne peut pas savoir si un kit cooling est installé autrement que via system_config
- On ne peut pas détecter le 2nd zone mixing kit autrement que via system_config

**Stratégie retenue:**
1. Le **profil** définit ce qui est *théoriquement possible* pour le hardware
2. Le **system_config** dit ce qui est *réellement configuré*
3. On fait confiance à system_config pour les options (DHW, cooling, circuits)
4. Le profil sert à:
   - Valider la cohérence (warning si config impossible pour ce modèle)
   - Fournir les limites spécifiques (DHW max temp, etc.)
   - Identifier les capacités fixes (compresseur secondaire S80, haute temp, etc.)

**Exemples:**
| Situation | Comportement |
|-----------|--------------|
| Yutaki S + system_config avec DHW | ✅ Créer entités DHW (accessoire installé) |
| Yutaki S + system_config avec 2nd compresseur | ⚠️ Warning log (impossible sur S) |
| Yutaki S80 + system_config avec cooling | ⚠️ Warning log (S80 = heating only) |
| Yutampo R32 + system_config avec circuits | ⚠️ Warning log (DHW only) |

### Sources

- [Hitachi Yutaki S Specifications](https://www.manualslib.com/manual/2011040/Hitachi-Yutaki-S-Series.html)
- [Yutaki S Combi UK](https://www.hitachiaircon.com/uk/ranges/heating/yutaki-s-combi)
- [Yutaki S80 Logicool](https://www.logicool-ac.com/products/yutaki-s80/)
- [Yutaki M UK](https://www.hitachiaircon.com/uk/ranges/heating/yutaki-m)
- [Yutampo R32](https://www.hitachiaircon.com/ranges/heating/yutampo-eco-friendly-water-heater)
- [Installation Manual Yutaki Series](https://documentation.hitachiaircon.com/emea/en/controls/atw-ycc/download/R0000013259_JCH)

---

## Structure de données proposée

### Approche retenue: Classes Python

Les profils sont des classes pures (domain) définissant les capacités hardware:

```python
class HitachiHeatPumpProfile(ABC):
    """Capacités hardware d'un modèle de pompe à chaleur."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Nom du modèle."""

    # DHW
    @property
    def supports_dhw(self) -> bool: ...
    @property
    def dhw_min_temp(self) -> int | None: ...
    @property
    def dhw_max_temp(self) -> int | None: ...

    # Circuits
    @property
    def max_circuits(self) -> int: ...
    @property
    def supports_cooling(self) -> bool: ...
    @property
    def max_water_outlet_temp(self) -> int: ...

    # Équipements
    @property
    def supports_secondary_compressor(self) -> bool: ...
    @property
    def supports_boiler(self) -> bool: ...
    @property
    def supports_pool(self) -> bool: ...
```

---

## Fichiers à modifier

### Domain (profiles/)
- `profiles/base.py` - Enrichir avec nouvelles propriétés
- `profiles/yutaki_s.py` - Implémenter capacités réelles
- `profiles/yutaki_s_combi.py` - Implémenter capacités réelles
- `profiles/yutaki_s80.py` - Implémenter capacités réelles
- `profiles/yutaki_m.py` - Implémenter capacités réelles
- `profiles/yutampo_r32.py` - Implémenter capacités réelles

### Infrastructure (api/)
- `api/modbus/registers/atw_mbs_02.py` - Corriger mapping unit_model (0-3)

### Orchestration (HA)
- `config_flow.py` - Logique de suggestion de profil (unit_model + config)
- `coordinator.py` ou `__init__.py` - Intersection profil × system_config

---

## Sources de données

- [ ] Site Hitachi - Fiches techniques par modèle
- [ ] Documentation ATW-MBS-02
- [ ] Dumps Modbus utilisateurs (discussion #115)

---

## Prochaines étapes

### Complété (beta.8)
1. [x] Compléter le tableau des spécificités hardware (données Hitachi)
2. [x] Corriger mapping unit_model dans `atw_mbs_02.py` (0-3 au lieu de 1-5)
3. [x] Enrichir `profiles/base.py` avec nouvelles propriétés
   - `dhw_min_temp`, `dhw_max_temp`, `max_circuits`, `supports_cooling`
   - `max_water_outlet_temp`, `supports_high_temperature`, `supports_pool`
4. [x] Implémenter chaque profil avec ses vraies capacités
   - Yutaki S: 2 circuits, cooling (kit), 60°C, pool, boiler
   - Yutaki S Combi: 1 circuit, cooling (kit), 60°C, pool, boiler
   - Yutaki S80: 2 circuits, NO cooling, 80°C, high-temp, secondary compressor
   - Yutaki M: 2 circuits, cooling (native), 60°C, pool, boiler
   - Yutampo R32: 0 circuits, DHW only, no pool/boiler
5. [x] Tests unitaires
   - Détection unicité (un seul profil match)
   - Exclusion mutuelle S Combi / Yutampo R32
   - Robustesse données manquantes
   - Cohérence max_circuits / supports_circuit1/2

### Restant (beta.9+)
6. [x] `config_flow.py` - Déjà fonctionnel (auto-détection + dropdown avec suggestion)
7. [~] `coordinator.py` - Intersection profil × config → **ABANDONNÉ** (voir décision ci-dessous)

---

## Décision architecturale : Pas d'intersection profil × system_config

### Contexte

L'idée initiale était de faire une intersection entre les capacités du profil et le `system_config` :
```
Entités créées = profil ∩ system_config
```

### Problème identifié

Cette approche pose problème car :

1. **Le profil est choisi par l'utilisateur** (même si suggéré par auto-détection)
   - Si l'utilisateur choisit le mauvais profil, l'intersection désactiverait des features réellement présentes
   - Exemple : S Combi sélectionné comme "Yutampo R32" → circuits désactivés alors qu'ils existent

2. **`system_config` est la source de vérité**
   - C'est ce que la gateway rapporte comme réellement configuré
   - Si la gateway voit un circuit, il existe physiquement

3. **L'auto-détection se base déjà sur system_config**
   - Le profil est suggéré à partir de `unit_model` + `system_config`
   - Faire une intersection ensuite est redondant

### Décision

**Le profil sert à BORNER, pas à ACTIVER/DÉSACTIVER.**

| Utilisation | Source de vérité |
|-------------|------------------|
| Feature activée (circuit, DHW, pool) | `system_config` |
| Limites de température | `profile` |
| Features hardware fixes (compresseur secondaire) | `profile` |
| Warnings de cohérence | Comparaison `profile` vs `system_config` |

### Implémentation retenue

```python
# coordinator.py
def has_circuit(self, circuit_id, mode) -> bool:
    """Return True if circuit is configured in system_config."""
    return self.api_client.has_circuit(circuit_id, mode)  # Pas d'intersection

# Les entités utilisent le profil pour les LIMITES :
# - climate: min/max temp basés sur profile.max_water_outlet_temp
# - water_heater: min/max temp basés sur profile.dhw_min/max_temp
```

### Warnings de cohérence (optionnel, futur)

On pourrait ajouter des warnings au démarrage si le profil choisi est incohérent avec system_config :
- S80 + cooling dans system_config → Warning "Profile S80 doesn't support cooling"
- Yutampo + circuits dans system_config → Warning "Profile Yutampo is DHW-only"

Ces warnings aideraient au debug sans bloquer les features.

---

## Note pour plus tard : Propriétés `supports_*`

Les propriétés booléennes suivantes existent dans les profils mais **ne sont pas utilisées au runtime** :

```python
supports_circuit1, supports_circuit2  # Redondant avec max_circuits
supports_cooling
supports_dhw
supports_pool
supports_boiler
```

### Propriétés activement utilisées

| Propriété | Utilité |
|-----------|---------|
| `dhw_min_temp`, `dhw_max_temp` | ✅ Borner water_heater |
| `max_water_outlet_temp` | ✅ Borner climate |
| `max_circuits` | ✅ Auto-détection (Yutampo = 0) |
| `supports_secondary_compressor` | ✅ Créer entités compresseur S80 |
| `supports_high_temperature` | ✅ Informatif / UI |
| `extra_register_keys` | ✅ Registres additionnels S80 |

### Décision

On conserve les `supports_*` comme **documentation passive** des capacités hardware. Ils pourront servir plus tard pour :
- Warnings de cohérence profil vs system_config au démarrage
- UI plus intelligente (masquer options impossibles)

**Pas de nettoyage prévu** — le code est clair et documenté.

---

*Clos le 2026-02-03*
