from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from app.ml import HORIZONS
from app.ml.builder import DATASET_SCHEMA_VERSION, materialize_dataset
from app.ml.inference import VersionedForecaster
from app.ml.providers import YahooDatasetProvider
from app.ml.training import train_pooled_horizon
from app.services.asset_universe_service import AssetUniverseService
from app.services.financial_nlp_service import FinancialNLPService, audit_offline_model, benchmark_predictions
from app.services.news_scoring_service import NewsScoringService
from app.services.prediction_repository import PredictionRepository
from app.services.predictive_analysis_service import PredictiveAnalysisService


NLP_CANDIDATES = (
    "ProsusAI/finbert",
    "lucasalmda/pt-br-financial-sentiment-analysis",
    "Kenpache/multilingual-financial-sentiment-v2",
)


def _storage_root(repository: PredictionRepository) -> Path:
    return Path(repository.storage.base_dir)


def _latest_dataset(repository: PredictionRepository) -> dict:
    pointer = repository.storage.load_json("datasets/predictive/latest.json")
    if not pointer:
        raise ValueError("Dataset preditivo ainda nao foi construido")
    return pointer


def _dataset_build(args, *, repository: PredictionRepository | None = None) -> dict:
    if args.universe != "top30-b3":
        raise ValueError("Universo suportado nesta etapa: top30-b3")
    repository = repository or PredictionRepository()
    universe = AssetUniverseService().get_all()
    candidates = [
        (asset.ticker, asset.asset_class)
        for asset in universe
        if asset.asset_class in {"BR_STOCK", "FII"}
    ]
    cutoff = datetime.now(timezone.utc)
    provider = YahooDatasetProvider()
    market = provider.fetch_market(
        candidates,
        since=args.since,
        until=(cutoff.date() + timedelta(days=1)).isoformat(),
    )
    context = provider.fetch_context(
        since=args.since,
        until=(cutoff.date() + timedelta(days=1)).isoformat(),
    )
    macro_path = _storage_root(repository) / "macro" / "releases.parquet"
    macro_releases = pd.read_parquet(macro_path) if macro_path.exists() else None
    sources = provider.source_metadata(cutoff.isoformat())
    sources["macro"] = (
        f"Point-in-time releases: {macro_path.resolve()}"
        if macro_releases is not None
        else "not_included: no audited point-in-time release file"
    )
    result = materialize_dataset(
        market,
        context=context,
        macro_releases=macro_releases,
        output_root=_storage_root(repository) / "datasets" / "predictive",
        cutoff=cutoff.isoformat(),
        sources=sources,
    )
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    pointer = {
        "dataset_hash": result.dataset_hash,
        "dataset_dir": str(result.dataset_dir.resolve()),
        "features_path": str(result.features_path.resolve()),
        "manifest_path": str(result.manifest_path.resolve()),
        "tickers": [item["ticker"] for item in manifest["cohort"]],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    repository.storage.save_json("datasets/predictive/latest.json", pointer)
    return pointer


def _review_dataset_path(repository: PredictionRepository, name: str) -> Path:
    if name == "current-ptbr":
        return _storage_root(repository) / "nlp" / "current-ptbr.json"
    return Path(name)


def _deterministic_labels(records: list[dict]) -> list[str]:
    scorer = NewsScoringService()
    labels = []
    for item in records:
        score = scorer.score_sentiment(str(item["text"]))
        labels.append("positive" if score > 0.1 else "negative" if score < -0.1 else "neutral")
    return labels


def _create_review_dataset(repository: PredictionRepository, path: Path) -> int:
    archive_path = _storage_root(repository) / "news" / "raw" / "archive.json"
    if not archive_path.exists():
        raise ValueError("Arquivo historico de noticias nao encontrado para montar a amostra")
    archive = json.loads(archive_path.read_text(encoding="utf-8-sig"))
    candidates = []
    for item in archive:
        text = " ".join(
            str(item.get(key) or "")
            for key in ("title", "subtitle", "content_preview", "summary")
        ).strip()
        if not text:
            continue
        published = str(item.get("published_at") or "")
        candidates.append(
            {
                "id": str(item.get("id") or hashlib.sha256(text.encode("utf-8")).hexdigest()),
                "text": text[:2000],
                "source": str(item.get("source_name") or item.get("source_id") or "unknown"),
                "ticker": str((item.get("mentioned_assets") or ["MARKET"])[0]),
                "period": published[:7] or "unknown",
            }
        )
    groups: dict[tuple[str, str, str], list[dict]] = {}
    for item in candidates:
        groups.setdefault((item["source"], item["ticker"], item["period"]), []).append(item)
    ordered = []
    while len(ordered) < 300:
        added = False
        for key in sorted(groups):
            if groups[key]:
                ordered.append(groups[key].pop(0))
                added = True
                if len(ordered) == 300:
                    break
        if not added:
            break
    if len(ordered) < 300:
        raise ValueError(f"Corpus insuficiente para amostra PT-BR: {len(ordered)} noticias")
    suggestions = _deterministic_labels(ordered)
    review = [
        {
            **item,
            "suggested_label": suggestion,
            "label": None,
            "review_status": "pending",
        }
        for item, suggestion in zip(ordered, suggestions, strict=True)
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(review)


def _nlp_benchmark(args, *, repository: PredictionRepository | None = None) -> dict:
    repository = repository or PredictionRepository()
    path = _review_dataset_path(repository, args.dataset)
    if not path.exists():
        samples = _create_review_dataset(repository, path)
        raise ValueError(
            f"Amostra com {samples} noticias criada em {path}; revise label e marque review_status=reviewed"
        )
    records = json.loads(path.read_text(encoding="utf-8-sig"))
    if len(records) < 300:
        raise ValueError("O benchmark PT-BR exige no minimo 300 noticias revisadas")
    results = {
        "deterministic": benchmark_predictions(records, _deterministic_labels(records))
    }
    for model_name in NLP_CANDIDATES:
        audit = audit_offline_model(model_name)
        if not audit.get("available_offline") or not audit.get("license_approved"):
            results[model_name] = {**audit, "accepted": False}
            continue
        service = FinancialNLPService(model_name)
        scored = [service.score(str(item["text"])) for item in records]
        if any(item["source"] != "financial_nlp" for item in scored):
            results[model_name] = {**audit, "available_offline": False, "accepted": False}
            continue
        metrics = benchmark_predictions(records, [item["label"] for item in scored])
        metrics.update({**audit, "available_offline": True, "accepted": False})
        results[model_name] = metrics

    baseline_f1 = results["deterministic"]["macro_f1"]
    eligible = [
        (name, result)
        for name, result in results.items()
        if name != "deterministic"
        and result.get("available_offline")
        and result["macro_f1"] >= baseline_f1 + 0.05
    ]
    promoted = max(eligible, key=lambda item: item[1]["macro_f1"], default=(None, None))[0]
    if promoted:
        results[promoted]["accepted"] = True
    report = {
        "dataset": str(path.resolve()),
        "dataset_checksum": hashlib.sha256(path.read_bytes()).hexdigest(),
        "samples": len(records),
        "selected_model": promoted or "deterministic",
        "results": results,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    repository.storage.save_json("nlp/benchmark-latest.json", report)
    return report


def _train(args, *, repository: PredictionRepository | None = None) -> dict:
    if args.stage != "shadow":
        raise ValueError("Novos treinamentos sempre comecam em shadow")
    repository = repository or PredictionRepository()
    pointer = _latest_dataset(repository) if args.dataset == "latest" else {
        "dataset_dir": args.dataset,
        "features_path": str(Path(args.dataset) / "features.parquet"),
        "manifest_path": str(Path(args.dataset) / "manifest.json"),
    }
    manifest = json.loads(Path(pointer["manifest_path"]).read_text(encoding="utf-8"))
    frame = pd.read_parquet(pointer["features_path"])
    results = []
    for asset_class in ("BR_STOCK", "FII"):
        for horizon in HORIZONS:
            trained = train_pooled_horizon(
                frame,
                asset_class=asset_class,
                horizon_days=horizon,
                dataset_hash=manifest["dataset_hash"],
                artifact_root=_storage_root(repository) / "models" / "predictive",
            )
            record = repository.register_model_version(
                {
                    "id": trained.model_version,
                    "model_family": "xgboost_pool",
                    "asset_class": asset_class,
                    "horizon_days": horizon,
                    "artifact_path": str(trained.artifact_path.resolve()),
                    "metadata_path": str(trained.metadata_path.resolve()),
                    "dataset_hash": trained.dataset_hash,
                    "feature_schema_version": DATASET_SCHEMA_VERSION,
                    "metrics": trained.metrics,
                    "status": "shadow",
                }
            )
            results.append(record)
    summary = {
        "dataset_hash": manifest["dataset_hash"],
        "model_ids": [item["id"] for item in results],
        "all_gates_passed": all(not item["metrics"].get("promotion_reasons") for item in results),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    repository.storage.save_json("ai/predictive/latest-shadow.json", summary)
    return summary


def run_scheduled_training(repository: PredictionRepository | None = None) -> dict:
    repository = repository or PredictionRepository()
    dataset = _dataset_build(
        argparse.Namespace(since="2019-01-01", universe="top30-b3"),
        repository=repository,
    )
    training = _train(
        argparse.Namespace(dataset="latest", stage="shadow"),
        repository=repository,
    )
    replay = _replay(
        argparse.Namespace(model="latest-shadow"),
        repository=repository,
    )
    snapshots = _snapshots_generate(
        argparse.Namespace(model="latest-shadow"),
        repository=repository,
    )
    promotion = None
    if replay["all_gates_passed"] and not snapshots["errors"]:
        promotion = _promote(
            argparse.Namespace(model="latest-shadow", require_gates=True),
            repository=repository,
        )
    return {
        "dataset": dataset,
        "training": training,
        "replay": replay,
        "snapshots": snapshots,
        "promotion": promotion,
    }


def _latest_shadow(repository: PredictionRepository) -> tuple[dict, list[dict]]:
    pointer = repository.storage.load_json("ai/predictive/latest-shadow.json")
    if not pointer:
        raise ValueError("Nenhum pacote shadow foi treinado")
    models = [repository.get_model_version(model_id) for model_id in pointer["model_ids"]]
    if any(model is None for model in models):
        raise ValueError("Pacote shadow incompleto")
    return pointer, models


def _replay(args, *, repository: PredictionRepository | None = None) -> dict:
    repository = repository or PredictionRepository()
    if args.model != "latest-shadow":
        raise ValueError("Replay suporta latest-shadow nesta etapa")
    pointer, models = _latest_shadow(repository)
    report = {
        "dataset_hash": pointer["dataset_hash"],
        "models": [
            {
                "id": item["id"],
                "asset_class": item["asset_class"],
                "horizon_days": item["horizon_days"],
                "metrics": item["metrics"],
            }
            for item in models
        ],
        "all_gates_passed": all(not item["metrics"].get("promotion_reasons") for item in models),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    repository.storage.save_json("ai/predictive/replay-latest.json", report)
    return report


def _snapshots_generate(args, *, repository: PredictionRepository | None = None) -> dict:
    repository = repository or PredictionRepository()
    pointer = _latest_dataset(repository)
    stage = "shadow" if args.model == "latest-shadow" else "active"
    service = PredictiveAnalysisService(
        repository=repository,
        forecaster=VersionedForecaster(repository, stage=stage),
    )
    generated, errors = [], []
    assets = AssetUniverseService()
    _, latest_models = _latest_shadow(repository)
    for ticker in pointer["tickers"]:
        asset = assets.get_by_ticker(ticker)
        asset_class = asset.asset_class if asset else "BR_STOCK"
        expected_versions = {
            item["id"]
            for item in latest_models
            if item["asset_class"] == asset_class
        }
        existing_shadow = next(
            (
                item
                for item in repository.list_snapshots(ticker)
                if not item.get("is_active")
                and item.get("payload", {}).get("generation_mode") == "model"
                and set(item.get("model_versions", {}).values()) == expected_versions
            ),
            None,
        )
        if stage == "shadow" and existing_shadow:
            generated.append(ticker)
            continue
        try:
            service.generate(ticker, asset_class, activate=stage == "active")
            generated.append(ticker)
        except Exception as exc:
            errors.append({"ticker": ticker, "error": str(exc)})
    return {"stage": stage, "generated": generated, "errors": errors}


def _promote(args, *, repository: PredictionRepository | None = None) -> dict:
    repository = repository or PredictionRepository()
    if args.model != "latest-shadow":
        raise ValueError("Promocao suporta latest-shadow nesta etapa")
    pointer, models = _latest_shadow(repository)
    model_ids = {item["id"] for item in models}
    dataset = _latest_dataset(repository)
    snapshots_to_activate = []
    for ticker in dataset["tickers"]:
        snapshot = next(
            (
                item
                for item in repository.list_snapshots(ticker)
                if not item.get("is_active")
                and set(item.get("model_versions", {}).values()).issubset(model_ids)
                and item.get("model_versions")
            ),
            None,
        )
        if snapshot:
            snapshots_to_activate.append(snapshot)
    if args.require_gates and len(snapshots_to_activate) != len(dataset["tickers"]):
        raise ValueError("Pacote shadow sem snapshots completos para toda a coorte")
    promoted = repository.promote_model_package(
        [item["id"] for item in models],
        require_gates=args.require_gates,
    )
    promoted_ids = {item["id"] for item in promoted}
    activated_snapshots = []
    for snapshot in snapshots_to_activate:
        if set(snapshot.get("model_versions", {}).values()).issubset(promoted_ids):
            repository.activate_snapshot(snapshot["id"])
            activated_snapshots.append(snapshot["id"])
    return {
        "dataset_hash": pointer["dataset_hash"],
        "promoted": [item["id"] for item in promoted],
        "activated_snapshots": activated_snapshots,
        "activated_at": datetime.now(timezone.utc).isoformat(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.ml.cli")
    commands = parser.add_subparsers(dest="command", required=True)

    dataset = commands.add_parser("dataset").add_subparsers(dest="dataset_command", required=True)
    dataset_build = dataset.add_parser("build")
    dataset_build.add_argument("--since", default="2019-01-01")
    dataset_build.add_argument("--universe", default="top30-b3")
    dataset_build.set_defaults(handler=_dataset_build)

    nlp = commands.add_parser("nlp").add_subparsers(dest="nlp_command", required=True)
    nlp_benchmark = nlp.add_parser("benchmark")
    nlp_benchmark.add_argument("--dataset", default="current-ptbr")
    nlp_benchmark.set_defaults(handler=_nlp_benchmark)

    train = commands.add_parser("train")
    train.add_argument("--dataset", default="latest")
    train.add_argument("--stage", default="shadow")
    train.set_defaults(handler=_train)

    replay = commands.add_parser("replay")
    replay.add_argument("--model", default="latest-shadow")
    replay.set_defaults(handler=_replay)

    snapshots = commands.add_parser("snapshots").add_subparsers(dest="snapshots_command", required=True)
    snapshots_generate = snapshots.add_parser("generate")
    snapshots_generate.add_argument("--model", default="latest-shadow")
    snapshots_generate.set_defaults(handler=_snapshots_generate)

    promote = commands.add_parser("promote")
    promote.add_argument("--model", default="latest-shadow")
    promote.add_argument("--require-gates", action="store_true")
    promote.set_defaults(handler=_promote)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = args.handler(args)
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "ok", "result": result}, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
