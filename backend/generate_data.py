from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd


DEPARTMENTS = [
    "Radiology",
    "Emergency",
    "Laboratory",
    "Cardiology",
    "Pharmacy",
    "Orthopedics",
    "Pediatrics",
    "General OPD",
]

PROFILES = {
    "Radiology": (16, 2, 20, 1),
    "Emergency": (30, 3, 12, 4),
    "Laboratory": (35, 2, 8, 1),
    "Cardiology": (25, 3, 16, 2),
    "Pharmacy": (48, 2, 7, 1),
    "Orthopedics": (22, 2, 18, 1),
    "Pediatrics": (18, 2, 15, 1),
    "General OPD": (50, 2, 12, 1),
}


def generate_data(output_path: Path | None = None) -> Path:
    output_path = output_path or Path(__file__).resolve().parent.parent / "data" / "operations.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(2026)
    today = date.today()
    rows = []

    for days_ago in range(7, -1, -1):
        current_date = today - timedelta(days=days_ago)
        for department in DEPARTMENTS:
            appointments, staff, task_minutes, emergency_cases = PROFILES[department]
            is_today = days_ago == 0

            if is_today and department == "Radiology":
                appointments, staff, task_minutes, emergency_cases = 42, 1, 25, 4
            elif is_today and department == "General OPD":
                appointments, staff, task_minutes, emergency_cases = 65, 2, 12, 1
            else:
                appointments += rng.randint(-5, 5)
                task_minutes += rng.randint(-2, 2)
                emergency_cases = max(0, emergency_cases + rng.randint(-1, 1))

            rows.append(
                {
                    "date": current_date.isoformat(),
                    "department": department,
                    "appointments": appointments,
                    "staff_available": staff,
                    "avg_task_minutes": task_minutes,
                    "emergency_cases": emergency_cases,
                }
            )

    pd.DataFrame(rows).to_csv(output_path, index=False)
    return output_path


if __name__ == "__main__":
    print(f"Generated synthetic operations data: {generate_data()}")
