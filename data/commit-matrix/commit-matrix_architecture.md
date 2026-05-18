# Architecture Overview: Commit Matrix System

## 1. System Overview
The repository defines a client-server web application (likely named "Commit Matrix") designed to parse, analyze, and visualize structured data (presumably Git commits based on repository artifacts). It utilizes a Python-based backend for data processing/serving and a modular JavaScript frontend for stateful data visualization. 

## 2. Core Modules

### 2.1. Backend API & Processing Engine (`/backend`)
*   **API Gateway/Router (`main.py`)**: The primary entry point for the backend service (likely Flask or FastAPI). Handles HTTP requests, static file routing, and serves base HTML templates.
*   **Parsing Engine (`parser.py`)**: The core business logic module responsible for ingesting raw data, applying transformations, and formatting it for frontend consumption.
*   **Business Rules/Rubrics (`rubrics/cirsd.md`)**: Externalized markdown-based rules or configurations used by the parser to categorize or evaluate data.

### 2.2. Frontend Visualization Client (`/static`, `/templates`)
*   **Core State & Data Management (`js/core/`)**:
    *   `dataEngine.js`: Handles fetching, filtering, and transforming backend data payloads for UI consumption.
    *   `state.js`: Centralized state management for the client session.
    *   `constants.js`: Shared immutable application configurations.
*   **Visualization Layer (`js/charts/`)**: Encapsulates graphing logic (`chartCtrl.js`) and third-party graphing integrations/extensions (`plugins.js`).
*   **UI Components (`js/ui/`)**: Distinct presentation controllers for specific layout domains, including `heatmap.js`, `tableCtrl.js`, and contextual `tooltips.js`.
*   **View Templates (`/templates`)**: Server-side injected base layouts (`layout.html`, `matrix.html`) that bootstrap the JavaScript application.

### 2.3. Orchestration & Deployment (`/`)
*   **Containerization (`docker-compose.yml`, `backend/Dockerfile`)**: Defines the infrastructure topology, networking, and volume bindings for local and deployed environments.
*   **Lifecycle Scripts (`install.sh`, `uninstall.sh`)**: Imperative setup and teardown routines for host-level configuration.

---

## 3. Architectural Coupling

*   **Client-Server Coupling (Moderate)**: The frontend and backend are decoupled at the data tier (communicating presumably via JSON over REST/HTTP), but are temporally coupled at the presentation tier since `main.py` likely serves the base Jinja/HTML files from `/templates`. 
*   **Frontend Data-to-View Coupling (Loose)**: The UI components (`charts/`, `ui/`) subscribe to or read from the `core/state.js` and `core/dataEngine.js`. This unidirectional data flow pattern isolates view logic from data retrieval.
*   **Backend Ingestion Coupling (Tight)**: `main.py` is tightly coupled to `parser.py`. The API layer acts as a direct proxy for the parser's output, meaning parser schema changes directly mutate the API contract.

---

## 4. Systemic Blast Radius

### High Blast Radius
*   **`backend/parser.py`**: Changes to the data structures generated here will cascade across the entire system. A schema mutation will break the API contract, causing cascading failures in `dataEngine.js`, `state.js`, and all downstream visualizations.
*   **`static/js/core/state.js` & `dataEngine.js`**: Modifying state lifecycle or data transformation logic risks bringing down the entire frontend SPA, as all UI modules depend on these singletons.
*   **`docker-compose.yml` & `.env`**: Infrastructure changes affect system availability, port bindings, and service discovery.

### Medium Blast Radius
*   **`backend/main.py`**: Changes to route definitions or middleware affect client-server connectivity. Bugs here result in localized 404/500 errors preventing specific views from loading.
*   **`templates/layout.html`**: Altering the DOM structure, script load order, or CSS injection will affect the foundational rendering of all pages inheriting this layout.

### Low Blast Radius
*   **Specific UI Controllers (e.g., `heatmap.js`, `tableCtrl.js`)**: Isolated presentation logic. A bug in the heatmap will generally not corrupt the state or crash the table view, provided state immutability is respected.
*   **`static/css/matrix.css`**: Purely aesthetic impact. Visual regressions are constrained to the browser's rendering engine without halting application logic.