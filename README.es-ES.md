

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Translation status](https://hosted.weblate.org/widget/hass-hitachi_yutaki/source/svg-badge.svg)](https://hosted.weblate.org/engage/hass-hitachi_yutaki/)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/alepee/hass-hitachi_yutaki)    
[![Validate](https://github.com/alepee/hass-hitachi_yutaki/actions/workflows/validate.yml/badge.svg?branch=main)](https://github.com/alepee/hass-hitachi_yutaki/actions/workflows/validate.yml)
[![Tests](https://github.com/alepee/hass-hitachi_yutaki/actions/workflows/tests.yml/badge.svg)](https://github.com/alepee/hass-hitachi_yutaki/actions/workflows/tests.yml)

# Integración de bombas de calor aire-agua Hitachi para Home Assistant

Esta integración personalizada te permite controlar y supervisar tus bombas de calor aire-agua Hitachi **Yutaki** y **Yutampo** a través de Home Assistant utilizando un gateway Modbus ATW-MBS-02 o HC-A(16/64)MB.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=alepee&category=integration&repository=hass-hitachi_yutaki)

## Compatibilidad

- **Modelos compatibles**: Bombas de calor aire-agua Hitachi (2016 y posteriores totalmente compatibles, anteriores a 2016 en beta)
- **Probado con**: Yutaki S80, Yutaki S, Yutaki S Combi, Yutampo R32
- **Hardware requerido**: Gateway Modbus ATW-MBS-02 o HC-A(16/64)MB

> **Soporte pre-2016 (Beta)**: Las unidades Gen 1 Yutaki S y S Combi (sufijo NWE/NWSE) son compatibles en versión beta. Esta implementación se basa en la documentación de Hitachi pero aún no ha sido validada con hardware real. Si tienes una unidad pre-2016, selecciona "Gen 1" durante la configuración y [infórmarnos de tus resultados](https://github.com/alepee/hass-hitachi_yutaki/discussions). ¿No estás seguro de qué generación tienes? Usa la [herramienta de decodificación de modelos](https://alepee.github.io/hass-hitachi_yutaki/model-decoder.html).

## Características

La integración detecta automáticamente el modelo de tu bomba de calor y crea dispositivos basados en la configuración de tu sistema:

- **Gateway** — supervisión de conectividad y sincronización
- **Unidad de control** — encendido/apagado, modo de operación, temperaturas (exterior, entrada/salida de agua), estado del sistema (descongelación, alarmas, compresor, caldera, bombas), sensores hidráulicos, seguimiento de energía eléctrica y térmica
- **Compresor principal** — frecuencia, corriente, temperaturas (gas, líquido, descarga, evaporador), aperturas de válvula de expansión, tiempos de ciclo
- **Compresor secundario** (solo S80) — frecuencia, corriente, temperaturas, presiones, tiempos de ciclo
- **Circuito 1 y 2** — control climático con modos de calefacción/refrigeración, modo ECO, configuración OTC, función termostática
- **Agua Caliente Sanitaria (ACS)** — control de calentador de agua, modo de refuerzo, tratamiento anti-legionela
- **Piscina** (si está configurada) — control de encendido y temperatura
- **Sensores de COP** — Coeficiente de Rendimiento en tiempo real para calefacción, refrigeración, ACS y piscina con indicadores de calidad

Consulta la [referencia completa de entidades](docs/reference/entities.md) para obtener una lista detallada de cada entidad por dispositivo.

Aspectos adicionales destacados:
- Soporte multilingüe ([ayuda a traducir](https://hosted.weblate.org/engage/hass-hitachi_yutaki/))
- Resistente a problemas de conexión del gateway durante el inicio
- Sugerencias de reparación automatizadas para la desincronización del gateway
- Descripciones completas de alarmas con traducciones
- Configurable: alimentación monofásica/trifásica, sensores externos, intervalos de escaneo

### Modos climáticos del circuito

El comportamiento del circuito depende de la configuración del sistema:
- **Circuito único**: Expone los modos `off` / `heat` / `cool` / `auto` con control de modo global directo
- **Dos circuitos**: Expone `off` / `heat_cool` (solo interruptor de encendido/apagado) — el modo global se controla a través del selector `operation_mode` de la Unidad de control para evitar conflictos entre circuitos

### Supervisión del COP

Cada sensor de COP incluye un atributo `quality` (`no_data`, `insufficient_data`, `preliminary`, `optimal`) que indica la fiabilidad de la medición. Para obtener la mayor precisión posible, configura sensores externos de temperatura del agua; los sensores internos tienen una resolución de 1°C.

La integración soporta dos métodos de cálculo:
- **Sensores externos** (recomendado): utiliza mediciones de temperatura externas precisas con acumulación de energía
- **Sensores internos** (predeterminado): utiliza sensores integrados, mitigando las limitaciones de precisión mediante acumulación basada en el tiempo

### Seguimiento de energía térmica

Seguimiento separado para calefacción y refrigeración:
- **Potencia en tiempo real** (`thermal_power_heating`, `thermal_power_cooling`) en kW
- **Energía diaria** (se reinicia automáticamente a medianoche) en kWh
- **Energía total** (persistente entre reinicios) en kWh

Las mediciones están filtradas: los ciclos de descongelación se excluyen y un bloqueo post-ciclo evita contar el ruido de inercia térmica tras la parada del compresor.

<details>
<summary>Migración desde v1.x</summary>

En la v2.0.0, los siguientes sensores han sido **reemplazados** (las entidades antiguas se migran automáticamente):
- `thermal_power` → `thermal_power_heating`
- `daily_thermal_energy` → `thermal_energy_heating_daily`
- `total_thermal_energy` → `thermal_energy_heating_total`

Los sensores antiguos contabilizaban los ciclos de descongelación como producción de energía, lo que resultaba en valores de COP poco realistas (p. ej., COP > 8). Los nuevos sensores separan correctamente la calefacción de la refrigeración y filtran los períodos de descongelación.
</details>

## Acciones de servicio

### `hitachi_yutaki.set_room_temperature`

Establece el punto de consigna de temperatura para el termostato de habitación de una entidad climática de circuito. Esto es útil cuando el circuito está configurado en modo termostático con un sensor de temperatura de ambiente.

| Parámetro | Requerido | Descripción |
|-----------|----------|-------------|
| `entity_id` | Sí | Entidad climática destino (`climate.circuit_1`, `climate.circuit_2`) |
| `temperature` | Sí | Punto de consigna de temperatura en °C (0–50, paso 0.1) |

**Ejemplo de automatización:**

```yaml
action:
  - action: hitachi_yutaki.set_room_temperature
    target:
      entity_id: climate.circuit_1
    data:
      temperature: 21.5
```

## Instalación

### Instalación mediante HACS (Recomendada)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=alepee&repository=hass-hitachi_yutaki)

1. Añade este repositorio a HACS:
    - Abre HACS en Home Assistant
    - Haz clic en "Integraciones"
    - Haz clic en los tres puntos de la esquina superior derecha
    - Selecciona "Repositorios personalizados"
    - Añade la URL del repositorio: `https://github.com/alepee/hass-hitachi_yutaki`
    - Selecciona la categoría: "Integración"
    - Haz clic en "Añadir"

2. Instala la integración a través de HACS:
    - Haz clic en "Integraciones"
    - Busca "Hitachi Yutaki"
    - Haz clic en "Descargar"
    - Reinicia Home Assistant

### Instalación manual

1. Copia el directorio `custom_components/hitachi_yutaki` al directorio `custom_components` de tu Home Assistant
2. Reinicia Home Assistant

## Desinstalación

1. Ve a **Configuración** > **Dispositivos y Servicios**
2. Busca la integración **Hitachi Heat Pump**
3. Haz clic en el menú de tres puntos y selecciona **Eliminar**
4. Reinicia Home Assistant
5. Si está instalada vía HACS, también puedes eliminar los archivos de la integración a través de HACS > Integraciones > Hitachi Yutaki > Eliminar

## Configuración

> **Nota:** El modo de control central de la bomba de calor NO debe estar configurado en 'Local' (0). Los modos aceptados son: Aire (1), Agua (2) o Total (3). **El modo 'Aire' (1) se recomienda para la mayoría de las instalaciones.** Consulta esta configuración en los parámetros de tu bomba de calor (Configuración del sistema > Opciones generales > Opción de control externo > Modo de control).

El flujo de configuración te guía a través de varios pasos:

1. **Selección de gateway**: Elige tu tipo de gateway (ATW-MBS-02 o HC-A(16/64)MB)
2. **Generación de hardware** (solo ATW-MBS-02): Selecciona tu generación de hardware (Gen 1 o Gen 2+). La integración lo detecta automáticamente tras conectar.
3. **Configuración del gateway**: Detalles de conexión (nombre, IP, puerto, ID esclavo, intervalo de escaneo). El HC-A(16/64)MB también solicita el ID de unidad.
4. **Selección de perfil**: La integración detecta automáticamente el modelo de tu bomba de calor. Puedes anular la detección si es necesario.
5. **Alimentación y sensores**: Tipo de suministro eléctrico (monofásico/trifásico) y entidades externas opcionales para voltaje, potencia, energía y temperaturas del agua (entrada/salida) para cálculos de COP y energía térmica más precisos.

Puedes reconfigurar la integración en cualquier momento a través de **Configuración** > **Dispositivos y Servicios** > **Hitachi Heat Pump** > **Configurar**.

## Telemetría

Esta integración puede recopilar opcionalmente datos de rendimiento anónimos para mejorar el soporte de todos los modelos de bombas de calor. **La telemetría está desactivada de forma predeterminada** y requiere una aceptación explícita.

- **Desactivado** — No se recopilan datos (predeterminado)
- **Activado** — Métricas anónimas cada 5 minutos, estadísticas agregadas diarias y una instantánea única del registro

Todos los datos se identifican mediante un hash irreversible. Nunca se recopila información personal, direcciones IP ni datos de ubicación. Puedes activar o desactivar la telemetría en cualquier momento en las opciones de la integración.

Consulta la [Referencia de Telemetría](docs/reference/telemetry.md) para obtener detalles sobre lo que se recopila y la [Discusión #200](https://github.com/alepee/hass-hitachi_yutaki/discussions/200) para el contexto comunitario.

## Limitaciones conocidas

- **Solo Modbus TCP**: No se admite Modbus serial directo.
- **Modelos pre-2016**: Las bombas de calor Hitachi antiguas utilizan mapas de registros diferentes y no son compatibles.
- **Precisión de temperatura**: Los sensores de temperatura internos tienen una precisión de 1°C. Configura sensores externos para obtener un COP más preciso.
- **Gateway único**: Cada instancia de la integración se conecta a un solo gateway. Varios gateways requieren múltiples instancias.
- **Modo de operación global**: Calefacción/refrigeración/auto se comparte entre todos los circuitos. Con dos circuitos activos, cambia el modo a través del selector `operation_mode` de la Unidad de control.
- **Sin descubrimiento automático**: El gateway debe configurarse manualmente.

## Solución de problemas

### El gateway no puede conectarse

- Verifica que el gateway esté encendido y conectado a tu red
- Comprueba la dirección IP y el puerto (predeterminado: 502) en la configuración de la integración
- Asegúrate de que ningún otro cliente Modbus esté conectado al gateway (solo se admite una conexión)
- Verifica que el ID esclavo de Modbus coincida con la configuración de tu gateway (predeterminado: 1)

### El gateway muestra el estado "Desincronizado"

El gateway ha perdido la sincronización con la bomba de calor. La integración crea un problema de reparación con instrucciones. Causas comunes:
- Interrupción de energía de la bomba de calor
- Problema con el firmware del gateway
- Problema con el cable de comunicación entre el gateway y la bomba de calor

### Las entidades muestran "No disponible"

- Revisa el sensor de conectividad del gateway; si muestra desconectado, consulta "El gateway no puede conectarse"
- La integración se recupera automáticamente cuando el gateway vuelve a estar en línea
- Tras un reinicio de Home Assistant, las entidades pueden mostrar brevemente no disponible mientras se restablece la conexión

### Los valores de COP parecen inexactos

- Revisa el atributo `quality`; se necesita calidad `preliminary` u `optimal` para valores fiables
- Configura sensores externos de temperatura del agua para mayor precisión
- El COP se filtra durante los ciclos de descongelación y tras el apagado del compresor
- Los sensores de COP rastrean la calefacción y el ACS por separado; asegúrate de leer el sensor correcto

### Modo de control de la bomba de calor

El modo de control externo de la bomba de calor NO debe estar configurado en 'Local' (0). Configúralo en Aire (1), Agua (2) o Total (3) a través de: **Configuración del sistema** > **Opciones generales** > **Opción de control externo** > **Modo de control**.

## Desarrollo

Esta integración sigue la **Arquitectura Hexagonal** (Puertos y Adaptadores). Consulta la [documentación para desarrolladores](docs/) para obtener detalles:

- [Arquitectura](docs/architecture.md) — capas, flujo de datos, matriz dominio-entidad
- [Primeros pasos](docs/development/getting-started.md) — configuración, contenedor de desarrollo, objetivos make
- [Añadir entidades](docs/development/adding-entities.md) — guía paso a paso para crear entidades
- [Capa de API y claves de datos](docs/development/api-data-keys.md) — abstracción de API y claves de datos
- [Perfiles](docs/development/profiles.md) — detección de modelos de bombas de calor y capacidades

## Traducciones

Esta integración se traduce utilizando [Weblate](https://hosted.weblate.org/engage/hass-hitachi_yutaki/).

[![Translation status](https://hosted.weblate.org/widget/hass-hitachi_yutaki/source/multi-auto.svg)](https://hosted.weblate.org/engage/hass-hitachi_yutaki/)

Para ayudar a traducir la integración a tu idioma, visita la [página del proyecto en Weblate](https://hosted.weblate.org/engage/hass-hitachi_yutaki/) y comienza a contribuir; ¡no requiere programación!

## Contribuciones

Consulta [CONTRIBUTING.md](CONTRIBUTING.md) para obtener el flujo de trabajo completo para colaboradores.

## Licencia

Este proyecto está bajo la Licencia MIT. Consulta el archivo LICENSE para obtener detalles.

## Créditos

Esta integración fue desarrollada por Antoine Lépée y no está afiliada con Hitachi Ltd.

## Soporte

Para informar errores y solicitar funciones, utiliza la página de [issues de GitHub](https://github.com/alepee/hass-hitachi_yutaki/issues).
