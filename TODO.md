## Tests
- [ ] Add tests for COP calculation

## COP Calculation
- [x] Add quality indicators for COP measurements (no_data, insufficient_data, preliminary, optimal)
- [ ] Add average COP sensor over days
- [ ] Check COP calculation for cooling mode
- [ ] Improve COP quality assessment:
  - Consider measurement stability (variance)
  - Take into account system state (compressor frequency stability)
  - Factor in data source quality (external vs internal sensors)
  - Define clear thresholds for each quality level (no_data, low, medium, high)

## Cleanup
- [ ] Remove unused sensors
- [ ] Split sensors into different files

## Actions
- [ ] Add action to set thermostat temperature
- [ ] Add action to set compressor mode (auto, cooling, heating)
- [ ]
