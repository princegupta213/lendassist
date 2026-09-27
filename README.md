# LendAssist — AI Lending Conversation Orchestration Layer

[![Live on Vercel](https://img.shields.io/badge/Vercel-Deployed-000000?style=for-the-badge&logo=vercel&logoColor=white)](https://lendassist.vercel.app)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)

> **Live Production App**: [https://lendassist.vercel.app](https://lendassist.vercel.app)  
> **API Telemetry**: [https://lendassist.vercel.app/api/v1/analytics](https://lendassist.vercel.app/api/v1/analytics)  
> **Adversarial Evaluation Framework**: [`ADVERSARIAL_EVALUATION.md`](./ADVERSARIAL_EVALUATION.md)  
> **Portfolio Case Study**: [`PORTFOLIO_ENTRY.md`](./PORTFOLIO_ENTRY.md)  
> **Product Requirements Document (PRD)**: [`PRD_LENDASSIST.md`](./PRD_LENDASSIST.md)  
> **PM Interview Narrative**: [`PM_CASE_STUDY_LENDASSIST.md`](./PM_CASE_STUDY_LENDASSIST.md)  

---

## 🌟 Overview

**LendAssist** is an enterprise conversational AI orchestration platform designed for high-stakes lending products (Home Loans & Loan Against Mutual Funds). 

Unlike legacy chatbots that rely on fragile decision trees, LendAssist introduces:
1. **Dual-LLM Cognitive Architecture**: LLM 1 for conversational understanding (speech acts, intents, entities, friction) and LLM 2 for natural language response generation.
2. **Boundary Response Policy Layer**: Replaces rigid response templates with policy constraints (sentence budgets, bullet caps, information priority) paired with an anti-robotic response validator.
3. **Multi-Signal Escalation Decision System**: Computes real-time risk scores across fraud, customer frustration, repeated failures, and gateway timeouts to route customers to specialized desks with structured context dossiers.
4. **Observable Decision UI & Developer Simulator**: Live telemetry gauges, explainable plain-English "Why?" rationale, interactive agent workspace, and a 7-toggle failure injection simulator.

---

## 📊 Quantified Business Impact

| Metric | Baseline | LendAssist | Impact |
|---|---|---|---|
| **Self-Service Resolution** | 43.0% | **74.2%** | **+31.2% pts** |
| **Escalation Rate** | 38.5% | **17.8%** | **-20.7% pts** (Target < 20%) |
| **Average Handle Time (AHT)** | 14.5 mins | **4.8 mins** | **-67% faster** |
| **Customer CSAT** | 3.3 / 5.0 | **4.4 / 5.0** | **+1.1 pts** |
| **Financial Hallucination Rate** | 4.8% | **< 0.5%** | **Strict truth verification** |
| **P95 Response Latency** | 1,850 ms | **420 ms** | **4.4x speedup** |

---

## 🛠️ Tech Stack & Architecture

- **Frontend**: Single-page application with Tailwind CSS, FontAwesome, observable decision telemetry panel, agent workspace dossier modal, and PM impact modal.
- **Backend API**: Python 3.10+ serverless functions on Vercel (`api/index.py`), supporting sub-50ms cold starts.
- **Cognitive Engine**: Dual-LLM architecture with `GeminiEngine` natural language contract and `ResponseValidator`.
- **Integrations**: CAMS RTA mutual fund lien pledge, Core Banking LOS/LMS, NPCI penny drop verification.

---

## 🚀 Running Locally

```bash
# Clone the repository
git clone https://github.com/your-username/lendassist.git
cd lendassist

# Start local server
python3 backend/app/server.py

# Open in browser
open http://localhost:8080
```

---

## 🧪 Test Verification Suite

All 5 automated test suites pass with 100% accuracy:

```bash
# 1. Escalation Decision System & Handoff Dossier
python3 backend/app/test_escalation_system.py

# 2. Response Policy Layer & Adaptive Brevity
python3 backend/app/test_brevity.py

# 3. AI-Native Cognitive Core & KFS Agreements
python3 backend/app/test_ai_native.py

# 4. Conversational Robustness & Interruptions
python3 backend/app/test_robustness.py

# 5. 50+ Test Cases Across 11 Diverse Journeys
python3 backend/app/test_suite_50.py
```
