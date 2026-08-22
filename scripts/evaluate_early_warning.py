#!/usr/bin/env python3
"""Evaluate a non-operational early-warning prototype out of sample.

The input is a documented monthly binary outcome with conventional climate
predictors and a suitability estimate. The script compares a month-of-year
seasonal baseline, a conventional-climate logistic model, and a
climate-plus-suitability logistic model. It uses a train/validation/test time
split, calibration diagnostics, bootstrap intervals, and an explicit decision
threshold. Nothing in this script authorizes operational deployment.

Optional dependencies are listed in requirements-extensions.txt.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
except ImportError as exc:  # pragma: no cover - exercised when optional deps are absent
    raise SystemExit(
        "evaluate_early_warning.py requires the optional packages in requirements-extensions.txt"
    ) from exc


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_COLUMNS = {
    "source_id",
    "geography",
    "suitability_species",
    "year",
    "month",
    "outcome",
    "outcome_unit",
    "suitability_value",
    "suitability_low",
    "suitability_high",
    "reporting_change_note",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=PROJECT_ROOT / "inputs" / "early_warning_monthly.csv",
    )
    parser.add_argument("--species", default=None)
    parser.add_argument("--validation-start", type=int, default=2005)
    parser.add_argument("--test-start", type=int, default=2015)
    parser.add_argument("--decision-threshold", type=float, default=0.5)
    parser.add_argument("--bootstrap-reps", type=int, default=500)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "early_warning",
    )
    return parser.parse_args()


def read_data(
    path: Path,
    species: str | None,
    validation_start: int,
    test_start: int,
) -> pd.DataFrame:
    frame = pd.read_csv(path, keep_default_na=False)
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Early-warning table is missing columns: {sorted(missing)}")
    species_values = sorted(frame["suitability_species"].astype(str).unique())
    if species is None:
        if len(species_values) != 1:
            raise ValueError(
                "The input contains multiple species; run once per species with --species."
            )
        species = species_values[0]
    frame = frame[frame["suitability_species"].eq(species)].copy()
    if frame.empty:
        raise ValueError(f"No rows found for suitability species {species!r}")
    for column in ("year", "month", "outcome"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    numeric_columns = [
        column
        for column in frame.columns
        if column.startswith("climate_")
        or column in {"suitability_value", "suitability_low", "suitability_high"}
    ]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame[["year", "month", "outcome"]].isna().any().any():
        raise ValueError("year, month, and outcome must be numeric")
    frame["year"] = frame["year"].astype(int)
    frame["month"] = frame["month"].astype(int)
    frame["outcome"] = frame["outcome"].astype(int)
    if not frame["year"].between(1975, 2024).all() or not frame["month"].between(1, 12).all():
        raise ValueError("Early-warning rows must fall within 1975–2024 and months 1–12")
    if not frame["outcome"].isin([0, 1]).all():
        raise ValueError("outcome must be a binary event indicator (0 or 1)")
    if frame.duplicated(["source_id", "geography", "year", "month"]).any():
        raise ValueError("Early-warning input has duplicate source-geography-month rows")
    climate_columns = [column for column in frame.columns if column.startswith("climate_")]
    if not climate_columns:
        raise ValueError("At least one climate_ predictor is required")
    frame["reporting_change_flag"] = frame["reporting_change_note"].astype(str).str.strip().ne("")
    frame["split"] = np.select(
        [frame["year"] < validation_start, frame["year"] < test_start],
        ["train", "validation"],
        default="test",
    )
    return frame


def seasonal_baseline(train: pd.DataFrame, target: pd.DataFrame) -> np.ndarray:
    overall = float(train["outcome"].mean())
    month_rates = train.groupby("month")["outcome"].mean()
    return target["month"].map(month_rates).fillna(overall).to_numpy(dtype=float)


def make_model() -> Pipeline:
    return Pipeline(
        steps=[
            ("impute", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
            ("model", LogisticRegression(max_iter=2000, random_state=42)),
        ]
    )


def binary_metrics(y_true: np.ndarray, prediction: np.ndarray, threshold: float) -> dict[str, float]:
    positive = prediction >= threshold
    actual_positive = y_true == 1
    actual_negative = y_true == 0
    tp = int((positive & actual_positive).sum())
    tn = int((~positive & actual_negative).sum())
    fp = int((positive & actual_negative).sum())
    fn = int((~positive & actual_positive).sum())
    return {
        "n": float(len(y_true)),
        "positive_rate": float(y_true.mean()) if len(y_true) else math.nan,
        "roc_auc": (
            float(roc_auc_score(y_true, prediction))
            if len(np.unique(y_true)) == 2
            else math.nan
        ),
        "average_precision": (
            float(average_precision_score(y_true, prediction))
            if len(np.unique(y_true)) == 2
            else math.nan
        ),
        "brier_score": float(brier_score_loss(y_true, prediction)) if len(y_true) else math.nan,
        "log_loss": (
            float(log_loss(y_true, np.clip(prediction, 1e-6, 1 - 1e-6), labels=[0, 1]))
            if len(np.unique(y_true)) == 2
            else math.nan
        ),
        "decision_threshold": threshold,
        "flagged_fraction": float(positive.mean()) if len(y_true) else math.nan,
        "sensitivity": float(tp / (tp + fn)) if tp + fn else math.nan,
        "specificity": float(tn / (tn + fp)) if tn + fp else math.nan,
        "positive_predictive_value": float(tp / (tp + fp)) if tp + fp else math.nan,
        "negative_predictive_value": float(tn / (tn + fn)) if tn + fn else math.nan,
    }


def calibration_rows(y_true: np.ndarray, prediction: np.ndarray, model_name: str, split: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    bins = np.linspace(0, 1, 11)
    labels = np.digitize(prediction, bins[1:-1], right=False)
    for bin_number in range(10):
        mask = labels == bin_number
        if not mask.any():
            continue
        rows.append(
            {
                "split": split,
                "model": model_name,
                "bin": bin_number,
                "n": int(mask.sum()),
                "mean_predicted_probability": float(prediction[mask].mean()),
                "observed_rate": float(y_true[mask].mean()),
            }
        )
    return rows


def bootstrap_rows(
    y_true: np.ndarray,
    predictions: dict[str, np.ndarray],
    reps: int,
    seed: int = 42,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    if len(y_true) < 2:
        return pd.DataFrame()
    for model_name, prediction in predictions.items():
        values: dict[str, list[float]] = {"roc_auc": [], "brier_score": [], "log_loss": []}
        for _ in range(reps):
            index = rng.integers(0, len(y_true), size=len(y_true))
            y = y_true[index]
            p = prediction[index]
            metrics = binary_metrics(y, p, threshold=0.5)
            for key in values:
                if np.isfinite(metrics[key]):
                    values[key].append(metrics[key])
        for metric, samples in values.items():
            if not samples:
                continue
            rows.append(
                {
                    "model": model_name,
                    "metric": metric,
                    "bootstrap_reps": reps,
                    "estimate_median": float(np.quantile(samples, 0.50)),
                    "lower_95": float(np.quantile(samples, 0.025)),
                    "upper_95": float(np.quantile(samples, 0.975)),
                }
            )
    return pd.DataFrame(rows)


def plot_calibration(calibration: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.4, 5.4), constrained_layout=True)
    for model, group in calibration[calibration["split"].eq("test")].groupby("model"):
        ax.plot(
            group["mean_predicted_probability"],
            group["observed_rate"],
            marker="o",
            linewidth=1.4,
            label=model,
        )
    ax.plot([0, 1], [0, 1], color="#777777", linestyle="--", label="perfect calibration")
    ax.set(xlim=(0, 1), ylim=(0, 1), xlabel="Mean predicted probability", ylabel="Observed rate")
    ax.set_title("Out-of-sample calibration; test period")
    ax.legend(fontsize=8)
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    if not args.data.exists():
        raise FileNotFoundError(
            f"Missing early-warning table: {args.data}. Populate inputs/early_warning_monthly.template.csv first."
        )
    if not 0 < args.decision_threshold < 1:
        raise ValueError("--decision-threshold must be between 0 and 1")
    if args.validation_start >= args.test_start:
        raise ValueError("validation period must precede test period")
    frame = read_data(args.data, args.species, args.validation_start, args.test_start)
    train = frame[frame["split"].eq("train")].copy()
    if train["outcome"].nunique() < 2:
        raise ValueError("Training data must contain both outcome classes")
    climate_columns = [column for column in frame.columns if column.startswith("climate_")]
    all_feature_columns = climate_columns + ["suitability_value"]
    climate_model = make_model().fit(train[climate_columns], train["outcome"])
    combined_model = make_model().fit(train[all_feature_columns], train["outcome"])

    predictions: list[pd.DataFrame] = []
    calibration: list[dict[str, object]] = []
    metric_rows: list[dict[str, object]] = []
    for split in ("train", "validation", "test"):
        subset = frame[frame["split"].eq(split)].copy()
        if subset.empty:
            continue
        y = subset["outcome"].to_numpy(dtype=int)
        model_predictions = {
            "seasonal_baseline": seasonal_baseline(train, subset),
            "climate": climate_model.predict_proba(subset[climate_columns])[:, 1],
            "climate_plus_suitability": combined_model.predict_proba(subset[all_feature_columns])[:, 1],
        }
        output = subset[["source_id", "geography", "year", "month", "outcome", "reporting_change_flag"]].copy()
        output["split"] = split
        for model_name, prediction in model_predictions.items():
            output[f"prediction_{model_name}"] = prediction
            metric = binary_metrics(y, prediction, args.decision_threshold)
            metric.update({"split": split, "model": model_name})
            metric_rows.append(metric)
            calibration.extend(calibration_rows(y, prediction, model_name, split))
        if split == "test":
            combined_prediction = model_predictions["climate_plus_suitability"]
            if {"suitability_low", "suitability_high"}.issubset(subset.columns):
                low_input = subset[all_feature_columns].copy()
                high_input = subset[all_feature_columns].copy()
                low_input["suitability_value"] = subset["suitability_low"]
                high_input["suitability_value"] = subset["suitability_high"]
                output["prediction_combined_suitability_low"] = combined_model.predict_proba(low_input)[:, 1]
                output["prediction_combined_suitability_high"] = combined_model.predict_proba(high_input)[:, 1]
                output["prediction_combined_suitability_mid"] = combined_prediction
        predictions.append(output)

    prediction_frame = pd.concat(predictions, ignore_index=True)
    test = prediction_frame[prediction_frame["split"].eq("test")]
    test_predictions = {
        column.removeprefix("prediction_"): test[column].to_numpy(dtype=float)
        for column in test.columns
        if column in {
            "prediction_seasonal_baseline",
            "prediction_climate",
            "prediction_climate_plus_suitability",
        }
    }
    bootstrap = bootstrap_rows(
        test["outcome"].to_numpy(dtype=int),
        test_predictions,
        args.bootstrap_reps,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    prediction_frame.to_csv(args.output_dir / "early_warning_predictions.csv", index=False, float_format="%.6f")
    pd.DataFrame(metric_rows).to_csv(args.output_dir / "early_warning_metrics.csv", index=False, float_format="%.6f")
    calibration_frame = pd.DataFrame(calibration)
    calibration_frame.to_csv(args.output_dir / "early_warning_calibration.csv", index=False, float_format="%.6f")
    bootstrap.to_csv(args.output_dir / "early_warning_bootstrap_intervals.csv", index=False, float_format="%.6f")
    pd.DataFrame(
        [
            {
                "decision_threshold": args.decision_threshold,
                "threshold_status": "provisional prototype threshold; not operationally approved",
                "test_start_year": args.test_start,
                "validation_start_year": args.validation_start,
                "reporting_change_flagged_test_rows": int(test["reporting_change_flag"].sum()),
                "test_rows": int(len(test)),
            }
        ]
    ).to_csv(args.output_dir / "early_warning_decision_threshold.csv", index=False)
    plot_calibration(calibration_frame, args.output_dir / "early_warning_calibration.png")
    print({"rows": len(frame), "test_rows": len(test), "models": list(test_predictions)})


if __name__ == "__main__":
    main()
