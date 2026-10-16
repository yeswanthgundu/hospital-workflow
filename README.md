# HospitalFlow AI

HospitalFlow AI is a small operational dashboard that highlights synthetic department workload bottlenecks, explains the computed evidence, forecasts tomorrow's utilization, and answers questions about the dashboard. It uses no patient records, real names, or clinical data; it is not for medical decisions.

**Live app:** [https://hospital-workflow-g8rq.onrender.com/](https://hospital-workflow-g8rq.onrender.com/)

## Architecture

One FastAPI application serves the static HTML, CSS, and vanilla JavaScript dashboard alongside its JSON API. Python and pandas generate reproducible synthetic operations data and compute all metrics. Optional local Ollama (`gemma2:2b`) writes explanations and answers from the computed evidence; when Ollama is unavailable, the same app uses rule-based explanations and question answers. No cloud AI service is used.

## Local setup

Use Python 3.12:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python backend/generate_data.py
```

Optionally install and start Ollama, then download the model:

```powershell
ollama pull gemma2:2b
```

Run the app and open <http://localhost:8000>:

```powershell
uvicorn backend.main:app --reload
```

The application works fully offline locally in fallback mode when Ollama is not running. Set `OLLAMA_URL` to change the local Ollama generate endpoint (default: `http://localhost:11434/api/generate`).

## Deploy on Render

1. Push this repository to GitHub.
2. In Render, select **New +** → **Blueprint** and connect the repository.
3. Render reads `render.yaml`, installs `requirements.txt`, and starts the FastAPI app.
4. Open the [live HospitalFlow AI app](https://hospital-workflow-g8rq.onrender.com/); without Ollama it runs in fallback mode.

The generated `data/operations.csv` is committed so deployment does not need to generate data first.
