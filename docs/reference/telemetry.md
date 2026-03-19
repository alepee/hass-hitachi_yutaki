# Telemetry

## Why?

This integration can collect anonymous performance data to:

- **Ensure stability** — detect regressions and validate fixes across all heat pump models and configurations.
- **Optimize energy consumption** — build realistic datasets that feed future energy-saving features while maintaining comfort.

## What is collected?

No personal information is ever collected. All data is identified by a non-reversible hash — there is no way to trace it back to you or your Home Assistant instance.

| Level | Data | Frequency |
|-------|------|-----------|
| **Off** | Nothing | — |
| **Basic** | Installation info (model, gateway type, configuration) + daily aggregated stats (temperatures, COP, compressor hours) | Once per day |
| **Full** | Everything in Basic + fine-grained metrics (temperatures, compressor frequency, power consumption) + a one-time register snapshot | Metrics every 5 min, snapshot once after opt-in |

## How to change your telemetry level

Go to **Settings → Devices & Services → Hitachi Yutaki → Configure** and select the telemetry step. You can change your level or disable telemetry entirely at any time.

## Community discussion

See [Discussion #200](https://github.com/alepee/hass-hitachi_yutaki/discussions/200) for context and community feedback on this feature.
