### Clean Architecture and Separation of Concerns

This project utilizes **Clean Architecture** along with the **Repository** and **Unit of Work** design patterns to ensure a highly decoupled and maintainable codebase.

### Architectural Overview

The system is designed so that dependencies always point inward. This means the **Core** remains independent of external frameworks like FastAPI or SQLAlchemy, interacting only with abstract interfaces.

---

### Layer Responsibilities

| Layer | Path | Description |
| --- | --- | --- |
| **Core** | `lockstream/core/` | Defines **what** the system does (Enterprise & Application rules).
|
| **Infrastructure** | `lockstream/infrastructure/` | Defines **how** the system stores data and talks to external systems (Adapters).
|
| **Presentation** | `lockstream/presentation/` | Defines **what the outside world calls** (HTTP Delivery).
|
| **Services** | `lockstream/services/` | The **glue** that links everything together (Composition/Wiring).
|
---

### Detailed Breakdown

#### 1. Core (Domain + Use Cases)

This layer focuses strictly on business logic and rules, such as validating reservations or defining degraded compartments.

* **Entities**: Domain objects holding business meaning.
* **Use Cases**: Orchestration of actions like ingesting events or rebuilding projections.
* **Repository Interfaces**: Abstract "ports" or contracts that the core needs, without committing to specific storage technologies.

#### 2. Infrastructure (Adapters for Persistence & IO)

Contains concrete implementations of the ports defined in the Core.
* **Event Store**: JSONL-based append-only log with idempotency.
* **Projections**: SQLAlchemy-based models and repository implementations.
* **Config**: Settings for database connections and event log paths.
* **Isolation**: All SQL, file IO, and session handling stay outside the core.

#### 3. Presentation (HTTP)

The delivery mechanism where FastAPI routing and controllers reside.

* Parses incoming HTTP requests.
* Returns appropriate HTTP responses and status codes.
* Calls the service layer to execute work.
* Focuses purely on request/response orchestration.

#### 4. Services (Composition & Wiring)

The coordination layer that instantiates the components.
* Creates concrete infrastructure repositories.
* Instantiates core use cases.
* Maps and converts between API schemas and core entities/DTOs.
---

### Summary
* **Core** depends on **interfaces**, not implementations.
* **Infrastructure** depends on the **Core** to implement those interfaces.
* **Presentation** depends on **Services** to execute behavior.
* **Services** depend on **both Core and Infrastructure** to wire them together.

---

### Future Improvements

* **Refactoring**: Wrap `ingest_event` use case logic into functions for better readability and testability.
* **Quality**: Increase test coverage.
* **Performance**: Improve general performance and optimize SQL indexes for better searching.

