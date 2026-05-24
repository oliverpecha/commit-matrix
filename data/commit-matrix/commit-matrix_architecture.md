# Architecture Overview

This document outlines the system architecture, core modules, coupling characteristics, and systemic blast radius for the repository. Based on the structure, the system is a web-based evaluation and visualization engine that parses code commits and architectural documents against predefined rubrics.

## Core Modules

1. **Backend Engine (`backend/`)**
   * **`main.py`**: The primary application server (likely FastAPI or Flask) handling API requests and serving templates.
   * **`parser.py`**: The core logic module responsible for ingesting inputs (diffs, architecture documents) and evaluating them against the rubric definitions.
   * **Containerization**: Managed via `Dockerfile` and orchestrated via the root `docker-compose.yml`.

2. **Frontend Application (`static/`, `templates/`)**
   * **Templates (`templates/`)**: Server-rendered HTML layouts (`layout.html`, `matrix.html`) providing the structural DOM.
   * **Core State & Data (`static/js/core/`)**: Manages application state (`state.js`) and API communication/data processing (`dataEngine.js`).
   * **UI & Visualization (`static/js/charts/`, `static/js/ui/`)**: Modular components for rendering complex data, including heatmaps, data tables, terminal emulators, and charts.

3. **Rubric Domain (`rubrics/`)**
   * The central source of truth for evaluation criteria. Contains markdown-based rulesets (`plan.md`, `ship.md`, `flux.md`, etc.) that dictate how the backend parser scores or categorizes inputs.

4. **Calibration Framework (`calibration/`)**
   * A comprehensive testing and validation suite (`calibrate.py`).
   * **Fixtures**: Contains highly structured test cases (`typical`, `adversarial`, `floor`) for each rubric, including input data (`commit.diff`, `architecture.md`) and expected outputs (`expected.json`).

5. **Maintenance & Operations (Root Scripts)**
   * A suite of utility scripts (`fix_all.py`, `fix_duplicates.py`, `patch_ansi.py`, `fix_visibility.py`) used for data sanitization, state correction, and environment management.

---

## Architectural Coupling

* **Backend ↔ Rubrics (Tight Coupling)**: The `parser.py` is heavily dependent on the exact schema and structure of the markdown files in the `rubrics/` directory. Any structural change to the rubrics requires a corresponding update to the parser.
* **Calibration ↔ Backend/Rubrics (Tight Coupling)**: The calibration suite acts as a strict contract monitor. It is tightly coupled to both the parser's logic and the rubrics' definitions. Changes to either will immediately invalidate the `expected.json` fixtures.
* **Frontend ↔ Backend (Loose/Moderate Coupling)**: The frontend operates as a decoupled Single Page Application (SPA) or hybrid app, communicating with the backend via `dataEngine.js`. It relies on a stable JSON contract from the backend API.
* **Frontend Core ↔ UI Components (Moderate Coupling)**: UI components (`heatmap.js`, `terminal.js`, `chartCtrl.js`) are coupled to the centralized state manager (`state.js`), ensuring synchronized updates across the dashboard.

---

## Systemic Blast Radius

### High Blast Radius
* **`backend/parser.py`**: The most critical operational component. Bugs or changes here will alter evaluation results system-wide, break the frontend data contract, and fail the entire calibration suite.
* **`rubrics/*.md`**: Modifying the domain rules directly impacts the business logic. A change to a rubric alters how inputs are evaluated, requiring cascading updates to calibration fixtures and potentially frontend visualization logic.
* **`static/js/core/state.js` & `dataEngine.js`**: Changes to frontend state management or data ingestion will affect all downstream UI components simultaneously.

### Medium Blast Radius
* **`backend/main.py`**: Changes to routing or middleware affect API availability and template rendering, but do not alter the core evaluation logic.
* **`templates/matrix.html`**: Structural DOM changes will break the bindings of the frontend JavaScript components (e.g., `tableCtrl.js`, `heatmap.js`).

### Low Blast Radius
* **`calibration/`**: Changes here are isolated to the CI/CD or local testing environments. While critical for validation, breaking the calibration suite does not directly impact the running production system.
* **Root Utility Scripts (`fix_*.py`)**: These are ad-hoc operational tools. Errors here are localized to the specific maintenance task being performed and do not affect the continuous runtime of the application.
* **Individual UI Components (`static/js/ui/tooltips.js`, etc.)**: Visual or logical bugs in a specific UI module are isolated to that specific feature and will not crash the broader application state.