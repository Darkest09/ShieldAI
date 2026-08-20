# Thesis Proposal

## Title
Design and Development of a Privacy-Preserving AI Gateway for Class 'A' Commercial Banks in Kathmandu: A Zero-Trust Framework for Mitigating PII Leakage and Ensuring Compliance with NRB Cyber Resilience Guidelines and the Individual Privacy Act (2018)

---

## 1. Introduction and Background

Artificial intelligence (AI) and large language models (LLMs) are increasingly being adopted across industries, including the financial sector. Class 'A' commercial banks in Kathmandu, Nepal are beginning to explore LLM-powered tools for use cases such as customer support automation, internal policy Q&A, fraud narrative analysis, and staff productivity tools. However, these use cases introduce a critical and underexplored security risk: **sensitive personally identifiable information (PII) and financial data may be inadvertently transmitted to external third-party LLM providers** (such as OpenAI, Groq, or similar cloud-hosted services) as part of user prompts.

Nepal's banking sector is regulated by the **Nepal Rastra Bank (NRB)**, whose Cyber Resilience Guidelines place obligations on licensed financial institutions to implement technical and organizational controls over data security. Additionally, the **Individual Privacy Act, 2018 (Vyaktigat Gupta Sauchana Sambandhi Ain, 2075)** establishes legal obligations around the processing, storage, and sharing of personal information of Nepali citizens. Both frameworks create a regulatory imperative for banks to control where and how customer and employee data flows — including through AI systems.

Despite this, there is currently no standardized architectural pattern or open reference implementation that helps Class 'A' Nepali banks manage LLM-related data leakage risk. This research addresses that gap.

---

## 2. Problem Statement

When bank staff or systems send prompts to external LLMs, those prompts may contain:

- Customer names, phone numbers, citizenship numbers, addresses
- Account numbers, transaction references, financial figures
- Internal credentials, API keys, or infrastructure identifiers

Existing LLM API clients (SDKs, chat tools) have no built-in mechanism to detect or remove PII before sending it upstream. This creates:

1. **Data leakage risk** — sensitive data leaves the bank's trust boundary uncontrolled.
2. **Regulatory exposure** — potential violations of NRB cyber resilience expectations and the Individual Privacy Act (2018).
3. **Audit gaps** — no tamper-evident record of what was sent, when, and with what level of sensitivity.

---

## 3. Research Objectives

1. Design a **privacy-preserving AI gateway** that intercepts LLM API traffic from bank clients and enforces PII scrubbing before upstream transmission.
2. Implement a **zero-trust approach** specific to the AI egress channel: treat the external model and transport as untrusted; minimize every payload.
3. Incorporate **Nepal-specific PII recognizers** (citizenship numbers, mobile patterns) alongside general financial/credential patterns.
4. Build a **tamper-evident audit trail** and operator dashboard to support accountability and monitoring requirements.
5. Evaluate the prototype through **synthetic test scenarios** inspired by Class 'A' bank use cases in Kathmandu.
6. Map implemented controls to selected **NRB Cyber Resilience Guidelines** and **Individual Privacy Act (2018)** principles.

---

## 4. Research Questions

- How can a proxy gateway architecture enforce data minimization for LLM traffic in a financial institution?
- What PII entity types are most relevant to Nepali banking contexts, and how can they be reliably detected?
- How does inserting a privacy gateway affect latency, usability, and LLM response quality?
- To what extent do the implemented technical controls align with NRB and Privacy Act requirements?

---

## 5. Scope and Limitations

**In scope:**
- Design and implementation of the gateway prototype (ShieldAI)
- Pre-flight PII detection (Microsoft Presidio + spaCy NLP + custom Nepal-oriented recognizers)
- Reversible anonymization strategies: placeholder substitution, masking, and hashing
- Post-flight de-anonymization (response path vault restore)
- Hash-chained SQLite audit log and internal metrics/logs API
- React-based operator dashboard
- Evaluation with synthetic, fictional prompts only

**Out of scope:**
- Legal compliance certification (the prototype demonstrates technical controls; formal regulatory approval is outside this project)
- Production deployment at any real bank
- Multi-tenant key management, HSM, or enterprise IAM integration
- Real customer or employee data of any kind (all evaluation uses synthetic data)
- Full NRB licensing or DPIA procedures

---

## 6. Proposed Architecture

The gateway sits between **client applications** (bank staff tools, internal systems) and **external LLM providers**:

```
Bank Client (staff tool / API consumer)
         |
         | POST /v1/chat/completions
         v
+---------------------------+
|     ShieldAI Gateway      |
|  (FastAPI, port 8888)     |
|                           |
|  1. Injection scan        |
|  2. Presidio PII analysis |
|     (spaCy en_core_web_lg)|
|  3. Anonymize (vault)     |
|  4. Forward to upstream   |
|  5. De-anonymize response |
|  6. Audit log (SQLite)    |
+---------------------------+
         |
         v
External LLM (OpenAI / Groq / etc.)
```

**Key components:**

| Component | Technology | Purpose |
|-----------|------------|---------|
| Gateway API | FastAPI (Python 3.11+) | OpenAI-compatible request/response handler |
| PII detector | Microsoft Presidio + spaCy `en_core_web_lg` | Entity recognition (NLP + regex) |
| Nepal recognizers | Custom Presidio `PatternRecognizer` | NP citizenship, mobile, AWS/Stripe keys |
| Anonymization vault | In-memory dict (Redis-ready) with TTL | Reversible placeholder storage per request |
| Audit log | SQLite with SHA-256 hash chain | Tamper-evident event record (no raw PII stored) |
| Operator dashboard | React + Vite + Tailwind CSS + shadcn/ui | Metrics, logs, config, shadow mode toggle |
| Config API | JSON-backed PATCH endpoint | Live recognizer enable/disable, shadow mode |
| Demo chat UI | Plain HTML + JS at `/chat` | Easy evaluation without SDK setup |

---

## 7. Zero-Trust Framing (AI Egress Slice)

This research applies zero-trust principles narrowly to the **AI data egress channel**, not to the full enterprise network. The key posture is:

- **Never trust the external model**: always minimize the payload before it leaves the bank's boundary.
- **Never trust the transport**: correlation IDs and audit hashes enable forensic traceability even if logs are later tampered with externally.
- **Least privilege per request**: each request gets its own vault key; placeholders are scoped to that request's TTL.
- **Continuous verification**: injection heuristics, rate/token budgets, and shadow observability mode provide ongoing signal.

---

## 8. Regulatory Alignment (to be cited formally with supervisor)

The table below uses placeholder citation references — fill these with the exact NRB circular/section numbers and Privacy Act article numbers your supervisor approves.

| Control theme | Regulatory basis (TBD — add real citations) | Technical implementation |
|---------------|----------------------------------------------|--------------------------|
| Data minimization before third-party processing | Individual Privacy Act 2018, [Article TBD]; NRB Cyber Resilience Guidelines [Section TBD] | Pre-flight Presidio scrub; configurable strategies |
| Accountability and audit trail | NRB Guidelines [Section TBD] | Hash-chained SQLite audit; correlation IDs |
| Monitoring and anomaly detection | NRB Guidelines [Section TBD] | `/internal/metrics`, `/internal/alerts`, injection policy |
| Technical security measures | Individual Privacy Act 2018, [Article TBD] | Gateway architecture; admin-gated internal routes; CORS policy |
| Data retention control | Individual Privacy Act 2018, [Article TBD] | Vault TTL (`VAULT_TTL_SECONDS`); audit stores counts/hashes, not raw text |
| Nepal-specific data categories | NRB Guidelines [Section TBD] | Custom recognizers: `NP_CITIZENSHIP_NUMBER`, `NP_MOBILE_NUMBER` |

---

## 9. Methodology

**Phase 1 — Literature review and requirements**
- Review existing DLP, API gateway, and LLM privacy literature
- Analyze NRB Cyber Resilience Guidelines and Individual Privacy Act (2018)
- Document threat model: what PII types matter in a Nepali banking context

**Phase 2 — Design**
- Architecture design: gateway placement, anonymization pipeline, audit schema
- Recognizer selection: which Presidio built-ins + Nepal custom patterns
- Define evaluation metrics: detection rate, latency overhead, false positive rate

**Phase 3 — Implementation**
- Implement gateway, PII pipeline, vault, audit, dashboard (complete — see codebase)
- Iterative testing with synthetic prompts

**Phase 4 — Evaluation**
- Design 10–15 synthetic test scenarios (fictional names, fake account numbers, synthetic credentials)
- Measure: PII detection accuracy, response latency vs direct call, audit chain integrity, operator visibility
- Honest gap analysis: what the prototype does not cover vs a production deployment

**Phase 5 — Writeup**
- Map implemented controls to regulatory themes
- Present results and limitations
- Discuss deployment path for a real bank (governance, legal, operations)

---

## 10. Tools and Technologies

| Layer | Tool/Library | Version |
|-------|-------------|---------|
| Language | Python | 3.11+ |
| Gateway framework | FastAPI | ≥ 0.115 |
| ASGI server | Uvicorn | ≥ 0.32 |
| PII detection | Microsoft Presidio Analyzer | ≥ 2.2.354 |
| NLP model | spaCy `en_core_web_lg` | 3.x |
| HTTP client | httpx | ≥ 0.27 |
| Settings | pydantic-settings | ≥ 2.6 |
| Token estimation | tiktoken | ≥ 0.8 |
| Database | SQLite (built-in) | — |
| Dashboard frontend | React + Vite + Tailwind CSS + shadcn/ui | Node 20+ |
| Containerization | Docker + Docker Compose | — |
| Test framework | pytest + pytest-asyncio | — |

---

## 11. Expected Outcomes

1. A working **open-source prototype** of a privacy-preserving AI gateway designed for Nepali banking context.
2. A **Nepal-oriented PII recognizer set** (citizenship number, mobile number, plus general financial credentials).
3. A **tamper-evident audit mechanism** demonstrating accountability without storing raw sensitive text.
4. A **control-to-regulation mapping** template for NRB and the Individual Privacy Act (2018).
5. An honest **gap analysis** distinguishing what the prototype achieves vs what a production bank would additionally need.

---

## 12. Timeline (indicative)

| Phase | Duration |
|-------|----------|
| Literature review and requirements | 3 weeks |
| Architecture design | 2 weeks |
| Implementation (core gateway) | 4 weeks |
| Implementation (dashboard, audit, Nepal recognizers) | 3 weeks |
| Evaluation and testing | 3 weeks |
| Writing and revision | 4 weeks |
| **Total** | **~19 weeks** |

---

## 13. Ethical Considerations

- This is a **supervised academic project** on defensive cybersecurity and privacy engineering.
- All evaluation uses **synthetic, fictional data only** — no real customer or employee records.
- The prototype is deployed on **controlled local infrastructure** only; no production banking system is involved.
- The project does not include any offensive security components, exploit code, or unauthorized access attempts.
- Work follows the institution's research ethics guidelines.

---

## 14. References (to be completed)

1. Nepal Rastra Bank — Cyber Resilience Guidelines (latest version; add URL/date)
2. Individual Privacy Act, 2018 (Vyaktigat Gupta Sauchana Sambandhi Ain, 2075) — Government of Nepal
3. Microsoft Presidio — https://microsoft.github.io/presidio/
4. spaCy — https://spacy.io
5. FastAPI — https://fastapi.tiangolo.com
6. NIST Zero Trust Architecture, SP 800-207 (2020)
7. OWASP LLM Top 10 — https://owasp.org/www-project-top-10-for-large-language-model-applications/
8. [Add relevant academic papers on DLP, privacy gateways, LLM safety]
9. [Add NRB licensing/guideline documents available from nrb.org.np]
