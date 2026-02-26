# Lo**stream

An event ingestion + projection API for lo***rs/compartments/reservations (and faults), built with FastAPI HTTP endpoints and a lightweight event log.

## 1) How to run the API

### Prerequisites
- Python **3.12+**
- A virtual environment tool (recommended)

### Setup
```bash
git clone https://github.com/samiferr/candidateSamyVelvetQuasar695
cd 'candidateSamyVelvetQuasar695'
python -m venv .venv 
source .venv/bin/activate 
pip install --upgrade pip
pip install -r requirements.txt
```
Then run the API with:
```bash
python run.py
```


Once running, the API will be available at: `http://localhost:8000/`
- `POST /events` (ingest domain events)
- `GET /l***ers/{l***er_id}`
- `GET /l***ers/{l***ker_id}/compartments/{compartment_id}`
- `GET /reservations/{reservation_id}`

Interactive docs are enabled in your server configuration, check:
- `http://localhost:8000/docs` (Swagger UI)

### Event log storage
The system appends ingested events to a JSONL event log file. You can control the location via an environment variable:
```bash
bash export EVENT_LOG_PATH="event_log.jsonl
```


---

## 2) How to run tests

### Run all tests
from the project root:
```
export PYTHONPATH=$PYTHONPATH:.
pytest
```


### Run a single test file
from the project root:

```
export PYTHONPATH=$PYTHONPATH:.
```
then 
```
pytest -q lockstream/tests/test_fault_severity_behavior.py
```



### Notes
- Tests clear the JSONL event log before each test to avoid cross-test contamination.
- If you see failures due to state leaking, ensure you are not reusing an external/shared event log path.

---

## 3) Architecture & design rationale (short)

### High-level structure
- `lockstream/core/`
  - **Domain entities** and **use cases** (application rules).
  - Repository interfaces live here so the core stays independent of persistence details.
- `lockstream/infrastructure/`
  - Concrete persistence implementations:
    - Append-only **JSONL event store** for ingested events (idempotency by `event_id`)
    - In-memory/SQLite **projection store** (SQLAlchemy models) for queryable read models
- `lockstream/services/`
  - Wiring layer: builds use-cases + repositories and adapts request/response models.
- `lockstream/presentation/`
  - HTTP routing layer (web/controller concerns).
- `lockstream/schemas/` and `lockstream/openapi/`
  - API schemas and contract.

### Implementation Summary
* **Core** depends on **interfaces**, not implementations.
* **Infrastructure** depends on the **Core** to implement those interfaces.
* **Presentation** depends on **Services** to execute behavior.
* **Services** depend on **both Core and Infrastructure** to wire them together.

