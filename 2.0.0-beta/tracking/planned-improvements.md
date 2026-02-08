# Améliorations Envisagées - v2.0.0+

Ce document liste les améliorations potentielles pour les futures versions de l'intégration Hitachi Yutaki.

---

## 1. Unique ID basé sur l'adresse MAC pour la Config Entry

**Priorité**: 🔴 Haute
**Complexité**: 🟡 Moyenne
**Version cible**: Beta.8 ou v2.1.0
**GitHub Issue**: [#162](https://github.com/alepee/hass-hitachi_yutaki/issues/162)
**Investigation complète**: [issue-162-mac-based-unique-id.md](../investigations/issue-162-mac-based-unique-id.md)

### Problème actuel

Actuellement, la config entry utilise un unique_id basé sur `{IP}_{slave_id}`, ce qui pose plusieurs problèmes:

1. **Doublons possibles**: Un utilisateur peut créer plusieurs config entries pour la même gateway
2. **Pas de détection de changement d'IP**: Si l'IP de la gateway change (DHCP), HA ne peut pas le détecter automatiquement
3. **Non-conformité**: Home Assistant recommande d'utiliser un identifiant stable (MAC, serial number)

### Solution proposée

Utiliser l'**adresse MAC de la gateway** comme unique_id pour la config entry.

#### Avantages

✅ **Détection de doublons**: Empêche la création de multiples config entries pour la même gateway physique
✅ **Stabilité**: Le unique_id ne change pas même si l'IP change
✅ **Conformité HA**: Respecte les bonnes pratiques recommandées
✅ **Future-proof**: Prépare pour une éventuelle discovery DHCP
✅ **Meilleure UX**: Message clair "Already configured" si tentative de duplication

#### Implémentation technique

##### 1. Récupération de l'adresse MAC

**Via table ARP:**
```python
import subprocess
import re
from typing import Optional

async def async_get_gateway_mac(ip_address: str) -> Optional[str]:
    """Get gateway MAC address from ARP table.

    Args:
        ip_address: IP address of the gateway

    Returns:
        MAC address in format XX:XX:XX:XX:XX:XX or None
    """
    try:
        # Ping to populate ARP cache
        await asyncio.create_subprocess_exec(
            "ping", "-c", "1", "-W", "1", ip_address,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )

        # Read ARP table
        process = await asyncio.create_subprocess_exec(
            "arp", "-n", ip_address,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()

        # Parse MAC address
        mac_pattern = r'([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})'
        match = re.search(mac_pattern, stdout.decode())

        if match:
            mac = match.group(0).replace('-', ':').upper()
            return mac

    except Exception as err:
        _LOGGER.debug("Could not get MAC from ARP: %s", err)

    return None
```

**Note importante:** La gateway ATW-MBS-02 n'expose **pas** son adresse MAC via les registres Modbus. La méthode ARP est la seule méthode viable.

##### 2. Intégration dans config_flow.py

```python
from homeassistant.helpers.device_registry import format_mac

class HitachiYutakiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hitachi Yutaki."""

    VERSION = 2

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Validate connection
            try:
                # Test Modbus connection
                await self._async_test_connection(
                    user_input[CONF_HOST],
                    user_input[CONF_PORT],
                    user_input[CONF_SLAVE]
                )

                # Get gateway MAC address
                mac = await async_get_gateway_mac(user_input[CONF_HOST])

                if mac:
                    # Format MAC and set as unique_id
                    unique_id = format_mac(mac)
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

                    _LOGGER.info("Gateway MAC address: %s", mac)
                else:
                    _LOGGER.warning(
                        "Could not retrieve gateway MAC address. "
                        "Duplicate detection will not be available."
                    )

                # Continue with normal setup
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input
                )

            except Exception as err:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"

        # Show form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=502): int,
                vol.Required(CONF_SLAVE, default=1): int,
            }),
            errors=errors,
        )
```

##### 3. Gestion du changement d'IP (future)

Si on implémente la discovery DHCP plus tard:

```python
async def async_step_dhcp(self, discovery_info):
    """Handle DHCP discovery."""
    # Extract MAC from discovery
    mac = format_mac(discovery_info.macaddress)

    # Set unique_id
    await self.async_set_unique_id(mac)

    # If already configured, update IP silently
    self._abort_if_unique_id_configured(
        updates={CONF_HOST: discovery_info.ip}
    )

    # Otherwise, propose configuration
    self.context["title_placeholders"] = {
        "name": "Hitachi Yutaki",
        "host": discovery_info.ip,
    }

    return await self.async_step_user()
```

#### Considérations

**Compatibilité avec installations existantes:**
- Les installations existantes n'ont pas de unique_id
- Lors de la première exécution post-upgrade, tenter de récupérer le MAC
- Si réussi, ajouter le unique_id à la config entry existante
- Si échec, continuer sans unique_id (mode dégradé)

**Gestion des erreurs:**
- Si la récupération du MAC échoue, logger un warning mais permettre quand même la configuration
- L'unique_id est un "nice to have", pas un bloquant

**Alternative si MAC inaccessible:**
- Utiliser un identifiant basé sur l'IP + slave + timestamp (moins stable)
- Ou ne pas définir de unique_id (comportement actuel)

#### Script de référence

Le script de récupération MAC est disponible dans:
```
/Users/alepee/Documents/Perso/homeassistant/integrations/
  hitachi-yutaki-modus-data-extractor/get_gateway_mac.py
```

Ce script implémente:
- Récupération via ARP
- Formatage pour Home Assistant
- Gestion d'erreurs robuste
- Support multi-plateforme (Linux, macOS, Windows)

#### Tests nécessaires

1. ✅ Récupération MAC sur différents OS (Linux, macOS, Windows)
2. ✅ Détection de doublons (tentative d'ajout 2x)
3. ✅ Comportement si MAC non récupérable
4. ✅ Migration pour installations existantes
5. ✅ Compatibilité avec différentes valeurs de slave_id

#### Documentation utilisateur

Ajouter dans le README:
- Expliquer que l'intégration utilise le MAC comme identifiant
- Mentionner que les doublons sont automatiquement détectés
- Expliquer comment identifier sa gateway si nécessaire

---

## 2. Discovery DHCP pour détection automatique

**Priorité**: 🟡 Moyenne
**Complexité**: 🟢 Faible
**Version cible**: v2.1.0 ou plus tard
**Prérequis**: Amélioration #1 (Unique ID MAC)

### Description

Implémenter la découverte automatique de la gateway via DHCP events.

#### Avantages

- Détection automatique de la gateway sur le réseau
- Mise à jour automatique de l'IP si elle change
- Meilleure expérience utilisateur (moins de configuration manuelle)

#### Prérequis

1. Connaître le **MAC prefix** du fabricant (Hitachi/OEM)
2. Avoir implémenté le unique_id MAC (amélioration #1)

#### Implémentation

```python
# Dans manifest.json
{
  "dhcp": [
    {
      "hostname": "*",
      "macaddress": "XXXXXX*"  # À déterminer: MAC prefix Hitachi
    }
  ]
}
```

#### Limitations

- Nécessite de connaître le MAC prefix du fabricant
- Ne fonctionne que si la gateway est sur le même réseau
- La gateway doit utiliser DHCP ou broadcast

---

## 3. Nettoyage automatique des entités orphelines

**Priorité**: 🟡 Moyenne
**Complexité**: 🟢 Faible
**Version cible**: Beta.8

### Description

Après la migration des entités (issue #8), certaines anciennes entités peuvent rester si la migration a échoué. Implémenter un nettoyage automatique.

#### Implémentation

La fonction existe déjà dans `entity_migration.py`:

```python
async def async_remove_orphaned_entities(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Remove orphaned entities that failed migration."""
```

Il suffit de l'activer dans `__init__.py` après la migration:

```python
# After migration
await async_migrate_entities(hass, entry)

# Optional: Clean up orphans
await async_remove_orphaned_entities(hass, entry)
```

#### Considérations

- Potentiellement destructif (supprime des entités)
- À activer uniquement si demandé par l'utilisateur
- Ou créer une repair issue pour demander confirmation

---

## 4. Statistiques de migration dans les Repairs

**Priorité**: 🟢 Basse
**Complexité**: 🟢 Faible
**Version cible**: Beta.8 ou plus tard

### Description

Créer une repair issue après migration pour informer l'utilisateur du résultat.

#### Exemple

```python
async_create_issue(
    hass,
    DOMAIN,
    f"migration_report_{entry.entry_id}",
    is_fixable=False,
    is_persistent=False,
    severity=IssueSeverity.INFO,
    translation_key="migration_report",
    translation_placeholders={
        "migrated": str(migrations_performed),
        "failed": str(migrations_failed),
    },
)
```

#### Avantages

- Transparence pour l'utilisateur
- Aide au troubleshooting
- Confirme que la migration s'est bien passée

---

## 5. Migration de l'historique Recorder

**Priorité**: 🟢 Basse
**Complexité**: 🔴 Élevée
**Version cible**: Non planifié

### Description

Migrer l'historique des anciennes entités vers les nouvelles dans la base Recorder.

#### Limitations

- Très complexe
- Nécessite manipulation directe de la base de données
- Risques de corruption de données
- Peut-être pas nécessaire (l'historique reste accessible via anciennes entités)

#### Statut

**Non recommandé** pour le moment. L'historique reste accessible car les entity_id ne changent pas lors de la migration des unique_id.

---

## 6. Support du refroidissement (Cooling)

**Priorité**: 🔴 Haute
**Complexité**: 🟡 Moyenne
**Version cible**: Beta.7 ou Beta.8
**Lié à**: [Issue #177 (Consolidated)](https://github.com/alepee/hass-hitachi_yutaki/issues/177)

### Description

Améliorer la détection et le support du refroidissement pour les installations avec cooling hardware.

#### Problèmes actuels

- Auto-détection du refroidissement ne fonctionne pas
- Capteurs de refroidissement ne sont pas créés malgré la présence du hardware
- Régression depuis v1.9.x où le refroidissement fonctionnait correctement
- Voir [Issue #177 (Consolidated)](https://github.com/alepee/hass-hitachi_yutaki/issues/177) pour détails complets

#### Investigation en cours

- Analyse du dump Modbus fourni par tijmenvanstraten
- Identification des registres cooling manquants
- Mise à jour de l'auto-détection

---

## Statut des améliorations

| # | Amélioration | Priorité | Complexité | Statut | Version cible |
|---|-------------|----------|------------|--------|---------------|
| 1 | Unique ID MAC | 🔴 Haute | 🟡 Moyenne | 📋 Planifiée | Beta.8 |
| 2 | Discovery DHCP | 🟡 Moyenne | 🟢 Faible | 💭 À étudier | v2.1.0+ |
| 3 | Nettoyage orphelins | 🟡 Moyenne | 🟢 Faible | ⚙️ Code existe | Beta.8 |
| 4 | Stats migration | 🟢 Basse | 🟢 Faible | 💭 À étudier | Beta.8+ |
| 5 | Migration historique | 🟢 Basse | 🔴 Élevée | ❌ Non recommandé | - |
| 6 | Support cooling | 🔴 Haute | 🟡 Moyenne | 🔍 En investigation | Beta.7/8 |

---

## Notes

- Les améliorations sont listées par ordre d'apparition dans ce document, pas par priorité
- Les priorités et versions cibles peuvent changer selon les retours utilisateurs
- Certaines améliorations dépendent d'autres (voir Prérequis)

---

*Document créé: 2026-01-22*
*Dernière mise à jour: 2026-01-22*
