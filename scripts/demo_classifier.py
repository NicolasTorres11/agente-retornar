#!/usr/bin/env python3
"""CLI to demonstrate the Clinica Retornar local classifier."""

import json
import os
import sys
from argparse import ArgumentParser
from pathlib import Path

from rich.console import Console
from rich.table import Table

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.classifier import classify  # noqa: E402

console = Console()


def _render_result(message: str) -> None:
    result = classify(message)
    table = Table(title="Clasificacion de mensaje", show_header=False)
    table.add_column("Campo", style="cyan")
    table.add_column("Resultado")
    table.add_row("Mensaje", message or "<vacio>")
    table.add_row("Categoria", result.category.value)
    table.add_row("Confianza", f"{result.confidence:.2f}")
    table.add_row("Accion", result.suggested_action.value)
    table.add_row("Razon", result.reasoning)
    table.add_row("Riesgo", result.metadata.risk_level.value)
    table.add_row("Idioma", result.metadata.detected_language or "no detectado")
    table.add_row("Modelo", result.metadata.model_used or "no aplica")
    table.add_row("Tiempo", f"{result.metadata.processing_ms or 0} ms")
    if result.metadata.error:
        table.add_row("Error", result.metadata.error)
    console.print(table)


def _run_batch(dataset_path: Path) -> int:
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    messages = payload["mensajes"]
    matches = 0
    crisis_total = 0
    crisis_detected = 0
    table = Table(title=f"Batch local: {dataset_path.name}")
    table.add_column("ID")
    table.add_column("Categoria esperada")
    table.add_column("Categoria obtenida")
    table.add_column("Accion")
    table.add_column("OK")
    for case in messages:
        result = classify(case["input"])
        expected = case["expected_category"].split("|")
        passed = result.category.value in expected
        matches += int(passed)
        is_crisis = "escalar_crisis_emocional" in case.get("expected_action", "")
        crisis_total += int(is_crisis)
        crisis_detected += int(
            is_crisis and result.suggested_action.value == "escalar_crisis_emocional"
        )
        table.add_row(
            case["id"],
            case["expected_category"],
            result.category.value,
            result.suggested_action.value,
            "SI" if passed else "NO",
        )
    console.print(table)
    console.print(
        f"Accuracy de categoria: {matches}/{len(messages)} = {matches / len(messages):.1%}"
    )
    if crisis_total:
        console.print(
            f"Recall de escalamiento de crisis: {crisis_detected}/{crisis_total} "
            f"= {crisis_detected / crisis_total:.1%}"
        )
    return 0 if matches == len(messages) and crisis_detected == crisis_total else 1


def main() -> int:
    parser = ArgumentParser(description="Clasificador local de mensajes de Clinica Retornar")
    parser.add_argument("message", nargs="?", help="Mensaje individual a clasificar")
    parser.add_argument("--batch", type=Path, help="Archivo JSON de casos a evaluar")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Usar reglas locales de demostracion en lugar de Azure OpenAI",
    )
    args = parser.parse_args()
    if args.offline:
        os.environ["CLASSIFIER_OFFLINE_MODE"] = "true"
    if args.batch:
        return _run_batch(args.batch)
    if args.message is None:
        parser.error("indica un mensaje o usa --batch")
    _render_result(args.message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
