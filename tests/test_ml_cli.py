from __future__ import annotations

from app.ml.cli import build_parser


def test_cli_exposes_approved_pipeline_commands():
    parser = build_parser()

    assert parser.parse_args(["dataset", "build", "--since", "2019-01-01", "--universe", "top30-b3"]).handler
    assert parser.parse_args(["nlp", "benchmark", "--dataset", "current-ptbr"]).handler
    assert parser.parse_args(["train", "--dataset", "latest", "--stage", "shadow"]).handler
    assert parser.parse_args(["replay", "--model", "latest-shadow"]).handler
    assert parser.parse_args(["snapshots", "generate", "--model", "latest-shadow"]).handler
    assert parser.parse_args(["promote", "--model", "latest-shadow", "--require-gates"]).handler
