# Home Assistant Quality Scale — Assessment

**Date**: 2026-02-08
**Version**: 2.0.0-beta.12
**Branch**: beta/2.0.0
**Reference**: https://developers.home-assistant.io/docs/core/integration-quality-scale/

> **Note** : Le Quality Scale est concu pour les integrations **core** de Home Assistant.
> Les integrations custom sont classees "Custom" et ne peuvent pas etre officiellement scorees.
> Cette evaluation sert de reference qualite interne.

---

## Resultat global

| Tier | Score | Statut |
|------|-------|--------|
| Bronze | 14/18 | Non atteint |
| Silver | 6/10 | Non atteint |
| Gold | 7/21 | Non atteint |
| Platinum | 1/3 | Non atteint |

**Niveau actuel : juste en-dessous de Bronze** (4 regles manquantes)

---

## Bronze (18 regles)

### Regles validees (14)

| Regle | Detail |
|-------|--------|
| `config-flow` | Multi-step UI flow complet (4 etapes) |
| `test-before-configure` | Validation connexion Modbus dans le config flow |
| `test-before-setup` | `ConfigEntryNotReady` si connexion echoue au demarrage |
| `unique-config-entry` | `unique_id` hardware via registres Modbus input |
| `entity-unique-id` | Format `{entry_id}_{key}` sur toutes les entites |
| `has-entity-name` | `has_entity_name = True` sur toutes les classes de base |
| `entity-event-setup` | Lifecycle HA respecte via CoordinatorEntity |
| `dependency-transparency` | `requirements` declare dans manifest.json |
| `common-modules` | Modules communs : `entities/base/`, `domain/services/`, `adapters/` |
| `action-setup` | Service `set_room_temperature` enregistre dans `climate.py` |
| `appropriate-polling` | DataUpdateCoordinator avec intervalle configurable |
| `docs-high-level-description` | Present dans README.md |
| `docs-installation-instructions` | Present dans README.md |
| `docs-actions` | Service documente dans services.yaml |

### Regles non validees (4)

| Regle | Detail | Effort |
|-------|--------|--------|
| `brands` | Pas d'assets branding (logo/icon) | Faible |
| `config-flow-test-coverage` | Pas de tests pour le config flow | Important |
| `runtime-data` | Utilise `hass.data[DOMAIN]` au lieu de `ConfigEntry.runtime_data` | Moyen |
| `docs-removal-instructions` | Pas d'instructions de suppression dans README | Faible |

---

## Silver (10 regles)

### Regles validees (6)

| Regle | Detail |
|-------|--------|
| `config-entry-unloading` | `async_unload_entry` complet (fermeture API, nettoyage hass.data) |
| `integration-owner` | `@alepee` dans manifest.json |
| `entity-unavailable` | `last_update_success` sur toutes les entites |
| `action-exceptions` | Exceptions levees dans les services |
| `docs-configuration-parameters` | Parametres decrits dans README |
| `docs-installation-parameters` | Parametres d'installation decrits dans README |

### Regles non validees (4)

| Regle | Detail | Effort |
|-------|--------|--------|
| `log-when-unavailable` | Log a chaque erreur au lieu d'une seule fois ; pas de log au retour de connexion | Faible |
| `parallel-updates` | `PARALLEL_UPDATES` non defini dans les fichiers plateforme | Faible |
| `reauthentication-flow` | Pas de flow reauth (discutable : Modbus n'a pas d'authentification) | Moyen / N/A |
| `test-coverage` | Couverture < 95% — tests limites au domain layer | Important |

---

## Gold (21 regles)

### Regles validees (7)

| Regle | Detail |
|-------|--------|
| `devices` | 8 devices crees dynamiquement selon le profil |
| `entity-category` | `EntityCategory.DIAGNOSTIC` utilise sur les entites avancees |
| `entity-device-class` | `SensorDeviceClass.POWER`, `ENERGY`, `TEMPERATURE`, etc. |
| `entity-disabled-by-default` | Entites avancees desactivees par defaut |
| `entity-translations` | Traductions EN + FR completes (translations/) |
| `reconfiguration-flow` | Options flow en 4 etapes avec reload automatique |
| `repair-issues` | Repair flows + issue registry (connexion, config manquante, desync) |

### Regles non validees (14)

| Regle | Detail | Effort |
|-------|--------|--------|
| `diagnostics` | Pas de `diagnostics.py` | Moyen |
| `discovery` | Pas de decouverte auto (limite par Modbus TCP) | N/A |
| `discovery-update-info` | N/A sans discovery | N/A |
| `dynamic-devices` | Devices statiques a la configuration | N/A |
| `stale-devices` | Pas de nettoyage des devices obsoletes | Faible |
| `icon-translations` | Pas de `icons.json` | Moyen |
| `exception-translations` | Exceptions non traduisibles (`HomeAssistantError` sans `translation_key`) | Moyen |
| `docs-data-update` | Pas de section dediee dans la documentation | Faible |
| `docs-examples` | Pas d'exemples d'automatisation | Faible |
| `docs-known-limitations` | Pas de section limitations connues | Faible |
| `docs-troubleshooting` | Pas de section depannage | Faible |
| `docs-use-cases` | Pas de section cas d'usage | Faible |
| `docs-supported-functions` | Partiel — entites listees mais pas exhaustif | Faible |

---

## Platinum (3 regles)

| Regle | Statut | Detail |
|-------|--------|--------|
| `async-dependency` | ✅ | pymodbus supporte asyncio |
| `inject-websession` | N/A | Modbus TCP, pas HTTP |
| `strict-typing` | ❌ | Type hints presents mais pas de `py.typed` / strict mode |

---

## Plan d'action suggere

### Pour atteindre Bronze (4 actions)

**Quick wins :**
1. `brands` — Ajouter logo et icon dans le repo
2. `docs-removal-instructions` — Ajouter une section "Uninstall" dans README

**Travail plus consequent :**
3. `runtime-data` — Migrer de `hass.data[DOMAIN][entry_id]` vers `ConfigEntry.runtime_data`
4. `config-flow-test-coverage` — Ecrire des tests couvrant tout le config flow

### Pour atteindre Silver (4 actions supplementaires)

**Quick wins :**
1. `parallel-updates` — Ajouter `PARALLEL_UPDATES = 0` dans chaque fichier plateforme
2. `log-when-unavailable` — Logger une seule fois quand indisponible et une fois au retour

**Travail plus consequent :**
3. `reauthentication-flow` — Evaluer si pertinent pour Modbus (potentiellement exemptable)
4. `test-coverage` — Etendre les tests a >95% (config flow, platforms, entities)

### Pour progresser vers Gold

**Quick wins documentation :**
- `docs-data-update`, `docs-examples`, `docs-known-limitations`, `docs-troubleshooting`, `docs-use-cases`, `docs-supported-functions`

**Developpement :**
- `diagnostics` — Implementer `diagnostics.py` (export config + registres Modbus)
- `icon-translations` — Creer `icons.json`
- `exception-translations` — Utiliser `HomeAssistantError` avec `translation_key`
- `stale-devices` — Nettoyer les devices qui ne sont plus dans le profil
