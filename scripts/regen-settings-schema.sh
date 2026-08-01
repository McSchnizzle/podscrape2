#!/usr/bin/env bash
# Regenerate the JSON the web UI consumes from the Python source of truth.
# Run after changing src/config/models.py or web_config.py DEFAULTS.
# tests/test_model_roles.py fails if the checked-in file is stale.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/export_settings_schema.py > web_ui_hosted/generated/settings-schema.json
echo "regenerated web_ui_hosted/generated/settings-schema.json"
