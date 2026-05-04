from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np
import pandas as pd

from db.database import resolve_storage_path
from modules.data.data_fetcher import DataFetcher
from modules.research_lab.store import ResearchLabStore


FEATURE_COLUMNS = [
    "ret_1",
    "ret_3",
    "ret_5",
    "ret_10",
    "momentum_20",
    "zscore_20",
    "vol_20",
    "range_pct",
    "trend_gap_20",
    "trend_gap_50",
    "vol_ratio_20",
]


@dataclass
class _SplitResult:
    train_idx: np.ndarray
    validation_idx: np.ndarray
    test_idx: np.ndarray


class ResearchLabService:
    @classmethod
    async def bootstrap(cls, owner_username: str) -> dict[str, Any]:
        from modules.projects.store import ProjectStore

        return {
            "datasets": await ResearchLabStore.list_datasets(owner_username),
            "runs": await ResearchLabStore.list_runs(owner_username),
            "projects": await ProjectStore.list_projects(owner_username),
        }

    @classmethod
    async def ingest_uploaded_csv(
        cls,
        *,
        owner_username: str,
        title: str,
        csv_text: str,
        project_id: Optional[str] = None,
    ) -> dict[str, Any]:
        if not str(csv_text or "").strip():
            raise ValueError("CSV vuoto")
        df = pd.read_csv(io.StringIO(csv_text))
        normalized = cls._normalize_market_dataframe(df)
        return await cls._persist_dataset(
            owner_username=owner_username,
            project_id=project_id,
            title=title or "Dataset caricato",
            source="upload",
            symbol=None,
            timeframe=None,
            date_from=normalized.index.min().isoformat() if len(normalized.index) else None,
            date_to=normalized.index.max().isoformat() if len(normalized.index) else None,
            df=normalized,
            metadata={"ingest_mode": "upload"},
        )

    @classmethod
    async def fetch_market_data(
        cls,
        *,
        owner_username: str,
        title: str,
        provider: str,
        symbol: str,
        timeframe: str,
        date_from: str,
        date_to: str,
        project_id: Optional[str] = None,
    ) -> dict[str, Any]:
        fetcher = DataFetcher()
        df = await fetcher.fetch(provider, symbol, timeframe, date_from, date_to)
        return await cls._persist_dataset(
            owner_username=owner_username,
            project_id=project_id,
            title=title or f"{symbol} {timeframe}",
            source=provider,
            symbol=symbol,
            timeframe=timeframe,
            date_from=date_from,
            date_to=date_to,
            df=df,
            metadata={
                "ingest_mode": "provider",
                "quality_warnings": fetcher.get_quality_warnings(),
                "cleaning_stats": fetcher.get_cleaning_stats(),
            },
        )

    @classmethod
    async def train_statistical_model(
        cls,
        *,
        owner_username: str,
        dataset_id: str,
        title: Optional[str],
        horizon_bars: int = 12,
        return_threshold_bps: float = 8.0,
        train_ratio: float = 0.6,
        validation_ratio: float = 0.2,
        learning_rate: float = 0.05,
        epochs: int = 600,
        l2_penalty: float = 0.002,
    ) -> dict[str, Any]:
        dataset = await ResearchLabStore.get_dataset(owner_username, dataset_id)
        if not dataset:
            raise ValueError("Dataset non trovato")
        df = cls._load_dataset_frame(dataset["storage_path"])
        prepared = cls._prepare_training_frame(
            df,
            horizon_bars=max(2, int(horizon_bars)),
            return_threshold_bps=float(return_threshold_bps),
        )
        if len(prepared) < 240:
            raise ValueError("Dati insufficienti: servono almeno 240 righe utili dopo feature engineering e target.")

        split = cls._make_split(len(prepared), train_ratio=train_ratio, validation_ratio=validation_ratio)
        feature_cols = [column for column in FEATURE_COLUMNS if column in prepared.columns]
        x = prepared[feature_cols].to_numpy(dtype=float)
        y = prepared["target"].to_numpy(dtype=float)

        model = cls._fit_logistic_regression(
            x_train=x[split.train_idx],
            y_train=y[split.train_idx],
            x_validation=x[split.validation_idx],
            y_validation=y[split.validation_idx],
            learning_rate=learning_rate,
            epochs=epochs,
            l2_penalty=l2_penalty,
        )

        train_probs = cls._predict_proba(x[split.train_idx], model["weights"], model["bias"], model["mean"], model["std"])
        validation_probs = cls._predict_proba(x[split.validation_idx], model["weights"], model["bias"], model["mean"], model["std"])
        test_probs = cls._predict_proba(x[split.test_idx], model["weights"], model["bias"], model["mean"], model["std"])

        train_metrics = cls._classification_metrics(y[split.train_idx], train_probs)
        validation_metrics = cls._classification_metrics(y[split.validation_idx], validation_probs)
        test_metrics = cls._classification_metrics(y[split.test_idx], test_probs)
        walk_forward = cls._walk_forward_evaluation(
            prepared=prepared,
            feature_cols=feature_cols,
            horizon_bars=horizon_bars,
            return_threshold_bps=return_threshold_bps,
            learning_rate=learning_rate,
            epochs=epochs,
            l2_penalty=l2_penalty,
        )
        shuffled_metrics = cls._shuffled_baseline(
            x_train=x[split.train_idx],
            y_train=y[split.train_idx],
            x_test=x[split.test_idx],
            y_test=y[split.test_idx],
            learning_rate=learning_rate,
            epochs=max(200, int(epochs * 0.5)),
            l2_penalty=l2_penalty,
        )

        target_positive_rate = float(prepared["target"].mean())
        train_test_gap = float(train_metrics["auc"] - test_metrics["auc"])
        signal_to_noise = max(0.0, round(test_metrics["auc"] - shuffled_metrics["auc"], 4))
        warnings = []
        if train_test_gap > 0.12:
            warnings.append("Gap train/test elevato: il segnale rischia di degradare fuori campione.")
        if test_metrics["auc"] <= shuffled_metrics["auc"] + 0.03:
            warnings.append("Il modello batte poco il baseline shuffled: rischio rumore elevato.")
        if walk_forward["stability_score"] < 55:
            warnings.append("Stabilita walk-forward debole: il pattern non regge bene in finestre successive.")
        if target_positive_rate < 0.25 or target_positive_rate > 0.75:
            warnings.append("Target sbilanciato: valuta horizon o threshold diversi prima di fidarti del modello.")

        quality_score = int(
            np.clip(
                100
                - max(0.0, train_test_gap) * 180
                + max(0.0, test_metrics["auc"] - 0.5) * 120
                + max(0.0, walk_forward["stability_score"] - 50) * 0.35
                + signal_to_noise * 120,
                15,
                98,
            )
        )
        verdict = (
            "PRONTO_PER_RICERCA_AVANZATA"
            if quality_score >= 78 and not warnings
            else "DA_RIFINIRE"
            if quality_score >= 58
            else "RUMORE_O_OVERFIT"
        )
        feature_ranking = cls._feature_ranking(model["weights"], feature_cols)
        result = {
            "run_id": "",
            "dataset_id": dataset_id,
            "summary": {
                "model_type": "logistic_research_v1",
                "rows_used": int(len(prepared)),
                "feature_count": len(feature_cols),
                "target_positive_rate": round(target_positive_rate, 4),
                "quality_score": quality_score,
                "verdict": verdict,
            },
            "target_definition": {
                "horizon_bars": int(horizon_bars),
                "return_threshold_bps": float(return_threshold_bps),
                "label_rule": f"Target=1 se il rendimento forward a {horizon_bars} barre supera {return_threshold_bps:.1f} bps.",
            },
            "split_summary": {
                "train_rows": int(len(split.train_idx)),
                "validation_rows": int(len(split.validation_idx)),
                "test_rows": int(len(split.test_idx)),
                "train_from": prepared.index[split.train_idx[0]].isoformat() if len(split.train_idx) else None,
                "train_to": prepared.index[split.train_idx[-1]].isoformat() if len(split.train_idx) else None,
                "test_from": prepared.index[split.test_idx[0]].isoformat() if len(split.test_idx) else None,
                "test_to": prepared.index[split.test_idx[-1]].isoformat() if len(split.test_idx) else None,
            },
            "metrics": {
                "train": train_metrics,
                "validation": validation_metrics,
                "test": test_metrics,
            },
            "walk_forward": walk_forward,
            "feature_ranking": feature_ranking,
            "anti_overfitting": {
                "train_test_gap": round(train_test_gap, 4),
                "shuffled_baseline_accuracy": round(shuffled_metrics["accuracy"], 4),
                "shuffled_baseline_auc": round(shuffled_metrics["auc"], 4),
                "signal_to_noise_score": round(signal_to_noise, 4),
                "warnings": warnings,
            },
            "recommendations": cls._build_recommendations(
                verdict=verdict,
                warnings=warnings,
                test_metrics=test_metrics,
                walk_forward=walk_forward,
                dataset=dataset,
            ),
        }
        stored = await ResearchLabStore.create_run(
            dataset_id=dataset_id,
            owner_username=owner_username,
            project_id=dataset.get("project_id"),
            title=title or f"Run {dataset.get('title')}",
            model_type="logistic_research_v1",
            config={
                "horizon_bars": horizon_bars,
                "return_threshold_bps": return_threshold_bps,
                "train_ratio": train_ratio,
                "validation_ratio": validation_ratio,
                "learning_rate": learning_rate,
                "epochs": epochs,
                "l2_penalty": l2_penalty,
                "features": feature_cols,
            },
            result=result,
        )
        result["run_id"] = stored["run_id"]
        stored["result"] = result
        return stored

    @classmethod
    async def _persist_dataset(
        cls,
        *,
        owner_username: str,
        project_id: Optional[str],
        title: str,
        source: str,
        symbol: Optional[str],
        timeframe: Optional[str],
        date_from: Optional[str],
        date_to: Optional[str],
        df: pd.DataFrame,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        quality = cls._dataset_quality(df, metadata)
        storage_dir = resolve_storage_path("research_lab", "datasets")
        storage_dir.mkdir(parents=True, exist_ok=True)
        created = await ResearchLabStore.create_dataset(
            owner_username=owner_username,
            project_id=project_id,
            title=title,
            source=source,
            symbol=symbol,
            timeframe=timeframe,
            date_from=date_from,
            date_to=date_to,
            row_count=len(df),
            quality=quality,
            metadata=metadata,
            storage_path="",
        )
        dataset_path = storage_dir / f"{created['dataset_id']}.csv"
        df_to_store = df.reset_index().rename(columns={"index": "timestamp"})
        df_to_store.to_csv(dataset_path, index=False)
        updated = await ResearchLabStore.update_dataset(
            owner_username,
            created["dataset_id"],
            storage_path=str(dataset_path),
            quality=quality,
            metadata=metadata,
            row_count=len(df),
        )
        return updated or {**created, "storage_path": str(dataset_path)}

    @classmethod
    def _normalize_market_dataframe(cls, df: pd.DataFrame) -> pd.DataFrame:
        mapping = {}
        for column in df.columns:
            normalized = str(column).strip().lower().replace(" ", "").replace("_", "")
            if normalized in {"timestamp", "datetime", "date", "time", "gmttime"}:
                mapping[column] = "timestamp"
            elif normalized in {"open", "o"}:
                mapping[column] = "Open"
            elif normalized in {"high", "h"}:
                mapping[column] = "High"
            elif normalized in {"low", "l"}:
                mapping[column] = "Low"
            elif normalized in {"close", "c", "adjclose", "last"}:
                mapping[column] = "Close"
            elif normalized in {"volume", "vol", "tickvolume"}:
                mapping[column] = "Volume"
        df = df.rename(columns=mapping)
        if "timestamp" not in df.columns:
            raise ValueError("Colonna tempo non trovata nel dataset")
        if "Close" not in df.columns:
            raise ValueError("Colonna Close non trovata nel dataset")
        for required in ("Open", "High", "Low"):
            if required not in df.columns:
                df[required] = df["Close"]
        if "Volume" not in df.columns:
            df["Volume"] = 1.0
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        df = df.dropna(subset=["timestamp"])
        df = df.set_index("timestamp").sort_index()
        for column in ("Open", "High", "Low", "Close", "Volume"):
            df[column] = pd.to_numeric(df[column], errors="coerce")
        df = df.dropna(subset=["Open", "High", "Low", "Close"])
        return df[["Open", "High", "Low", "Close", "Volume"]]

    @classmethod
    def _dataset_quality(cls, df: pd.DataFrame, metadata: dict[str, Any]) -> dict[str, Any]:
        quality_warnings = list(metadata.get("quality_warnings") or [])
        duplicate_count = int(df.index.duplicated().sum())
        gaps = df.index.to_series().diff().dropna()
        median_gap_min = float(gaps.median().total_seconds() / 60) if not gaps.empty else 0.0
        gap_ratio = float((gaps > gaps.median() * 5).mean()) if len(gaps) else 0.0
        if duplicate_count:
            quality_warnings.append(f"Rilevati {duplicate_count} timestamp duplicati.")
        if gap_ratio > 0.05:
            quality_warnings.append("Dataset con molti gap temporali rispetto alla frequenza mediana.")
        return {
            "rows": int(len(df)),
            "columns": list(df.columns),
            "from": df.index.min().isoformat() if len(df.index) else None,
            "to": df.index.max().isoformat() if len(df.index) else None,
            "duplicate_timestamps": duplicate_count,
            "median_gap_min": round(median_gap_min, 2),
            "gap_ratio": round(gap_ratio, 4),
            "warnings": quality_warnings,
        }

    @classmethod
    def _load_dataset_frame(cls, storage_path: str) -> pd.DataFrame:
        path = Path(storage_path)
        if not path.exists():
            raise FileNotFoundError("File dataset non trovato")
        df = pd.read_csv(path)
        return cls._normalize_market_dataframe(df)

    @classmethod
    def _prepare_training_frame(
        cls,
        df: pd.DataFrame,
        *,
        horizon_bars: int,
        return_threshold_bps: float,
    ) -> pd.DataFrame:
        frame = df.copy()
        frame["ret_1"] = frame["Close"].pct_change(1)
        frame["ret_3"] = frame["Close"].pct_change(3)
        frame["ret_5"] = frame["Close"].pct_change(5)
        frame["ret_10"] = frame["Close"].pct_change(10)
        frame["momentum_20"] = frame["Close"].pct_change(20)
        rolling_mean = frame["Close"].rolling(20).mean()
        rolling_std = frame["Close"].rolling(20).std().replace(0, np.nan)
        frame["zscore_20"] = (frame["Close"] - rolling_mean) / rolling_std
        frame["vol_20"] = frame["ret_1"].rolling(20).std()
        frame["range_pct"] = (frame["High"] - frame["Low"]) / frame["Close"].replace(0, np.nan)
        ema20 = frame["Close"].ewm(span=20, adjust=False).mean()
        ema50 = frame["Close"].ewm(span=50, adjust=False).mean()
        frame["trend_gap_20"] = (frame["Close"] / ema20) - 1
        frame["trend_gap_50"] = (frame["Close"] / ema50) - 1
        vol_mean = frame["Volume"].rolling(20).mean().replace(0, np.nan)
        frame["vol_ratio_20"] = frame["Volume"] / vol_mean
        frame["future_return"] = frame["Close"].shift(-horizon_bars) / frame["Close"] - 1
        frame["target"] = (frame["future_return"] >= (return_threshold_bps / 10000.0)).astype(float)
        frame = frame.replace([np.inf, -np.inf], np.nan).dropna(subset=FEATURE_COLUMNS + ["future_return", "target"])
        return frame

    @classmethod
    def _make_split(cls, length: int, *, train_ratio: float, validation_ratio: float) -> _SplitResult:
        train_end = max(80, int(length * train_ratio))
        validation_end = min(length - 40, train_end + max(40, int(length * validation_ratio)))
        validation_end = max(train_end + 20, validation_end)
        return _SplitResult(
            train_idx=np.arange(0, train_end),
            validation_idx=np.arange(train_end, validation_end),
            test_idx=np.arange(validation_end, length),
        )

    @classmethod
    def _fit_logistic_regression(
        cls,
        *,
        x_train: np.ndarray,
        y_train: np.ndarray,
        x_validation: np.ndarray,
        y_validation: np.ndarray,
        learning_rate: float,
        epochs: int,
        l2_penalty: float,
    ) -> dict[str, Any]:
        mean = x_train.mean(axis=0)
        std = x_train.std(axis=0)
        std[std == 0] = 1.0
        x_train_n = (x_train - mean) / std
        weights = np.zeros(x_train.shape[1], dtype=float)
        bias = 0.0
        best = {"auc": -1.0, "weights": weights.copy(), "bias": bias}
        for _ in range(max(100, epochs)):
            logits = x_train_n @ weights + bias
            probs = 1.0 / (1.0 + np.exp(-np.clip(logits, -25, 25)))
            error = probs - y_train
            grad_w = (x_train_n.T @ error) / len(x_train_n) + l2_penalty * weights
            grad_b = float(error.mean())
            weights -= learning_rate * grad_w
            bias -= learning_rate * grad_b
            if len(x_validation):
                val_probs = cls._predict_proba(x_validation, weights, bias, mean, std)
                val_auc = cls._classification_metrics(y_validation, val_probs)["auc"]
                if val_auc > best["auc"]:
                    best = {"auc": val_auc, "weights": weights.copy(), "bias": float(bias)}
        return {"weights": best["weights"], "bias": best["bias"], "mean": mean, "std": std}

    @classmethod
    def _predict_proba(
        cls,
        x: np.ndarray,
        weights: np.ndarray,
        bias: float,
        mean: np.ndarray,
        std: np.ndarray,
    ) -> np.ndarray:
        normalized = (x - mean) / std
        logits = normalized @ weights + bias
        return 1.0 / (1.0 + np.exp(-np.clip(logits, -25, 25)))

    @classmethod
    def _classification_metrics(cls, y_true: np.ndarray, probs: np.ndarray) -> dict[str, float]:
        preds = (probs >= 0.5).astype(float)
        tp = float(((preds == 1) & (y_true == 1)).sum())
        tn = float(((preds == 0) & (y_true == 0)).sum())
        fp = float(((preds == 1) & (y_true == 0)).sum())
        fn = float(((preds == 0) & (y_true == 1)).sum())
        accuracy = (tp + tn) / max(1.0, len(y_true))
        precision = tp / max(1.0, tp + fp)
        recall = tp / max(1.0, tp + fn)
        specificity = tn / max(1.0, tn + fp)
        balanced_accuracy = 0.5 * (recall + specificity)
        auc = cls._roc_auc(y_true, probs)
        brier = float(np.mean((probs - y_true) ** 2))
        return {
            "accuracy": round(float(accuracy), 4),
            "precision": round(float(precision), 4),
            "recall": round(float(recall), 4),
            "balanced_accuracy": round(float(balanced_accuracy), 4),
            "auc": round(float(auc), 4),
            "brier": round(float(brier), 4),
        }

    @classmethod
    def _roc_auc(cls, y_true: np.ndarray, probs: np.ndarray) -> float:
        positives = probs[y_true == 1]
        negatives = probs[y_true == 0]
        if len(positives) == 0 or len(negatives) == 0:
            return 0.5
        comparisons = [(p > n) + 0.5 * (p == n) for p in positives for n in negatives]
        return float(np.mean(comparisons)) if comparisons else 0.5

    @classmethod
    def _walk_forward_evaluation(
        cls,
        *,
        prepared: pd.DataFrame,
        feature_cols: list[str],
        horizon_bars: int,
        return_threshold_bps: float,
        learning_rate: float,
        epochs: int,
        l2_penalty: float,
    ) -> dict[str, Any]:
        folds = []
        total_rows = len(prepared)
        fold_size = max(60, int(total_rows * 0.15))
        cursor = max(120, int(total_rows * 0.4))
        while cursor + fold_size < total_rows and len(folds) < 4:
            train = prepared.iloc[:cursor]
            test = prepared.iloc[cursor : cursor + fold_size]
            model = cls._fit_logistic_regression(
                x_train=train[feature_cols].to_numpy(dtype=float),
                y_train=train["target"].to_numpy(dtype=float),
                x_validation=test[feature_cols].to_numpy(dtype=float),
                y_validation=test["target"].to_numpy(dtype=float),
                learning_rate=learning_rate,
                epochs=max(250, int(epochs * 0.6)),
                l2_penalty=l2_penalty,
            )
            probs = cls._predict_proba(
                test[feature_cols].to_numpy(dtype=float),
                model["weights"],
                model["bias"],
                model["mean"],
                model["std"],
            )
            metrics = cls._classification_metrics(test["target"].to_numpy(dtype=float), probs)
            folds.append(
                {
                    "train_to": train.index.max().isoformat(),
                    "test_from": test.index.min().isoformat(),
                    "test_to": test.index.max().isoformat(),
                    **metrics,
                }
            )
            cursor += fold_size
        avg_acc = float(np.mean([fold["accuracy"] for fold in folds])) if folds else 0.5
        avg_auc = float(np.mean([fold["auc"] for fold in folds])) if folds else 0.5
        dispersion = float(np.std([fold["auc"] for fold in folds])) if len(folds) > 1 else 0.0
        stability_score = int(np.clip((avg_auc - dispersion) * 100, 10, 95))
        return {
            "folds": folds,
            "stability_score": stability_score,
            "average_test_accuracy": round(avg_acc, 4),
            "average_test_auc": round(avg_auc, 4),
        }

    @classmethod
    def _shuffled_baseline(
        cls,
        *,
        x_train: np.ndarray,
        y_train: np.ndarray,
        x_test: np.ndarray,
        y_test: np.ndarray,
        learning_rate: float,
        epochs: int,
        l2_penalty: float,
    ) -> dict[str, float]:
        shuffled = np.random.default_rng(42).permutation(y_train)
        model = cls._fit_logistic_regression(
            x_train=x_train,
            y_train=shuffled,
            x_validation=x_test,
            y_validation=y_test,
            learning_rate=learning_rate,
            epochs=epochs,
            l2_penalty=l2_penalty,
        )
        probs = cls._predict_proba(x_test, model["weights"], model["bias"], model["mean"], model["std"])
        return cls._classification_metrics(y_test, probs)

    @classmethod
    def _feature_ranking(cls, weights: np.ndarray, feature_cols: list[str]) -> list[dict[str, Any]]:
        ranking = []
        for feature, weight in sorted(zip(feature_cols, weights), key=lambda item: abs(item[1]), reverse=True):
            ranking.append(
                {
                    "feature": feature,
                    "weight": round(float(weight), 4),
                    "direction": "positive" if weight > 0.0001 else "negative" if weight < -0.0001 else "neutral",
                }
            )
        return ranking

    @classmethod
    def _build_recommendations(
        cls,
        *,
        verdict: str,
        warnings: list[str],
        test_metrics: dict[str, float],
        walk_forward: dict[str, Any],
        dataset: dict[str, Any],
    ) -> list[str]:
        recommendations = []
        if verdict == "RUMORE_O_OVERFIT":
            recommendations.append("Riduci il numero di feature o alza la soglia target per evitare pattern deboli.")
            recommendations.append("Ripeti il training con una finestra piu lunga o un timeframe meno rumoroso.")
        if test_metrics.get("auc", 0.0) < 0.56:
            recommendations.append("Il potere discriminante resta modesto: valuta feature di regime e filtri di volatilita.")
        if walk_forward.get("stability_score", 0) < 60:
            recommendations.append("Rafforza il controllo walk-forward: il modello cambia troppo tra le finestre.")
        if dataset.get("source") == "demo":
            recommendations.append("Sostituisci i dati demo con storico reale prima di prendere decisioni operative.")
        if not recommendations:
            recommendations.append("Il setup regge la prima selezione quantitativa: collega il risultato al builder o al desk per una validazione strategica completa.")
        recommendations.extend(warnings[:2])
        return recommendations[:5]
