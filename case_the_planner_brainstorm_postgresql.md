# Brainstorm: PostgreSQL & CSV Integration Strategies (Case Mr. Health)

> [!IMPORTANT]
> **Compliance Note:** All proposals below strictly adhere to the requirements of the [case_MrHealth.md](file:///c:/Users/Flavio%20Graf/Documents/Estudos_Arthur/annotations-and-studies-main/projects/projeto_empresa_data_lakers/case_MrHealth.md) file. The use of PostgreSQL is mandatory for ingesting the following matrix tables:
> - **PRODUCT TABLE:** `Id_Product`, `Name_Product`
> - **UNIT TABLE:** `Id_Unit`, `Name_Unit`, `Id_State`
> - **STATE TABLE:** `Id_State`, `Id_Country`, `Name_State`
> - **COUNTRY TABLE:** `Id_Country`, `Name_Country`
> 
> Unit CSV files (PEDIDO.CSV and ITEM_PEDIDO.CSV) cannot be removed, maintaining the existing operational flow.

This document explores architectural possibilities to integrate the matrix's PostgreSQL database with unit transactional data (CSV), focusing on scalability, low cost, and professionalism, inspired by cases from major tech and retail companies.

---

## Current Scenario vs. Need
*   **Sources:** Daily CSVs (Sales) and PostgreSQL (Product, Unit, State, Country).
*   **Challenge:** Unifying this data without losing CSV flexibility and without manual processes.

---

## Possibility 1: "Modern Data Stack" Architecture (ELT)
*Inspired by: Nubank, Airbnb*

In this model, PostgreSQL and CSVs are treated as raw sources converging into a **Data Warehouse** (like BigQuery or Snowflake).

*   **How it works:**
    1.  **Extraction:** A Python script extracts the 4 master tables from PostgreSQL (`PRODUCT`, `UNIT`, `STATE`, `COUNTRY`) and saves them to Cloud Storage.
    2.  **Landing:** Unit CSVs continue to land in Cloud Storage.
    3.  **Load:** Both datasets are loaded into "Bronze" (Raw) tables.
    4.  **Transform:** SQL unifies orders with master registries within BigQuery.
*   **Advantage:** Fully scalable. You keep CSVs as backup/history.

## Possibility 2: PostgreSQL as "Operational Data Store" (ODS)
*Inspired by: Retail Networks (e.g., Magalu, Carrefour)*

Many companies use PostgreSQL as an intermediate cleaning layer before data goes to the Cloud.

*   **How it works:**
    1.  **Ingestion:** Daily CSVs are inserted into staging tables in PostgreSQL.
    2.  **Processing:** PostgreSQL performs a JOIN between orders and its master tables (`PRODUCT`, `UNIT`, etc.).
    3.  **Export:** "Cleaned and enriched" data is sent to the Cloud.
*   **Advantage:** PostgreSQL ensures only valid data is uploaded to the Cloud.

## Possibility 3: Hybrid Architecture with "External Tables"
*Inspired by: Companies with critical legacy (e.g., Traditional Banks)*

If you wish not to remove CSVs, you can use PostgreSQL to "read" these files as if they were tables.

*   **How it works:**
    1.  **File FDW:** In PostgreSQL, a CSV directory is mapped as external tables.
    2.  **Unification:** Views in Postgres perform the JOIN: `PRODUCT + UNIT + EXTERNAL_ORDER`.
    3.  **Sync:** Consolidated results are sent to the Cloud.
*   **Advantage:** Zero redundancy. Data is not copied into Postgres; it is merely "seen" through it.

## Possibility 4: "Serverless Ingestion" (Minimum Cost)
*Inspired by: Startups and Greenfield Projects*

Pay only for what you use, without keeping servers running 24/7.

*   **How it works:**
    1.  **Trigger:** CSV upload triggers a Cloud Function.
    2.  **Lookup:** The Function performs a quick connection to PostgreSQL to validate `Id_Product` and `Id_Unit`.
    3.  **Destination:** Validated data lands directly in the Silver layer.
*   **Advantage:** Highly scalable and professional.

---

## "The Planner" Recommendation
**Possibility 4 (Serverless Ingestion)** is the most professional and cost-effective. It solves automation without forcing the abandonment of CSVs and ensures that matrix PostgreSQL ingestion happens on demand.
