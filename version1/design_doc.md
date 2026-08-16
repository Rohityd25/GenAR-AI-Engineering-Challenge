# Version 1 Architecture & Design Document
**Next-Generation Generalizable Pharmacovigilance Safety Reporting System**

---

## 1. Executive Summary & Vision
Version 0 successfully established the bedrock principle of automated regulatory reporting: **The report can only say what the data supports.** By decoupling deterministic data computation from scoped LLM prose generation and enforcing strict section packet isolation, Version 0 eliminated numeric hallucinations and ensured 100% factual traceability.

**Version 1** scales this foundation into an enterprise-grade pharmacovigilance intelligence platform capable of producing diverse periodic and aggregate safety documents (PADER, PSUR / PBRER, DSUR, CSR, and Annual Safety Reports) across hundreds of medicinal products simultaneously, complete with sentence-level cryptographic evidence tracing, longitudinal signal tracking, and multi-tiered automated compliance verification.

---

## 2. Core Version 1 Architectural Enhancements

```mermaid
flowchart TD
    subgraph Data & Knowledge Ingestion
        A[Multi-Source Safety Data: E2B R3 / FAERS / Argus] --> V[Versioned Data Lakehouse]
        B[External MedDRA Hierarchy 27.1 / WHODrug] --> V
        C[CCDS / SmPC / US Prescribing Information] --> V
    end

    subgraph Deterministic PV Compute Engine
        V --> D[Batch & Streaming Analysis Workers]
        D --> E[Validated Signal Algorithms: PRR / ROR / EBGM]
        D --> F[Deterministic Fact & Metric Store]
    end

    subgraph Declarative Report Orchestration
        G[Report Schema Definitions: PADER, PSUR, DSUR, CSR] --> H[Context Packet Assembler v2]
        F --> H
        H --> I[Scoped Evidence & Lineage Packets]
    end

    subgraph Controlled LLM Synthesis & Attribution
        I --> J[Section Generation Engine]
        J --> K[Sentence-Level Evidence Attribution Engine]
        K --> L[Structured Regulatory Draft]
    end

    subgraph Governance, Review & Publishing
        L --> M[Interactive Dual-Pane PV Review Console]
        M --> N[Audit-Logged Electronic Sign-off: 21 CFR Part 11]
        N --> O[Multi-Format Publishing: eCTD XML / PDF / DOCX]
    end

    subgraph Continuous Scaled Evaluation
        L --> P[1,000-Report Automated Compliance Evaluator]
        P --> Q[Numeric Grounding + Regulatory Fact Verifier]
    end
```

---

## 3. Key Technical Pillars of Version 1

### A. Sentence-Level Evidence Attribution (`EvidenceTracer`)
- Every generated sentence in every section is automatically tagged with the explicit JSON path of the underlying pre-computed metric (e.g., `[#ref:evidence_packet.serious_vs_nonserious.serious_cases]`).
- Reviewers in the medical review console can click any phrase or number to highlight the exact cell and SQL/Python computation in the raw dataset.

### B. MedDRA Hierarchy Integration & Labeledness Engine
- Ingests official MedDRA hierarchy mappings (PT $\rightarrow$ HLT $\rightarrow$ HLGT $\rightarrow$ SOC) to enable standard System Organ Class tabulations without model guesswork.
- Ingests Company Core Data Sheets (CCDS) and regional labels to deterministically compute **Expectedness / Labeledness** (Serious Unexpected Adverse Reactions / SUSARs).

### C. Multi-Report & Multi-Standard Generalization ("The Real Test")
- Extending from PADER to PSUR/PBRER, DSUR, or Clinical Study Reports (CSR) requires **only declarative YAML configuration updates** and optional registration of specialized statistical functions (e.g., disproportionality metrics like PRR/ROR).
- The pipeline core, validation logic, packet assembler, review workflows, and evaluation suites remain 100% untouched.

### D. Scaled Evaluation Architecture (1,000 Reports at Scale)
To validate 1,000 reports in production:
1. **Automated Numeric Grounding Audit:** 100% automated regex and token verification against pre-computed packet facts. Zero tolerance for ungrounded numbers ($Precision = 1.0$).
2. **Cross-Run Stability & Temperature Variance:** Multi-run stochastic diffing to ensure critical regulatory assertions do not drift.
3. **Rule-Based Regulatory Guardrails:** Automated linters that block non-compliant phrases (e.g., "no safety issues were found", "drug is safe and effective").
4. **Sampled Expert Human Review:** Stratified statistical sampling for clinical review based on case complexity and signal risk.

---

## 4. Migration & Backward Compatibility
Version 1 is fully backward-compatible with Version 0 configuration schemas, allowing legacy PADER pipelines to execute with zero migration downtime while gaining instant access to enhanced audit logging and export capabilities.
