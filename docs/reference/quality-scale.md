# Home Assistant Quality Scale -- Assessment

**Date**: 2026-03-02
**Version**: 2.0.1+
**Branch**: dev
**Reference**: https://developers.home-assistant.io/docs/core/integration-quality-scale/

> **Note**: The Quality Scale is designed for core Home Assistant integrations.
> Custom integrations are classified as "Custom" and cannot be officially scored.
> This assessment serves as an internal quality reference.

---

## Résultat global

| Tier | Score | Statut |
|------|-------|--------|
| Bronze | 18/18 | Atteint |
| Silver | 6/10 | Non atteint |
| Gold | 7/21 | Non atteint |
| Platinum | 1/3 | Non atteint |

**Niveau actuel : Bronze** (toutes les règles validées)

---

## Bronze (18 règles)

### Règles validées (18/18)

| Règle | Détail |
|-------|--------|
| `config-flow` | Multi-step UI flow complet (4 étapes) |
| `test-before-configure` | Validation connexion Modbus dans le config flow |
| `test-before-setup` | `ConfigEntryNotReady` si connexion échoue au démarrage |
| `unique-config-entry` | `unique_id` hardware via registres Modbus input |
| `entity-unique-id` | Format `{entry_id}_{key}` sur toutes les entités |
| `has-entity-name` | `has_entity_name = True` sur toutes les classes de base |
| `entity-event-setup` | Lifecycle HA respecté via CoordinatorEntity |
| `dependency-transparency` | `requirements` déclaré dans manifest.json |
| `common-modules` | Modules communs : `entities/base/`, `domain/services/`, `adapters/` |
| `action-setup` | Service `set_room_temperature` enregistré dans `climate.py` |
| `appropriate-polling` | DataUpdateCoordinator avec intervalle configurable |
| `docs-high-level-description` | Présent dans README.md |
| `docs-installation-instructions` | Présent dans README.md |
| `docs-actions` | Service documenté dans services.yaml |
| `brands` | Logo et icon dans `brand/` |
| `config-flow-test-coverage` | 12 tests couvrant config flow + options flow (`tests/test_config_flow.py`) |
| `runtime-data` | `ConfigEntry.runtime_data` avec type alias `HitachiYutakiConfigEntry` |
| `docs-removal-instructions` | Section "Uninstall" dans README.md |

---

## Silver (10 règles)

### Règles validées (6)

| Règle | Détail |
|-------|--------|
| `config-entry-unloading` | `async_unload_entry` complet (fermeture API, nettoyage hass.data) |
| `integration-owner` | `@alepee` dans manifest.json |
| `entity-unavailable` | `last_update_success` sur toutes les entités |
| `action-exceptions` | Exceptions levées dans les services |
| `docs-configuration-parameters` | Paramètres décrits dans README |
| `docs-installation-parameters` | Paramètres d'installation décrits dans README |

### Règles non validées (4)

| Règle | Détail | Effort |
|-------|--------|--------|
| `log-when-unavailable` | Log à chaque erreur au lieu d'une seule fois ; pas de log au retour de connexion | Faible |
| `parallel-updates` | `PARALLEL_UPDATES` non défini dans les fichiers plateforme | Faible |
| `reauthentication-flow` | Pas de flow reauth (discutable : Modbus n'a pas d'authentification) | Moyen / N/A |
| `test-coverage` | Couverture < 95% -- tests limités au domain layer | Important |

---

## Gold (21 règles)

### Règles validées (7)

| Règle | Détail |
|-------|--------|
| `devices` | 8 devices créés dynamiquement selon le profil |
| `entity-category` | `EntityCategory.DIAGNOSTIC` utilisé sur les entités avancées |
| `entity-device-class` | `SensorDeviceClass.POWER`, `ENERGY`, `TEMPERATURE`, etc. |
| `entity-disabled-by-default` | Entités avancées désactivées par défaut |
| `entity-translations` | Traductions EN + FR complètes (translations/) |
| `reconfiguration-flow` | Options flow en 4 étapes avec reload automatique |
| `repair-issues` | Repair flows + issue registry (connexion, config manquante, desync) |

### Règles non validées (14)

| Règle | Détail | Effort |
|-------|--------|--------|
| `diagnostics` | Pas de `diagnostics.py` | Moyen |
| `discovery` | Pas de découverte auto (limité par Modbus TCP) | N/A |
| `discovery-update-info` | N/A sans discovery | N/A |
| `dynamic-devices` | Devices statiques à la configuration | N/A |
| `stale-devices` | Pas de nettoyage des devices obsolètes | Faible |
| `icon-translations` | Pas de `icons.json` | Moyen |
| `exception-translations` | Exceptions non traduisibles (`HomeAssistantError` sans `translation_key`) | Moyen |
| `docs-data-update` | Pas de section dédiée dans la documentation | Faible |
| `docs-examples` | Pas d'exemples d'automatisation | Faible |
| `docs-known-limitations` | Pas de section limitations connues | Faible |
| `docs-troubleshooting` | Pas de section dépannage | Faible |
| `docs-use-cases` | Pas de section cas d'usage | Faible |
| `docs-supported-functions` | Partiel -- entités listées mais pas exhaustif | Faible |

---

## Platinum (3 règles)

| Règle | Statut | Détail |
|-------|--------|--------|
| `async-dependency` | Done | pymodbus supporte asyncio |
| `inject-websession` | N/A | Modbus TCP, pas HTTP |
| `strict-typing` | Not done | Type hints présents mais pas de `py.typed` / strict mode |

---

## Plan d'action suggéré

### Pour atteindre Silver (4 actions)

**Quick wins :**
1. `parallel-updates` -- Ajouter `PARALLEL_UPDATES = 0` dans chaque fichier plateforme
2. `log-when-unavailable` -- Logger une seule fois quand indisponible et une fois au retour

**Travail plus conséquent :**
3. `reauthentication-flow` -- Évaluer si pertinent pour Modbus (potentiellement exemptable)
4. `test-coverage` -- Étendre les tests à >95% (config flow, platforms, entities)

### Pour progresser vers Gold

**Quick wins documentation :**
- `docs-data-update`, `docs-examples`, `docs-known-limitations`, `docs-troubleshooting`, `docs-use-cases`, `docs-supported-functions`

**Développement :**
- `diagnostics` -- Implémenter `diagnostics.py` (export config + registres Modbus)
- `icon-translations` -- Créer `icons.json`
- `exception-translations` -- Utiliser `HomeAssistantError` avec `translation_key`
- `stale-devices` -- Nettoyer les devices qui ne sont plus dans le profil
