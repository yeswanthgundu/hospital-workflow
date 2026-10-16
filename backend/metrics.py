from __future__ import annotations

from pathlib import Path

import pandas as pd

# Planning assumptions for this synthetic operations demo.
SHIFT_MINUTES = 480
EMERGENCY_WEIGHT = 45
WARNING_THRESHOLD = 0.8
CRITICAL_THRESHOLD = 1.0

RISK_ORDER = {"Critical": 0, "Warning": 1, "Normal": 2}
DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "operations.csv"


def _risk(utilization: float) -> str:
    if utilization > CRITICAL_THRESHOLD:
        return "Critical"
    if utilization >= WARNING_THRESHOLD:
        return "Warning"
    return "Normal"


def _with_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["demand_minutes"] = (
        result["appointments"] * result["avg_task_minutes"]
        + result["emergency_cases"] * EMERGENCY_WEIGHT
    )
    result["capacity_minutes"] = result["staff_available"] * SHIFT_MINUTES
    result["utilization"] = result["demand_minutes"] / result["capacity_minutes"]
    result["risk"] = result["utilization"].map(_risk)
    result["_risk_order"] = result["risk"].map(RISK_ORDER)
    return result.sort_values(
        ["_risk_order", "utilization"], ascending=[True, False]
    ).drop(columns="_risk_order")


def load_operations(path: Path = DATA_PATH) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Synthetic operations data not found: {path}")
    frame = pd.read_csv(path, parse_dates=["date"])
    required = {
        "date",
        "department",
        "appointments",
        "staff_available",
        "avg_task_minutes",
        "emergency_cases",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Operations data is missing columns: {', '.join(sorted(missing))}")
    if frame.empty:
        raise ValueError("Operations data is empty")
    return frame


def _json_records(frame: pd.DataFrame) -> list[dict]:
    records = frame.copy()
    if "date" in records:
        records["date"] = pd.to_datetime(records["date"]).dt.strftime("%Y-%m-%d")
    return records.to_dict(orient="records")


def today_metrics(frame: pd.DataFrame | None = None) -> pd.DataFrame:
    frame = frame if frame is not None else load_operations()
    latest_date = frame["date"].max()
    today = frame.loc[frame["date"] == latest_date].drop(columns=["date"])
    return _with_metrics(today).reset_index(drop=True)


def forecast_metrics(frame: pd.DataFrame | None = None) -> pd.DataFrame:
    frame = frame if frame is not None else load_operations()
    latest_date = frame["date"].max()
    history = frame.loc[frame["date"] < latest_date].sort_values("date")
    if history["date"].nunique() < 7:
        raise ValueError("At least seven days of history are required for the forecast")
    last_seven_days = history.loc[history["date"] >= latest_date - pd.Timedelta(days=7)]
    forecast = (
        last_seven_days.groupby("department", as_index=False)
        .agg(
            appointments=("appointments", "mean"),
            staff_available=("staff_available", "mean"),
            avg_task_minutes=("avg_task_minutes", "mean"),
            emergency_cases=("emergency_cases", "mean"),
        )
    )
    forecast.insert(0, "date", (latest_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
    return _with_metrics(forecast).reset_index(drop=True)


def dashboard_data() -> dict:
    rows = today_metrics()
    counts = rows["risk"].value_counts()
    return {
        "counts": {risk: int(counts.get(risk, 0)) for risk in ("Normal", "Warning", "Critical")},
        "departments": _json_records(rows),
    }


def forecast_data() -> dict:
    return {"departments": _json_records(forecast_metrics())}


def question_context() -> str:
    today = today_metrics()
    forecast = forecast_metrics()
    forecast_by_department = forecast.set_index("department")
    lines = [
        "Department | Today risk | Today utilization | Appointments | Staff | "
        "Emergency cases | Forecast utilization tomorrow"
    ]
    for row in today.to_dict(orient="records"):
        next_day = forecast_by_department.loc[row["department"]]
        lines.append(
            f'{row["department"]} | {row["risk"]} | {row["utilization"]:.1%} | '
            f'{row["appointments"]} | {row["staff_available"]} | '
            f'{row["emergency_cases"]} | {next_day["utilization"]:.1%}'
        )
    return "\n".join(lines)
