# System Architecture

## Core Modules

1. **Backend Engine (`backend/`)**
   - **Components:** `main.py` (Application entry point/API), `parser.py` (Core processing logic).
   - **Responsibility:** Serves as the central processing unit. It ingests data (likely git diffs/commits), parses them using `parser.py`, and evaluates them against defined rubrics. It also serves the web application.

2. **Frontend & Visualization (`static/`, `templates/`)**
   - **Components:** `templates/` (HTML layouts), `static/js/core/` (State & Data Engine), `static/js/charts/` & `static/js/ui/` (Visual components).
   - **Responsibility:** Provides the user interface. The `dataEngine.js` and `state.js` manage client-side data flow, while specialized UI components (heatmaps, terminal, charts) render the evaluation metrics and parsed results.

3. **Rubric Definitions (`rubrics/`)**
   - **Components:** Markdown files (`plan.md`, `ship.md`, `grid.md`, etc.).
   - **Responsibility:** Acts as the domain-specific configuration layer. These files define the rules, metrics, and criteria used by the backend parser to evaluate inputs.

4. **Calibration & Testing Framework (`calibration/`)**
   - **Components:** `calibrate.py`, `fixtures/` (Categorized by rubric and scenario: typical, adversarial, floor).
   - **Responsibility:** A robust validation harness. It tests the backend parser's accuracy by running predefined `commit.diff` files against the rubrics and comparing the output to `expected.json`.

5. **Infrastructure & Orchestration (Root Directory)**
   - **Components:** `docker-compose.yml`, `Dockerfile`, `install.sh`, `uninstall.sh`, `.env`.
   - **Responsibility:** Manages containerization, environment configuration, and deployment lifecycle.

---

## Architectural Coupling

- **Backend ↔ Rubrics (Tight Coupling):** The `parser.py` is highly dependent on the structural schema of the markdown files in `rubrics/`. Changes to the rubric authoring format require corresponding updates to the parser.
- **Backend ↔ Frontend (Loose to Medium Coupling):** The frontend relies on the backend for data delivery (likely via REST/JSON given `dataEngine.js`). The templates (`layout.html`, `matrix.html`) suggest server-side initial rendering with client-side hydration/takeover.
- **Calibration ↔ Backend/Rubrics (High Dependency):** The calibration suite acts as an integration test layer. It is strictly coupled to the expected outputs of the parser and the current state of the rubrics.
- **Frontend UI ↔ Frontend Core (High Coupling):** The UI components (`heatmap.js`, `chartCtrl.js`) are tightly bound to the data structures emitted by `dataEngine.js` and `state.js`.

---

## Systemic Blast Radius

| Module | Blast Radius | Impact Description |
| :--- | :--- | :--- |
| **Backend (`parser.py`)** | **Critical** | Structural changes here will break data ingestion, evaluation logic, frontend rendering, and the entire calibration suite. |
| **Backend (`main.py`)** | **High** | Modifying the API/routing layer will sever the connection between the frontend and the data engine, causing total UI failure. |
| **Frontend Core (`core/*.js`)** | **High** | Bugs in state management or the data engine will cascade to all UI components, rendering charts and tables unusable. |
| **Rubrics (`rubrics/*.md`)** | **Medium** | Modifying a specific rubric (e.g., `flux.md`) isolates the blast radius to the evaluation of that specific category. It will break calibration tests for that category but will not crash the system. |
| **Frontend UI (`ui/`, `charts/`)** | **Low** | Changes to specific visual components (e.g., `tooltips.js`) are isolated and will only affect the rendering of that specific element. |
| **Calibration (`calibration/`)** | **None (Production)** | Changes here only affect the CI/CD pipeline and local development validation. They have zero impact on the running production system. |