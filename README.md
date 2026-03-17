# CFL Commute

Home Assistant integration for tracking Luxembourg CFL train commutes. Fork of [adamf83/my-rail-commute](https://github.com/adamf83/my-rail-commute).

## Installation

### HACS (Recommended)
1. Open HACS in Home Assistant
2. Go to Integrations
3. Click the three dots → Custom repositories
4. Add `https://github.com/ogerardin/hacs-cfl-commute`
5. Select "Integration"
6. Click Add
7. Restart Home Assistant

### Manual
Copy `custom_components/cfl_commute` to your Home Assistant's `custom_components` folder.

## Configuration

1. Go to Settings → Devices & Services
2. Click Add Integration
3. Search for "CFL Commute"
4. Follow the configuration steps

### API Key
Get a free API key by emailing: `opendata-api@atp.etat.lu`

## Sensors

- `{commute}_summary` - Summary of all tracked trains
- `{commute}_status` - Hierarchical status (Normal → Critical)
- `{commute}_next_train` - Next train details
- `{commute}_train_N` - Individual train sensors
- `{commute}_has_disruption` - Binary sensor for disruptions

## Support

Issues: https://github.com/ogerardin/hacs-cfl-commute/issues

## Running Tests

### Unit tests (no API key required):
```bash
pip install pytest pytest-asyncio aiohttp homeassistant voluptuous
pytest tests/ -v -m "not integration"
```

### Integration tests (requires API key):
```bash
export CFL_API_KEY=your_key_here
pytest tests/test_integration.py -v
```
