from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit

import requests

MODEL = "gemma2:2b"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
_EXPLANATION_CACHE: dict[tuple, dict] = {}
_CLINICAL_TERMS = (
    "diagnos",
    "symptom",
    "treatment",
    "medication",
    "medicine",
    "disease",
    "prognos",
    "patient",
    "clinical",
    "prescription",
    "therapy",
)


def _tags_url() -> str:
    parts = urlsplit(OLLAMA_URL)
    return urlunsplit((parts.scheme, parts.netloc, "/api/tags", "", ""))


@lru_cache(maxsize=1)
def _probe_ollama() -> bool:
    try:
        response = requests.get(_tags_url(), timeout=2)
        response.raise_for_status()
        models = response.json().get("models", [])
        return any(
            item.get("name", "").split(":")[0] == MODEL.split(":")[0]
            and item.get("name", "").split(":")[-1].startswith(MODEL.split(":")[-1])
            for item in models
        )
    except (requests.RequestException, ValueError, AttributeError, TypeError):
        return False


def ollama_available(refresh: bool = False) -> bool:
    if refresh:
        _probe_ollama.cache_clear()
    return _probe_ollama()


def _fallback_explanation(evidence: dict) -> dict:
    demand = evidence["demand_minutes"]
    capacity = evidence["capacity_minutes"]
    percent = evidence["utilization"] * 100
    return {
        "problem": (
            f'Demand is {demand} minutes against {capacity} minutes of capacity '
            f"({percent:.1f}% utilization)."
        ),
        "risk_window": "Current shift; review staffing and queues today.",
        "actions": [
            "Reassign available staff to this department.",
            "Defer non-urgent work where operationally appropriate.",
            "Prioritize emergency cases in the work queue.",
        ],
    }


def _safe_json(content: str) -> dict | None:
    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", content, flags=re.IGNORECASE)
    try:
        parsed = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    problem = parsed.get("problem")
    risk_window = parsed.get("risk_window")
    actions = parsed.get("actions")
    if (
        not isinstance(problem, str)
        or not problem.strip()
        or not isinstance(risk_window, str)
        or not risk_window.strip()
        or not isinstance(actions, list)
        or len(actions) != 3
        or any(not isinstance(action, str) or not action.strip() or len(action.split()) >= 15 for action in actions)
    ):
        return None
    return {"problem": problem.strip(), "risk_window": risk_window.strip(), "actions": [a.strip() for a in actions]}


def explain_bottleneck(evidence: dict) -> tuple[dict, str]:
    cache_key = tuple(sorted(evidence.items()))
    if not ollama_available():
        return _EXPLANATION_CACHE.setdefault(cache_key + ("fallback",), _fallback_explanation(evidence)), "fallback"

    prompt = (
        "Explain this hospital operations bottleneck using only the supplied evidence. "
        "Do not calculate or invent numbers. Do not give medical advice. "
        "Return only JSON with keys problem, risk_window, actions. "
        "actions must contain exactly 3 short actions, each under 15 words.\n"
        f"Evidence: {json.dumps(evidence, separators=(',', ':'))}"
    )
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": MODEL, "prompt": prompt, "stream": False, "format": "json"},
            timeout=60,
        )
        response.raise_for_status()
        content = response.json().get("response", "")
        parsed = _safe_json(content)
        if parsed is not None:
            _EXPLANATION_CACHE[cache_key + ("local",)] = parsed
            return parsed, "local"
    except (requests.RequestException, ValueError, AttributeError, TypeError):
        pass
    return _EXPLANATION_CACHE.setdefault(cache_key + ("fallback",), _fallback_explanation(evidence)), "fallback"


def _department_answer(question: str, context: str) -> str | None:
    from backend.metrics import forecast_metrics, today_metrics

    normalized = question.casefold()
    departments = sorted(today_metrics()["department"].tolist(), key=len, reverse=True)
    department = next((name for name in departments if name.casefold() in normalized), None)
    if department is None:
        return None

    today = today_metrics().set_index("department").loc[department]
    tomorrow = forecast_metrics().set_index("department").loc[department]
    if any(word in normalized for word in ("forecast", "tomorrow", "next day")):
        return (
            f"{department} is forecast at {tomorrow['utilization']:.1%} utilization tomorrow "
            f"from {tomorrow['appointments']:.1f} average appointments and "
            f"{tomorrow['emergency_cases']:.1f} average emergency cases."
        )
    return (
        f"{department} is {today['risk'].lower()} today at {today['utilization']:.1%} utilization: "
        f"{today['appointments']} appointments, {today['staff_available']} staff, "
        f"{today['emergency_cases']} emergency cases."
    )


def _rule_based_answer(question: str, context: str) -> str:
    from backend.metrics import forecast_metrics, today_metrics

    normalized = question.casefold()
    if any(term in normalized for term in _CLINICAL_TERMS):
        return "This tool covers operational data only."

    department_answer = _department_answer(question, context)
    if department_answer:
        return department_answer

    today = today_metrics()
    if "forecast" in normalized or "tomorrow" in normalized:
        forecast = forecast_metrics()
        highest = forecast.iloc[0]
        return (
            f"Tomorrow's highest forecast utilization is {highest['department']} at "
            f"{highest['utilization']:.1%}. Forecasts use seven-day averages of appointments "
            "and emergency cases, plus recent average staffing and task duration."
        )
    if "critical" in normalized or "warning" in normalized:
        risk = "Critical" if "critical" in normalized else "Warning"
        matches = today.loc[today["risk"] == risk, "department"].tolist()
        return f"{risk} departments today: {', '.join(matches) if matches else 'none'}."
    if any(term in normalized for term in ("overload", "busiest", "highest", "most")):
        busiest = today.iloc[0]
        return (
            f"{busiest['department']} is most overloaded today at {busiest['utilization']:.1%} "
            f"utilization ({busiest['demand_minutes']} demand minutes vs "
            f"{busiest['capacity_minutes']} capacity minutes)."
        )
    return (
        "I can answer operational questions such as “Which departments are critical?”, "
        "“What is the forecast tomorrow?”, or “How is Radiology doing?”"
    )


def answer_question(question: str, context: str) -> tuple[str, str]:
    question = question.strip()
    if len(question) > 300:
        return "Please keep your question to 300 characters or fewer.", "fallback"
    if any(term in question.casefold() for term in _CLINICAL_TERMS):
        return "This tool covers operational data only.", "fallback"
    if not ollama_available():
        return _rule_based_answer(question, context), "fallback"

    prompt = (
        "Answer the user's question using only this supplied operational data context. "
        "Do not calculate or invent numbers. Do not give medical advice. "
        "If the answer is absent from the context, say so briefly.\n"
        f"Context:\n{context}\nQuestion: {question}"
    )
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": MODEL, "prompt": prompt, "stream": False},
            timeout=60,
        )
        response.raise_for_status()
        answer = response.json().get("response", "").strip()
        if answer:
            return answer, "local"
    except (requests.RequestException, ValueError, AttributeError, TypeError):
        pass
    return _rule_based_answer(question, context), "fallback"
