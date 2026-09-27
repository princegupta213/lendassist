# Product Requirements Document (PRD)
## LendAssist — AI Lending Conversation Orchestration Layer

**Author**: Senior Product Manager, AI & Lending Platforms  
**Status**: Approved / Production Blueprint  
**Version**: 2.0 (AI-Native Architecture)  
**Target Systems**: Web SDK, iOS/Android Apps, Core Banking / LOS / LMS, Agent CRM  

---

## 1. Product Overview
**LendAssist** is an enterprise AI-native conversation orchestration layer for retail lending products (Home Loans, Loan Against Mutual Funds [LAMF], and Overdraft Facilities). 

Rather than functioning as a standard chatbot that mechanically matches FAQs or blindly generates generative text, LendAssist is an **intelligent decision engine**. It continuously evaluates customer intent, context, and multi-factor risk signals to make one of three authoritative decisions at every turn:
1. **ANSWER**: Communicate verified information naturally using adaptive response constraints.
2. **ACT**: Execute verified banking workflows (e.g. CAMS RTA lien marking, penny drop verification, e-sign).
3. **ESCALATE**: Intelligently transfer conversations to human specialists when continuing with AI introduces financial, compliance, operational, or customer experience risk.

```
                         CUSTOMER (Web / App / WhatsApp)
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │   UNDERSTANDING ENGINE    │
                         │  Intent + Speech Act + PII│
                         └─────────────┬─────────────┘
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │     DIALOGUE MANAGER      │
                         │   Context + Funnel FSM    │
                         └─────────────┬─────────────┘
                                       │
             ┌─────────────────────────┼─────────────────────────┐
             ▼                         ▼                         ▼
         RAG (KB)                  LOS / RTA                   APIs
    (KFS / Regulations)       (CAMS / Core Banking)      (Penny Drop / OTP)
             │                         │                         │
             └─────────────────────────┼─────────────────────────┘
                                       ▼
                         ┌───────────────────────────┐
                         │      VERIFIED FACTS       │
                         └─────────────┬─────────────┘
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │  RESPONSE POLICY ENGINE   │
                         │  • Brevity boundaries     │
                         │  • Tone & Priority        │
                         │  • Escalation Decision    │
                         └─────────────┬─────────────┘
                                       │
                        ┌──────────────┴──────────────┐
                        ▼                             ▼
                 RESPONSE LLM                  HUMAN ESCALATION
             (Natural Synthesis)              (Agent Workspace)
                        │                             │
                        ▼                             ▼
                    CUSTOMER                   HUMAN SPECIALIST
```

---

## 2. Problem Statement
Traditional lending chatbots suffer from four structural dysfunctions:
1. **Robotic Database Expositions**: Systems mechanically expose database columns (`Interest rate: 10.5% p.a. on simple daily reducing balance. Foreclosure: Nil.`) instead of interpreting and synthesizing facts into human-level advisory sentences.
2. **Over-Compression vs. Bloat**: Systems swing between rigid single-line answers that omit essential context and verbose multi-paragraph essays loaded with conversational filler (*"I'd be happy to assist you today..."*).
3. **Binary, Inflexible Escalation**: Chatbots either escalate prematurely (eroding automation efficiency) or cling to the conversation despite mounting customer frustration, high compliance risk, or technical errors.
4. **Context Loss During Handoff**: When a customer reaches a human executive, they are forced to re-explain their situation from scratch, re-verify their identity, and re-submit details.

---

## 3. Product Goals
* **Automate Safely**: Enable 70%+ self-service resolution for routine inquiries and standard LAMF origination workflows.
* **Reduce Customer Effort**: Limit repetitive questioning; provide instant KFS breakdowns and proactive state resumption across question interruptions.
* **Risk-Aware Escalation**: Detect high-risk triggers (fraud, demise, disputes) and route them with full context to specialists within 0 seconds of detection.
* **Zero Factual Hallucination**: Never permit the generative model to invent interest rates, credit limits, or foreclosure policies.

---

## 4. Product Principles
1. **Verified Facts, Natural Language**: The LLM may interpret, paraphrase, and synthesize verified facts, but must never invent financial information.
2. **Brevity Without Loss of Meaning**: The shortest natural response that fully satisfies the customer's intent is preferred.
3. **Escalation is a Strategic Product Decision**: Escalation is governed by multi-factor scoring (Risk + Explicit Request + Failure Count + Uncertainty + Frustration + Workflow Error).
4. **Humans Receive Complete Context**: No customer should ever repeat themselves. Human agents receive structured handoff dossiers containing history, diagnoses, and AI recommendations.
5. **AI Must Know Its Boundaries**: The goal is not maximum automation at all costs; the goal is **appropriate, safe automation**.

---

## 5. Target Users & Personas

### Primary Persona: The Borrower
* **Needs**: Instant clarity on borrowing capacity against mutual funds, transparent interest rates, simple step-by-step digital loan setup, and immediate resolution of doubts.
* **Pain Points**: Confusing financial jargon, fear of mutual fund liquidation, repetitive chatbot loops.

### Secondary Persona: The Customer Support Specialist
* **Needs**: Instant situational awareness when taking over escalated chats; immediate visibility into what failed, what the customer said, and recommended actions.
* **Pain Points**: Blind handoffs with no history; spending the first 5 minutes of every call re-asking standard questions.

### Stakeholders: Risk, Operations & Compliance
* **Needs**: Audit logs of every recommendation; strict adherence to RBI digital lending guidelines and Fair Practices Codes.

---

## 6. Core Use Cases

### A. Informational Inquiries
* *"What's my interest rate?"* $\rightarrow$ Direct, natural explanation of 10.5% p.a. simple daily reducing balance.
* *"What are the foreclosure charges?"* $\rightarrow$ Clarification of ₹0 penalty and prepayment terms.

### B. Agreement & KFS Understanding
* *"Explain key points from the agreement."* $\rightarrow$ 4 natural bullets covering credit line, interest rate, nil foreclosure, and linked repayment bank, followed by an offer to explain charges.

### C. Workflow Execution (LAMF Origination)
* **Step 1: Portfolio Fetch**: PAN-based lookup via CAMS/KFintech registrar APIs.
* **Step 2: Limit Selection**: LTV calculation (50% on equity) with flexible natural input parsing (`250000`, `2.5L`, `full limit`).
* **Step 3: Lien Authorization**: CAMS OTP verification (`9032`) without selling mutual fund units.
* **Step 4: Bank Mandate & Disbursal**: Penny Drop verification + digital KFS execution.

### D. Real-Time Status & Mutation
* *"Has my lien been marked?"* $\rightarrow$ Real-time CAMS registry lookup.
* *"Change my bank account"* $\rightarrow$ Penny drop verification workflow.

### E. Complex & High-Risk Escalations
* *"Someone stole my phone and took a loan."* $\rightarrow$ Immediate account freeze + Priority 1 Fraud Desk handoff.
* *"What happens if I die while the loan is active?"* $\rightarrow$ Nominee transmission principle + Senior Loan Settlement Specialist connection.

---

## 7. Response Policy Engine Specification
The Policy Engine acts as a boundary constraint system. It prescribes:

```json
{
  "archetype": "SIMPLE_FACT | MULTI_POINT | WORKFLOW | COMPLEX_REQUEST | COMPLAINT",
  "max_sentences": 1,
  "max_bullets": 0,
  "format_style": "sentence | bullets | step_action",
  "tone": "conversational_natural | reassuring | direct_clear | respectful_concise | empathetic_swift",
  "information_priority": ["annual percentage rate", "daily reducing calculation"],
  "allowed_facts": ["10.5% p.a.", "daily reducing balance"],
  "allow_followup_question": false,
  "followup_purpose": null,
  "prohibited_patterns": ["as an ai", "the applicable interest rate is", "as per available records"]
}
```

---

## 8. Natural Language Contract (Response LLM)
The final generation LLM adheres to the **12-Rule Natural Language Contract**:
1. Ground truth originates solely from `VERIFIED_FACTS`.
2. Paraphrase and synthesize facts naturally as a human advisor.
3. Zero invention or inference of unsupported financial terms.
4. Answer the user's primary intent first.
5. Avoid database label dumping (`Credit line: ₹2.9L`).
6. Avoid robotic boilerplate (*"Kindly note that..."*, *"Please be informed..."*).
7. Do not restate user questions verbatim.
8. Eliminate conversational filler (*"I would be delighted to assist..."*).
9. Treat response policies as boundaries, not verbatim templates.
10. Respect assigned sentence and bullet budgets.
11. Select and prioritize only facts relevant to the customer's question.
12. Sound like an experienced financial services professional.

---

## 9. Risk-Aware Escalation Decision System

### Multi-Factor Scoring Formula
$$\text{Escalation Score} = S_{\text{risk}} + S_{\text{explicit}} + S_{\text{failure}} + S_{\text{uncertainty}} + S_{\text{frustration}} + S_{\text{workflow}}$$

| Signal Factor | Weight Range | Trigger Condition |
| :--- | :---: | :--- |
| **Risk Score ($S_{\text{risk}}$)** | $0.0 - 0.80$ | Fraud ($0.80$), Demise ($0.55$), Dispute ($0.50$), Hardship ($0.50$) |
| **Explicit Request ($S_{\text{explicit}}$)** | $0.0 \text{ or } 0.85$ | Customer demands human agent / executive |
| **Repeated Failure ($S_{\text{failure}}$)** | $0.0 - 0.30$ | 1 error ($0.10$), 2 errors ($0.20$), $\ge 3$ errors ($0.30$) |
| **AI Uncertainty ($S_{\text{uncertainty}}$)** | $0.0 - 0.25$ | Model confidence $< 0.75$ ($0.15$), $< 0.60$ ($0.25$) |
| **Customer Frustration ($S_{\text{frustration}}$)** | $0.0 - 0.25$ | Negative sentiment, repeated complaints |
| **Workflow Failure ($S_{\text{workflow}}$)** | $0.0 - 0.35$ | Gateway timeout, penny drop reject, API disconnect |

### Escalation Tiers
* **Level 0 (Score $< 0.30$)**: Autonomous AI Self-Service.
* **Level 1 ($0.30 \le \text{Score} < 0.50$)**: Self-Service with Silent Telemetry Flagging.
* **Level 2 ($0.50 \le \text{Score} < 0.70$)**: Assisted Handoff (Specialist introduction + context draft).
* **Level 3 ($\text{Score} \ge 0.70$)**: Priority Escalation (Workflow freeze, P1/P2 ticket, agent workspace dispatch).

---

## 10. Agent Handoff Dossier Schema
When an escalation triggers, the agent receives an actionable context dossier:

```json
{
  "ticket_id": "TICK-LA-88391",
  "priority": "P1_CRITICAL",
  "escalation_level": "LEVEL_3_PRIORITY",
  "escalation_score": 0.85,
  "customer": {
    "customer_id": "CUST-9428",
    "name": "Aryan Agarwal",
    "application_id": "APP-LAMF-8831",
    "product": "Loan Against Mutual Funds (LAMF)",
    "phone_masked": "+91-98XXXX1234",
    "linked_bank": "HDFC Bank ending 3294",
    "sanctioned_limit": "₹2,50,000"
  },
  "conversation": {
    "turn_count": 5,
    "detected_intent": "FRAUD_ESCALATION",
    "summary": "Customer reports unauthorized transaction following phone theft."
  },
  "problem": {
    "category": "Unauthorized Activity & Fraud Alert",
    "stated_issue": "Someone stole my phone and took a loan",
    "contributing_factors": { "risk": 0.80, "uncertainty": 0.05 }
  },
  "system_context": {
    "workflow_state": "AUTOPAY_REVIEW",
    "actions_attempted": [
      "Facility registered: LAMF (₹2,50,000)",
      "Account marked for immediate security freeze"
    ]
  },
  "ai_recommendation": {
    "reason_for_escalation": "Customer reports unauthorized loan or phone theft.",
    "suggested_agent_action": "1. Confirm identity. 2. Verify temporary loan lock. 3. Initiate fraud investigation protocol.",
    "assigned_desk": "Priority Fraud Desk"
  },
  "customer_last_message": "Someone stole my phone and took a loan",
  "status": "OPEN"
}
```

---

## 11. Success Metrics

### Customer Experience Metrics
* **Successful Resolution Rate (North Star)**: $\ge 82\%$ resolved appropriately.
* **Customer Effort Score (CES)**: $\le 3.5$ turns to resolution.
* **First-Contact Resolution (FCR)**: $\ge 75\%$.
* **Customer Satisfaction (CSAT)**: $\ge 4.4 / 5.0$.

### AI System Quality Metrics
* **Hallucination Rate**: $< 0.5\%$ unsupported statements.
* **Escalation Precision**: $\ge 88\%$ of escalations genuinely required human judgment.
* **Escalation Recall**: $\ge 98\%$ of critical risk scenarios escalated immediately.
* **Average Response Latency**: $< 250\text{ ms}$ for deterministic flows, $< 1.2\text{ s}$ for generative synthesis.

### Business & Operational Metrics
* **Automation Containment Rate**: $70 - 75\%$ safe automation.
* **Average Handle Time (AHT) Reduction for Agents**: $45\%$ faster handle time due to rich context dossiers.

---

## 12. Phased Roadmap

| Phase | Milestone | Key Deliverables | Status |
| :--- | :--- | :--- | :---: |
| **Phase 1** | Foundation | Dual-LLM engine, 6-domain routing matrix, CAMS/LOS simulators, FSM | **Completed (100%)** |
| **Phase 2** | Boundaries & Synthesis | Response Policy Layer, Natural Language Contract, Anti-Robotic Validator | **Completed (100%)** |
| **Phase 3** | Risk-Aware Orchestration | Multi-factor Escalation Engine, Agent Workspace, Failure Injection Simulator | **Current Milestone** |
| **Phase 4** | Production Enterprise | Core Banking e-NACH connectors, Digilocker KYC, Live WebRTC Voice | Future |

