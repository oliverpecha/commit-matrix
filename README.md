# CommitMatrix 🧬

**Architectural telemetry and systemic risk scoring for Git repositories.**

Stop measuring developer velocity by counting lines of code. CommitMatrix is a lightweight, high-performance telemetry engine that converts raw Git history into an interactive flight console. It exposes technical debt, visualizes architectural coupling, and highlights dangerous codebase mutations before they reach production.

---

## 🧠 The CIRSD Framework

CommitMatrix abandons raw line counts in favor of the **CIRSD** scoring algorithm. Every commit is evaluated across five dimensions, yielding a maximum score of 15 points:

* **[ C ] Complexity (1-3):** Measures logical branching and cyclomatic depth. High complexity without high impact is technical debt.
* **[ I ] Impact (1-3):** The breadth of the systemic functional effect. The actual value delivered to the codebase.
* **[ R ] Risk (1-3):** The danger of regressions or catastrophic breakages.
* **[ S ] Scope (1-3):** The surface area of unique sub-services and modules touched. Massive scope demands integration testing.
* **[ D ] Documentation (1-3):** The mitigating factor. The delta between code changes and inline comments/tests.

By cross-referencing these axes, CommitMatrix extracts advanced telemetry:
* **Fragility Index:** `(Complexity + Risk) / Documentation` (Highlights unmitigated danger)
* **Churn Rate:** `Complexity / Impact` (Highlights over-engineering and wasted energy)
* **Blast Radius:** `Scope × Risk` (The QA Siren)

## 🚀 Features

* **Systemic Risk Convergence:** An algorithmic overlay that flags "Convergence Nodes"—commits that simultaneously trigger the worst 25% of Fragility, Churn, and Blast Radius metrics.
* **Decoupled ES6 Frontend:** A blazing fast, dependency-free UI utilizing native Canvas and SVG rendering. 
* **Service Touch Heatmaps:** Visually detect tight architectural coupling by tracking which sub-services are touched chronologically.
* **Temporal & Averaging Modes:** Cycle between Daily Peak, Trailing Averages, and Volume-Weighted scoring algorithms to expose different development patterns.

## ⚙️ 1-Minute Quickstart

CommitMatrix is packaged as a zero-configuration Docker container. 

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/yourusername/commit-matrix.git](https://github.com/yourusername/commit-matrix.git)
   cd commit-matrix
Secure your environment:

Bash
cp .env.example .env
# Edit .env to set your MATRIX_TOKEN
Boot the engine:

Bash
docker compose up -d
Access the console:
Open your browser and navigate to http://localhost:8000/?repo=example-repo&token=your_secure_token_here.

📂 Data Structure
CommitMatrix expects a matrix_ledger.csv file located in data/{repo_name}/. The Python FastAPI backend dynamically routes to the correct ledger based on the URL parameter, allowing you to monitor multiple repositories from a single dashboard instance.

Built for engineers who care about the blast radius.
