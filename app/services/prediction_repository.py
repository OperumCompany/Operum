from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import math
import pandas as pd

from app.db.postgres import PostgresClient
from app.services.local_storage_service import LocalStorageService


class PredictionRepository:
    def __init__(
        self,
        db: PostgresClient | None = None,
        storage: LocalStorageService | None = None,
    ):
        self.db = db or PostgresClient()
        self.storage = storage or LocalStorageService()
        self._snapshots_path = "ai/predictive/snapshots.json"
        self._active_path = "ai/predictive/active_snapshots.json"
        self._jobs_path = "ai/predictive/jobs.json"
        self._models_path = "ai/predictive/model_versions.json"
        self._outcomes_path = "ai/predictive/prediction_outcomes.json"

    def _predictive_model_root(self) -> Path:
        return Path(self.storage.base_dir) / "models" / "predictive"

    def _resolve_model_paths(self, record: dict | None) -> dict | None:
        """Resolve model paths after moving artifacts between worktrees.

        Older experiment metadata can contain absolute paths from a temporary
        worktree. Serving should use the copied local artifacts when the file
        name and model id match.
        """
        if not record:
            return None
        payload = dict(record)
        model_id = str(payload.get("id") or "")
        for key in ("artifact_path", "metadata_path"):
            raw = payload.get(key)
            if not raw:
                continue
            candidate = Path(str(raw))
            if candidate.is_file():
                payload[key] = str(candidate)
                continue
            fallback = self._predictive_model_root() / model_id / candidate.name
            if fallback.is_file():
                payload[key] = str(fallback)
        return payload

    @staticmethod
    def _finite_float(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    def _serving_candidate_score(self, record: dict) -> float:
        """Positive score means the shadow XGBoost is usable for serving.

        This is intentionally simpler than formal promotion gates: it only
        decides whether a locally available shadow model can replace the
        baseline preditor for development snapshots.
        """
        resolved = self._resolve_model_paths(record) or {}
        metadata_path = resolved.get("metadata_path")
        if not metadata_path or not Path(str(metadata_path)).is_file():
            return float("-inf")
        if str(resolved.get("model_family")) != "xgboost_pool":
            return float("-inf")
        metrics = resolved.get("metrics") or {}
        holdout = metrics.get("holdout") or {}
        holdout_baseline = metrics.get("holdout_baseline") or {}
        candidate_mae = self._finite_float(holdout.get("mae"))
        baseline_mae = self._finite_float(holdout_baseline.get("mae"))
        directional = self._finite_float(holdout.get("directional_accuracy"))
        coverage = self._finite_float(metrics.get("holdout_interval_coverage"))
        if (
            candidate_mae is None
            or baseline_mae is None
            or baseline_mae <= 0
            or directional is None
            or candidate_mae >= baseline_mae
            or directional < 0.52
        ):
            return float("-inf")
        coverage_penalty = 0.0 if coverage is None else abs(coverage - 0.80) * 0.10
        return ((baseline_mae - candidate_mae) / baseline_mae) - coverage_penalty

    @staticmethod
    def _outcome_rows(snapshot: dict) -> list[dict]:
        cutoff = pd.Timestamp(snapshot["data_cutoff"])
        labels = {"1m": 21, "2m": 42, "3m": 63}
        rows = []
        for label, days in labels.items():
            horizon = snapshot.get("payload", {}).get("horizons", {}).get(label)
            if not horizon:
                continue
            returns = horizon.get("return_range", {})
            if "expected_return" not in horizon or not {"adverse", "favorable"}.issubset(returns):
                continue
            rows.append(
                {
                    "snapshot_id": snapshot["id"],
                    "ticker": snapshot["ticker"],
                    "horizon_days": days,
                    "target_date": (cutoff + pd.offsets.BDay(days)).date().isoformat(),
                    "predicted_return": float(horizon["expected_return"]),
                    "lower_return": float(returns["adverse"]),
                    "upper_return": float(returns["favorable"]),
                    "actual_return": None,
                    "scored_at": None,
                }
            )
        return rows

    @property
    def enabled(self) -> bool:
        return bool(self.db.enabled)

    def ensure_schema(self) -> None:
        if not self.enabled:
            return
        statements = [
            """
            create table if not exists public.model_versions (
              id uuid primary key,
              model_family text not null,
              asset_class text not null,
              horizon_days integer not null,
              artifact_path text not null,
              metadata_path text not null,
              dataset_hash text not null,
              feature_schema_version text not null,
              metrics jsonb not null default '{}'::jsonb,
              status text not null check (status in ('shadow','active','rejected','archived')),
              created_at timestamptz not null default timezone('utc', now()),
              activated_at timestamptz
            )
            """,
            """
            create unique index if not exists idx_model_versions_one_active
            on public.model_versions(asset_class,horizon_days) where status='active'
            """,
            """
            create table if not exists public.asset_analysis_snapshots (
              id uuid primary key,
              ticker text not null,
              data_cutoff timestamptz not null,
              news_fingerprint text not null default '',
              model_versions jsonb not null default '{}'::jsonb,
              payload jsonb not null,
              generation_mode text not null,
              is_active boolean not null default false,
              created_at timestamptz not null default timezone('utc', now())
            )
            """,
            """
            create unique index if not exists idx_asset_analysis_one_active
            on public.asset_analysis_snapshots(ticker) where is_active
            """,
            """
            create index if not exists idx_asset_analysis_ticker_created
            on public.asset_analysis_snapshots(ticker, created_at desc)
            """,
            """
            create table if not exists public.analysis_jobs (
              id uuid primary key,
              ticker text not null,
              reason text not null,
              dedupe_key text not null unique,
              status text not null check (status in ('pending','running','completed','failed')),
              priority integer not null default 0,
              attempts integer not null default 0,
              run_after timestamptz not null default timezone('utc', now()),
              error text,
              created_at timestamptz not null default timezone('utc', now()),
              updated_at timestamptz not null default timezone('utc', now())
            )
            """,
            """
            create index if not exists idx_analysis_jobs_claim
            on public.analysis_jobs(status, run_after, priority desc, created_at)
            """,
            """
            create table if not exists public.prediction_outcomes (
              snapshot_id uuid not null references public.asset_analysis_snapshots(id) on delete cascade,
              ticker text not null,
              horizon_days integer not null,
              target_date date not null,
              predicted_return real not null,
              lower_return real not null,
              upper_return real not null,
              actual_return real,
              scored_at timestamptz,
              primary key (snapshot_id, horizon_days)
            )
            """,
        ]
        for statement in statements:
            self.db.execute(statement)

    def register_model_version(self, record: dict) -> dict:
        payload = dict(record)
        payload.setdefault("id", str(uuid.uuid4()))
        payload.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        if self.enabled:
            row = self.db.fetch_one(
                """
                insert into public.model_versions (
                  id, model_family, asset_class, horizon_days, artifact_path, metadata_path,
                  dataset_hash, feature_schema_version, metrics, status, created_at
                ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict (id) do update set
                  artifact_path=excluded.artifact_path,
                  metrics=excluded.metrics,
                  status=excluded.status
                returning *
                """,
                (
                    payload["id"], payload["model_family"], payload["asset_class"],
                    payload["horizon_days"], payload["artifact_path"], payload["metadata_path"], payload["dataset_hash"],
                    payload["feature_schema_version"], payload.get("metrics", {}),
                    payload.get("status", "shadow"), payload["created_at"],
                ),
            )
            return dict(row or payload)
        models = self.storage.load_json(self._models_path) or []
        models = [item for item in models if item["id"] != payload["id"]]
        models.append(payload)
        self.storage.save_json(self._models_path, models)
        return payload

    def get_model_version(self, model_id: str) -> dict | None:
        if self.enabled:
            row = self.db.fetch_one("select * from public.model_versions where id=%s", (model_id,))
            return self._resolve_model_paths(dict(row)) if row else None
        return self._resolve_model_paths(next(
            (item for item in (self.storage.load_json(self._models_path) or []) if item["id"] == model_id),
            None,
        ))

    def get_active_model(self, asset_class: str, horizon_days: int) -> dict | None:
        if self.enabled:
            row = self.db.fetch_one(
                """
                select * from public.model_versions
                where asset_class=%s and horizon_days=%s and status='active'
                order by activated_at desc limit 1
                """,
                (asset_class, horizon_days),
            )
            return self._resolve_model_paths(dict(row)) if row else None
        return self._resolve_model_paths(next(
            (
                item for item in reversed(self.storage.load_json(self._models_path) or [])
                if item["asset_class"] == asset_class
                and int(item["horizon_days"]) == int(horizon_days)
                and item["status"] == "active"
            ),
            None,
        ))

    def get_serving_model(self, asset_class: str, horizon_days: int) -> dict | None:
        """Returns the active XGBoost for the slot, or the best usable shadow one.

        If no XGBoost can beat the baseline with valid holdout metrics, callers
        keep using BaselineForecaster. That baseline is still the active
        preditor, not an empty analysis.
        """
        active = self.get_active_model(asset_class, horizon_days)
        if active:
            return active
        candidates = [
            item
            for item in self.list_model_versions(status="shadow")
            if item.get("asset_class") == asset_class
            and int(item.get("horizon_days", 0)) == int(horizon_days)
        ]
        scored = [
            (self._serving_candidate_score(item), self._resolve_model_paths(item))
            for item in candidates
        ]
        scored = [(score, item) for score, item in scored if item and score > 0]
        if not scored:
            return None
        return max(scored, key=lambda pair: pair[0])[1]

    def list_model_versions(
        self,
        *,
        status: str | None = None,
        dataset_hash: str | None = None,
    ) -> list[dict]:
        if self.enabled:
            clauses = []
            params: list[Any] = []
            if status:
                clauses.append("status=%s")
                params.append(status)
            if dataset_hash:
                clauses.append("dataset_hash=%s")
                params.append(dataset_hash)
            where = " where " + " and ".join(clauses) if clauses else ""
            return [
                self._resolve_model_paths(dict(row)) or dict(row)
                for row in self.db.fetch_all(
                    f"select * from public.model_versions{where} order by created_at desc",
                    tuple(params),
                )
            ]
        rows = list(self.storage.load_json(self._models_path) or [])
        if status:
            rows = [item for item in rows if item.get("status") == status]
        if dataset_hash:
            rows = [item for item in rows if item.get("dataset_hash") == dataset_hash]
        rows = [self._resolve_model_paths(item) or item for item in rows]
        return sorted(rows, key=lambda item: item.get("created_at", ""), reverse=True)

    def promote_model(self, model_id: str, *, require_gates: bool = True) -> dict:
        model = self.get_model_version(model_id)
        if not model:
            raise ValueError("Versao de modelo nao encontrada")
        promotion_reasons = model.get("metrics", {}).get("promotion_reasons", [])
        if require_gates and promotion_reasons:
            raise ValueError(f"Modelo reprovado nos gates: {', '.join(promotion_reasons)}")
        now = datetime.now(timezone.utc).isoformat()
        if self.enabled:
            with self.db.connection() as conn:
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            update public.model_versions set status='archived'
                            where asset_class=%s and horizon_days=%s
                              and status in ('active','shadow') and id<>%s
                            """,
                            (model["asset_class"], model["horizon_days"], model_id),
                        )
                        cur.execute(
                            """
                            update public.model_versions
                            set status='active',activated_at=%s where id=%s returning *
                            """,
                            (now, model_id),
                        )
                        return dict(cur.fetchone())
        models = self.storage.load_json(self._models_path) or []
        promoted = None
        for item in models:
            if (
                item["asset_class"] == model["asset_class"]
                and int(item["horizon_days"]) == int(model["horizon_days"])
                and item["status"] in {"active", "shadow"}
                and item["id"] != model_id
            ):
                item["status"] = "archived"
            if item["id"] == model_id:
                item["status"] = "active"
                item["activated_at"] = now
                promoted = item
        self.storage.save_json(self._models_path, models)
        return dict(promoted)

    def promote_model_package(
        self,
        model_ids: list[str],
        *,
        require_gates: bool = True,
    ) -> list[dict]:
        """Atomically promotes a complete class/horizon model package."""
        unique_ids = list(dict.fromkeys(model_ids))
        if not unique_ids:
            raise ValueError("Pacote de modelos vazio")
        now = datetime.now(timezone.utc).isoformat()

        def validate(models: list[dict]) -> None:
            if len(models) != len(unique_ids):
                raise ValueError("Uma ou mais versoes de modelo nao foram encontradas")
            identities = {
                (item["asset_class"], int(item["horizon_days"])) for item in models
            }
            if len(identities) != len(models):
                raise ValueError("Pacote possui modelos duplicados para o mesmo horizonte")
            if require_gates:
                rejected = [
                    item["id"]
                    for item in models
                    if item.get("metrics", {}).get("promotion_reasons", [])
                ]
                if rejected:
                    raise ValueError(
                        "Modelos reprovados nos gates: " + ", ".join(rejected)
                    )

        if self.enabled:
            with self.db.connection() as conn:
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute(
                            "select * from public.model_versions where id = any(%s) for update",
                            (unique_ids,),
                        )
                        models = [dict(row) for row in cur.fetchall()]
                        validate(models)
                        promoted = []
                        for model in models:
                            cur.execute(
                                """
                                update public.model_versions set status='archived'
                                where asset_class=%s and horizon_days=%s
                                  and status in ('active','shadow') and id<>%s
                                """,
                                (model["asset_class"], model["horizon_days"], model["id"]),
                            )
                            cur.execute(
                                """
                                update public.model_versions
                                set status='active',activated_at=%s where id=%s returning *
                                """,
                                (now, model["id"]),
                            )
                            promoted.append(dict(cur.fetchone()))
                        return promoted

        models = self.storage.load_json(self._models_path) or []
        selected = [item for item in models if item["id"] in unique_ids]
        validate(selected)
        targets = {
            (item["asset_class"], int(item["horizon_days"])): item["id"]
            for item in selected
        }
        for item in models:
            identity = (item["asset_class"], int(item["horizon_days"]))
            selected_id = targets.get(identity)
            if selected_id and item["id"] != selected_id and item["status"] in {"active", "shadow"}:
                item["status"] = "archived"
            if item["id"] in unique_ids:
                item["status"] = "active"
                item["activated_at"] = now
        self.storage.save_json(self._models_path, models)
        return [dict(item) for item in models if item["id"] in unique_ids]

    def save_snapshot(
        self,
        *,
        ticker: str,
        payload: dict,
        data_cutoff: str,
        news_fingerprint: str,
        activate: bool,
        model_versions: dict | None = None,
    ) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        snapshot = {
            "id": str(uuid.uuid4()),
            "ticker": ticker.upper(),
            "data_cutoff": data_cutoff,
            "news_fingerprint": news_fingerprint,
            "model_versions": model_versions or payload.get("model_versions", {}),
            "payload": payload,
            "generation_mode": payload.get("generation_mode", "deterministic_fallback"),
            "is_active": bool(activate),
            "created_at": now,
        }
        if self.enabled:
            with self.db.connection() as conn:
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute("select pg_advisory_xact_lock(hashtext(%s))", (snapshot["ticker"],))
                        if activate:
                            cur.execute(
                                "update public.asset_analysis_snapshots set is_active=false where ticker=%s and is_active",
                                (snapshot["ticker"],),
                            )
                        cur.execute(
                            """
                            insert into public.asset_analysis_snapshots (
                              id,ticker,data_cutoff,news_fingerprint,model_versions,payload,
                              generation_mode,is_active,created_at
                            ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            returning *
                            """,
                            (
                                snapshot["id"], snapshot["ticker"], data_cutoff,
                                news_fingerprint, snapshot["model_versions"], payload,
                                snapshot["generation_mode"], activate, now,
                            ),
                        )
                        saved = dict(cur.fetchone())
                        for outcome in self._outcome_rows(saved):
                            cur.execute(
                                """
                                insert into public.prediction_outcomes (
                                  snapshot_id,ticker,horizon_days,target_date,predicted_return,
                                  lower_return,upper_return,actual_return,scored_at
                                ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                                on conflict (snapshot_id,horizon_days) do nothing
                                """,
                                (
                                    outcome["snapshot_id"], outcome["ticker"], outcome["horizon_days"],
                                    outcome["target_date"], outcome["predicted_return"],
                                    outcome["lower_return"], outcome["upper_return"], None, None,
                                ),
                            )
                        return saved
        snapshots = self.storage.load_json(self._snapshots_path) or []
        if activate:
            for item in snapshots:
                if item["ticker"] == snapshot["ticker"]:
                    item["is_active"] = False
        snapshots.append(snapshot)
        self.storage.save_json(self._snapshots_path, snapshots)
        if activate:
            active = self.storage.load_json(self._active_path) or {}
            active[snapshot["ticker"]] = snapshot["id"]
            self.storage.save_json(self._active_path, active)
        outcomes = self.storage.load_json(self._outcomes_path) or []
        existing = {(item["snapshot_id"], int(item["horizon_days"])) for item in outcomes}
        outcomes.extend(
            item
            for item in self._outcome_rows(snapshot)
            if (item["snapshot_id"], int(item["horizon_days"])) not in existing
        )
        self.storage.save_json(self._outcomes_path, outcomes)
        return snapshot

    def list_prediction_outcomes(
        self,
        *,
        snapshot_id: str | None = None,
        unscored_only: bool = False,
    ) -> list[dict]:
        if self.enabled:
            clauses, params = [], []
            if snapshot_id:
                clauses.append("snapshot_id=%s")
                params.append(snapshot_id)
            if unscored_only:
                clauses.append("actual_return is null")
            where = " where " + " and ".join(clauses) if clauses else ""
            return [
                dict(row)
                for row in self.db.fetch_all(
                    f"select * from public.prediction_outcomes{where} order by target_date,horizon_days",
                    tuple(params),
                )
            ]
        rows = list(self.storage.load_json(self._outcomes_path) or [])
        if snapshot_id:
            rows = [item for item in rows if item["snapshot_id"] == snapshot_id]
        if unscored_only:
            rows = [item for item in rows if item.get("actual_return") is None]
        return sorted(rows, key=lambda item: (item["target_date"], int(item["horizon_days"])))

    def score_prediction_outcome(
        self,
        snapshot_id: str,
        horizon_days: int,
        actual_return: float,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if self.enabled:
            self.db.execute(
                """
                update public.prediction_outcomes
                set actual_return=%s,scored_at=%s
                where snapshot_id=%s and horizon_days=%s and actual_return is null
                """,
                (float(actual_return), now, snapshot_id, int(horizon_days)),
            )
            return
        rows = self.storage.load_json(self._outcomes_path) or []
        for item in rows:
            if item["snapshot_id"] == snapshot_id and int(item["horizon_days"]) == int(horizon_days):
                item["actual_return"] = float(actual_return)
                item["scored_at"] = now
                break
        self.storage.save_json(self._outcomes_path, rows)

    def get_active_snapshot(self, ticker: str) -> dict | None:
        ticker = ticker.upper()
        if self.enabled:
            row = self.db.fetch_one(
                "select * from public.asset_analysis_snapshots where ticker=%s and is_active",
                (ticker,),
            )
            return dict(row) if row else None
        active = self.storage.load_json(self._active_path) or {}
        active_id = active.get(ticker)
        if not active_id:
            return None
        return next(
            (item for item in (self.storage.load_json(self._snapshots_path) or []) if item["id"] == active_id),
            None,
        )

    def activate_snapshot(self, snapshot_id: str) -> dict:
        if self.enabled:
            with self.db.connection() as conn:
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute(
                            "select * from public.asset_analysis_snapshots where id=%s for update",
                            (snapshot_id,),
                        )
                        snapshot = cur.fetchone()
                        if not snapshot:
                            raise ValueError("Snapshot nao encontrado")
                        cur.execute("select pg_advisory_xact_lock(hashtext(%s))", (snapshot["ticker"],))
                        cur.execute(
                            "update public.asset_analysis_snapshots set is_active=false where ticker=%s and is_active",
                            (snapshot["ticker"],),
                        )
                        cur.execute(
                            "update public.asset_analysis_snapshots set is_active=true where id=%s returning *",
                            (snapshot_id,),
                        )
                        return dict(cur.fetchone())
        snapshots = self.storage.load_json(self._snapshots_path) or []
        target = next((item for item in snapshots if item["id"] == snapshot_id), None)
        if not target:
            raise ValueError("Snapshot nao encontrado")
        for item in snapshots:
            if item["ticker"] == target["ticker"]:
                item["is_active"] = item["id"] == snapshot_id
        self.storage.save_json(self._snapshots_path, snapshots)
        active = self.storage.load_json(self._active_path) or {}
        active[target["ticker"]] = snapshot_id
        self.storage.save_json(self._active_path, active)
        return dict(target)

    def list_snapshots(self, ticker: str, limit: int = 100) -> list[dict]:
        ticker = ticker.upper()
        if self.enabled:
            return [
                dict(row)
                for row in self.db.fetch_all(
                    "select * from public.asset_analysis_snapshots where ticker=%s order by created_at desc limit %s",
                    (ticker, limit),
                )
            ]
        rows = [item for item in (self.storage.load_json(self._snapshots_path) or []) if item["ticker"] == ticker]
        return sorted(rows, key=lambda item: item["created_at"], reverse=True)[:limit]

    def enqueue_job(
        self,
        ticker: str,
        *,
        reason: str,
        dedupe_key: str,
        priority: int = 0,
        run_after: str | None = None,
    ) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        job = {
            "id": str(uuid.uuid4()),
            "ticker": ticker.upper(),
            "reason": reason,
            "dedupe_key": dedupe_key,
            "status": "pending",
            "priority": int(priority),
            "attempts": 0,
            "run_after": run_after or now,
            "error": None,
            "created_at": now,
            "updated_at": now,
        }
        if self.enabled:
            row = self.db.fetch_one(
                """
                insert into public.analysis_jobs (
                  id,ticker,reason,dedupe_key,status,priority,attempts,run_after,created_at,updated_at
                ) values (%s,%s,%s,%s,'pending',%s,0,%s,%s,%s)
                on conflict (dedupe_key) do update set dedupe_key=excluded.dedupe_key
                returning *
                """,
                (
                    job["id"], job["ticker"], reason, dedupe_key, priority,
                    job["run_after"], now, now,
                ),
            )
            return dict(row or job)
        jobs = self.storage.load_json(self._jobs_path) or []
        existing = next((item for item in jobs if item["dedupe_key"] == dedupe_key), None)
        if existing:
            return existing
        jobs.append(job)
        self.storage.save_json(self._jobs_path, jobs)
        return job

    def claim_next_job(self) -> dict | None:
        now = datetime.now(timezone.utc)
        if self.enabled:
            with self.db.connection() as conn:
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            select * from public.analysis_jobs
                            where status='pending' and run_after <= timezone('utc', now())
                            order by priority desc, created_at
                            for update skip locked limit 1
                            """
                        )
                        row = cur.fetchone()
                        if not row:
                            return None
                        cur.execute(
                            """
                            update public.analysis_jobs
                            set status='running', attempts=attempts+1, updated_at=timezone('utc', now())
                            where id=%s returning *
                            """,
                            (row["id"],),
                        )
                        return dict(cur.fetchone())
        jobs = self.storage.load_json(self._jobs_path) or []
        eligible = [
            item for item in jobs
            if item["status"] == "pending" and datetime.fromisoformat(item["run_after"].replace("Z", "+00:00")) <= now
        ]
        if not eligible:
            return None
        job = sorted(eligible, key=lambda item: (-item["priority"], item["created_at"]))[0]
        job["status"] = "running"
        job["attempts"] += 1
        job["updated_at"] = now.isoformat()
        self.storage.save_json(self._jobs_path, jobs)
        return dict(job)

    def complete_job(self, job_id: str) -> None:
        self._update_job(job_id, status="completed", error=None)

    def fail_job(self, job_id: str, error: str, *, max_attempts: int = 3) -> None:
        if self.enabled:
            row = self.db.fetch_one("select attempts from public.analysis_jobs where id=%s", (job_id,))
            status = "failed" if row and int(row["attempts"]) >= max_attempts else "pending"
            self._update_job(job_id, status=status, error=error)
            return
        jobs = self.storage.load_json(self._jobs_path) or []
        job = next((item for item in jobs if item["id"] == job_id), None)
        if not job:
            return
        job["status"] = "failed" if int(job["attempts"]) >= max_attempts else "pending"
        job["error"] = error
        job["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.storage.save_json(self._jobs_path, jobs)

    def _update_job(self, job_id: str, *, status: str, error: str | None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if self.enabled:
            self.db.execute(
                "update public.analysis_jobs set status=%s,error=%s,updated_at=%s where id=%s",
                (status, error, now, job_id),
            )
            return
        jobs = self.storage.load_json(self._jobs_path) or []
        for item in jobs:
            if item["id"] == job_id:
                item["status"] = status
                item["error"] = error
                item["updated_at"] = now
                break
        self.storage.save_json(self._jobs_path, jobs)
