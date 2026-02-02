You are a Senior Data Architect and DevOps Engineer. Your task is to perform a comprehensive **Planning** session to audit, optimize, and scale the current data platform.

### 1. Infrastructure Audit & Validation
- **Problem**: We need to ensure the initial GCP setup (GCS, BigQuery, Cloud Functions) is fully functional and error-free.
- **Task**: Review @[log_criação_gcp.log] to identify any failed provisioning steps or IAM permission issues. Cross-reference the logs with the current code in `scripts/` and `cloud_functions/` to ensure the environment matches the implementation.

### 2. Architectural & Code Flow Review
- **Problem**: The current Bronze ⮕ Silver ⮕ Gold pipeline must follow modern data engineering standards for reliability and performance.
- **Task**: Analyze all SQL models and Python transformation logic. Validate the Star Schema implementation in the Gold layer and propose improvements for data quality, normalization, and modularity.

### 3. Continuous Data Strategy (Simulation to Production)
- **Problem**: Current data generation is manual and static. We need to simulate a "live" environment with continuous data flow.
- **Task**: Design a scheduling strategy (e.g., using Cron, Cloud Scheduler, or Airflow) for `generate_fake_sales.py`. The goal is to simulate real-time business activity (employees entering data) throughout the day.

### 4. Business Intelligence & Visualization
- **Problem**: We need actionable insights delivered via Apache Superset.
- **Task**: Plan the BI layer. Define the exact SQL queries needed for the Gold layer datasets. Specify visualization types (KPIs, trend lines, heatmaps) and dashboard structures tailored for business stakeholders.

### 5. Orchestration, Observability & Best Practices
- **Problem**: The platform lacks centralized orchestration and production-grade monitoring.
- **Task**: 
    - Evaluate the integration of **Apache Airflow** as the primary orchestrator.
    - Design an observability framework (Healthchecks, failure alerts, metadata logging) using industry best practices for Software Engineering and DataOps.

### 6. Cloud Agnosticism & AWS Portability
- **Problem**: We must avoid vendor lock-in and prepare for a potential migration to AWS.
- **Task**: Create a detailed portability roadmap. Map existing GCP components to AWS equivalents (S3, Redshift/Athena, Lambda, MWAA) and outline the necessary changes for a seamless structural transition.

---
**Constraint**: This is a **PLANNING ONLY** phase. Do not modify any code or infrastructure. Provide a structured architectural proposal for review before any execution begins.