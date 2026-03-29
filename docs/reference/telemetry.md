# Telemetry

## Why?

This integration can collect anonymous performance data to:

- **Ensure stability** — detect regressions and validate fixes across all heat pump models and configurations.
- **Optimize energy consumption** — build realistic datasets that feed future energy-saving features while maintaining comfort.

## What is collected?

No personal information is ever collected. All data is identified by a non-reversible hash — there is no way to trace it back to you or your Home Assistant instance.

| Setting | Data | Frequency |
|---------|------|-----------|
| **Off** | Nothing | — |
| **On** | Installation info (model, gateway type, configuration) + fine-grained metrics (temperatures, compressor frequency, power consumption) + daily aggregated stats + a one-time register snapshot | Metrics every 5 min, daily stats once per day, snapshot once after opt-in |

## How to enable or disable telemetry

Go to **Settings → Devices & Services → Hitachi Yutaki → Configure** and select the telemetry step. You can enable or disable telemetry at any time.

## Community discussion

See [Discussion #200](https://github.com/alepee/hass-hitachi_yutaki/discussions/200) for context and community feedback on this feature.
