#!/usr/bin/env python3
"""
cfg.py — YAML-Konfigurationsleser für Makefile-Integration

Verwendung:
    python3 scripts/cfg.py <config_path> <dotted_key>

Beispiel:
    python3 scripts/cfg.py configs/nightly.yaml promotion.pass_rate_exact_openbook_min
    # Ausgabe: 0.6

    python3 scripts/cfg.py configs/nightly.yaml retention.keep
    # Ausgabe: 3

Rückgabe:
    - Wert als String auf stdout (ohne Newline am Ende bei Makefile-kompatiblem Aufruf)
    - Exit 1 bei fehlender Datei, unbekanntem Schlüssel oder Parsefehler

Hinweis:
    - Benötigt PyYAML (auf Host verfügbar: python3 -c "import yaml")
    - Wird ausschließlich durch das Makefile aufgerufen, nicht direkt im Container
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print(
            f"Verwendung: {sys.argv[0]} <config_path> <dotted_key>",
            file=sys.stderr,
        )
        return 1

    config_path = Path(sys.argv[1])
    dotted_key = sys.argv[2]

    if not config_path.exists():
        print(
            f"FEHLER: Konfigurationsdatei nicht gefunden: {config_path}",
            file=sys.stderr,
        )
        return 1

    try:
        import yaml
    except ImportError:
        print(
            "FEHLER: PyYAML nicht verfügbar. Bitte installieren: pip3 install pyyaml",
            file=sys.stderr,
        )
        return 1

    try:
        with config_path.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
    except Exception as exc:
        print(f"FEHLER: YAML-Parsefehler in {config_path}: {exc}", file=sys.stderr)
        return 1

    if not isinstance(cfg, dict):
        print(
            f"FEHLER: YAML-Root muss ein Objekt sein in {config_path}", file=sys.stderr
        )
        return 1

    keys = dotted_key.split(".")
    value = cfg
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            print(
                f"FEHLER: Schlüssel '{dotted_key}' nicht gefunden in {config_path} (Fehler bei '{key}')",
                file=sys.stderr,
            )
            return 1
        value = value[key]

    if value is None:
        print(
            f"FEHLER: Schlüssel '{dotted_key}' hat Wert null in {config_path}",
            file=sys.stderr,
        )
        return 1

    print(value, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
