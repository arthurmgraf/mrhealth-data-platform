# Acesso Completo ao Sistema MR. HEALTH Data Platform

**Data da Validacao:** 2026-02-05
**Status:** TODOS OS COMPONENTES FUNCIONANDO

---

## Resumo Executivo

| Componente | Status | Acesso |
|------------|--------|--------|
| GCP Project | ATIVO | `your-gcp-project-id` |
| GCS Bucket | ATIVO | 19 arquivos CSV + 4 referencias |
| Cloud Functions | 3 ATIVAS | csv-processor, pg-reference-extractor, data-generator |
| Cloud Scheduler | 1 ATIVO | pg-reference-extraction (01:00 BRT) |
| BigQuery Bronze | 6 tabelas | 178 orders, 496 items |
| BigQuery Silver | 6 tabelas | 15 orders processados |
| BigQuery Gold | 9 tabelas | Star schema completo |
| BigQuery Monitoring | 3 tabelas | Quality logs, metrics, free tier |
| K3s Cluster | RUNNING | 1 node Ready |
| PostgreSQL | RUNNING | 30 produtos, 3 unidades |
| Airflow | RUNNING | 5 DAGs deployed, http://15.235.61.251:30180 |
| Superset | RUNNING | http://15.235.61.251:30188 |
| Grafana | RUNNING | http://15.235.61.251:30300 |
| Portainer | RUNNING | http://15.235.61.251:30777 |

---

## Guia Rápido de Acesso por Etapa

> **Legenda de Localização:**
> - 🖥️ **LOCAL** = Máquina de desenvolvimento (Windows)
> - 🖧 **SERVIDOR** = Servidor on-premise OVH (15.235.61.251) com K3s
> - ☁️ **GCP** = Google Cloud Platform (projeto `your-gcp-project-id`)

---

### 🔹 Etapa 1: Ingestão de Dados (Sources → GCS)

| Fonte | Localização | Como Acessar |
|-------|-------------|--------------|
| **PostgreSQL (dados de referência)** | 🖧 SERVIDOR | `ssh -L 5432:localhost:30432 arthur@15.235.61.251` → `psql -h localhost -U mrhealth_admin -d mrhealth` |
| **Scripts de geração de dados** | 🖥️ LOCAL | `scripts/generate_fake_sales.py`, `scripts/seed_postgresql.py` |
| **CSVs de Vendas (raw data)** | ☁️ GCP | `gcloud storage ls gs://mrhealth-datalake-485810/raw/csv_sales/` |
| **Dados de Referência no GCS** | ☁️ GCP | `gcloud storage ls gs://mrhealth-datalake-485810/raw/reference_data/` |
| **Cloud Function csv-processor** | ☁️ GCP | https://console.cloud.google.com/functions/details/us-central1/csv-processor?project=your-gcp-project-id |
| **Cloud Function pg-reference-extractor** | ☁️ GCP | Extrai dados do PG (SERVIDOR) e envia para GCS |
| **Código das Cloud Functions** | 🖥️ LOCAL | `cloud_functions/csv_processor/`, `cloud_functions/pg_reference_extractor/` |

---

### 🔹 Etapa 2: Camada Bronze (Raw Data no BigQuery)

| Item | Localização | Como Acessar |
|------|-------------|--------------|
| **Dataset mrhealth_bronze** | ☁️ GCP | https://console.cloud.google.com/bigquery?project=your-gcp-project-id |
| **Tabelas** | ☁️ GCP | orders, order_items, products, units, states, countries |
| **Query rápida** | ☁️ GCP | `SELECT COUNT(*) FROM your-gcp-project-id.mrhealth_bronze.orders;` |
| **SQL de criação** | 🖥️ LOCAL | `sql/bronze/create_tables.sql` |

---

### 🔹 Etapa 3: Camada Silver (Dados Limpos)

| Item | Localização | Como Acessar |
|------|-------------|--------------|
| **Dataset mrhealth_silver** | ☁️ GCP | BigQuery Console, mesmo projeto |
| **DAG que popula** | 🖧 SERVIDOR | Airflow DAG `mrhealth_daily_pipeline` (02:00 BRT) |
| **Trigger manual** | 🖧 SERVIDOR | http://15.235.61.251:30180 → DAGs → `mrhealth_daily_pipeline` → Trigger |
| **SQLs de transformação** | 🖥️ LOCAL | `sql/silver/01_transform_orders.sql`, `02_transform_items.sql`, `03_transform_references.sql` |
| **Cópia no servidor** | 🖧 SERVIDOR | `/home/arthur/case_mrHealth/sql/silver/` (montado via hostPath) |

---

### 🔹 Etapa 4: Camada Gold (Star Schema)

| Item | Localização | Como Acessar |
|------|-------------|--------------|
| **Dataset mrhealth_gold** | ☁️ GCP | BigQuery Console |
| **Dimensões** | ☁️ GCP | `dim_date`, `dim_product`, `dim_unit`, `dim_geography` |
| **Fatos** | ☁️ GCP | `fact_sales` (grain: pedido), `fact_order_items` (grain: item) |
| **Agregações** | ☁️ GCP | `agg_daily_sales`, `agg_unit_performance`, `agg_product_performance` |
| **SQLs de criação** | 🖥️ LOCAL | `sql/gold/01_dim_date.sql` até `sql/gold/09_agg_product_performance.sql` |
| **Cópia no servidor** | 🖧 SERVIDOR | `/home/arthur/case_mrHealth/sql/gold/` (montado via hostPath) |

---

### 🔹 Etapa 5: Qualidade e Monitoramento

| Item | Localização | Como Acessar |
|------|-------------|--------------|
| **Dataset monitoring** | ☁️ GCP | `mrhealth_monitoring` no BigQuery |
| **Logs de qualidade** | ☁️ GCP | `SELECT * FROM your-gcp-project-id.mrhealth_monitoring.data_quality_log ORDER BY execution_timestamp DESC LIMIT 10;` |
| **Métricas do pipeline** | ☁️ GCP | Tabela `mrhealth_monitoring.pipeline_metrics` |
| **Uso do Free Tier** | ☁️ GCP | Tabela `mrhealth_monitoring.free_tier_usage` |
| **DAG de quality checks** | 🖧 SERVIDOR | Airflow → `mrhealth_data_quality` (03:00 BRT) |
| **Código dos checks** | 🖥️ LOCAL | `plugins/mrhealth/quality/checks.py` |
| **Dashboard Grafana** | 🖧 SERVIDOR | http://15.235.61.251:30300 |

---

### 🔹 Etapa 6: Visualização e Dashboards

| Ferramenta | Localização | Acesso | Propósito |
|------------|-------------|--------|-----------|
| **Superset** | 🖧 SERVIDOR | http://15.235.61.251:30188 | Dashboards de negócio (vendas, produtos) |
| **Grafana** | 🖧 SERVIDOR | http://15.235.61.251:30300 | Monitoramento técnico (pipeline health) |
| **Portainer** | 🖧 SERVIDOR | http://15.235.61.251:30777 | Gestão visual do K3s cluster |
| **Airflow UI** | 🖧 SERVIDOR | http://15.235.61.251:30180 | Orquestração e logs de DAGs |
| **BigQuery Console** | ☁️ GCP | https://console.cloud.google.com/bigquery | Queries ad-hoc e exploração |

---

### 🔹 Etapa 7: Operações e Manutenção

| Operação | Localização | Comando/Acesso |
|----------|-------------|----------------|
| **SSH para servidor** | 🖧 SERVIDOR | `ssh arthur@15.235.61.251` |
| **Ver pods Kubernetes** | 🖧 SERVIDOR | `kubectl get pods -n mrhealth-db` |
| **Logs do Airflow** | 🖧 SERVIDOR | `kubectl logs -n mrhealth-db deployment/airflow-scheduler --tail=50` |
| **Reprocessar DAG** | 🖧 SERVIDOR | `kubectl exec -n mrhealth-db deployment/airflow-scheduler -- airflow dags trigger <dag_name>` |
| **Verificar Cloud Functions** | ☁️ GCP | `gcloud functions logs read csv-processor --project=your-gcp-project-id --limit=20` |
| **Deploy de manifests K8s** | 🖥️ LOCAL | `k8s/*.yaml` → aplicar com `kubectl apply -f` |
| **Código-fonte do projeto** | 🖥️ LOCAL | `projeto_empresa_data_lakers/` |
| **Cópia operacional (DAGs, plugins, SQL)** | 🖧 SERVIDOR | `/home/arthur/case_mrHealth/` |

> **Credenciais:** Todas as senhas estao em `docs/CREDENCIAIS_SEGURAS.md` (arquivo no .gitignore)

---

## 1. Google Cloud Platform

### Console
**URL:** https://console.cloud.google.com/?project=your-gcp-project-id
**Conta:** arthurmgraf@gmail.com

### Autenticacao
```bash
gcloud auth list
gcloud config set project your-gcp-project-id
```

---

## 2. Cloud Storage (GCS)

### Bucket
**Nome:** `mrhealth-datalake-485810`
**Console:** https://console.cloud.google.com/storage/browser/mrhealth-datalake-485810

### Estrutura
```
gs://mrhealth-datalake-485810/
├── raw/
│   ├── csv_sales/
│   │   ├── 2026/01/27/unit_{001,002,003}/  (6 CSVs)
│   │   ├── 2026/01/28/unit_{001,002,003}/  (6 CSVs)
│   │   └── test/, final/, test2/, test3/
│   └── reference_data/
│       ├── pais.csv, estado.csv, unidade.csv, produto.csv
└── quarantine/
```

### Verificar
```bash
gcloud storage ls gs://mrhealth-datalake-485810/
gcloud storage ls --recursive gs://mrhealth-datalake-485810/raw/csv_sales/
```

---

## 3. Cloud Functions

| Funcao | Trigger | Runtime | URL |
|--------|---------|---------|-----|
| csv-processor | Eventarc (GCS upload) | Python 3.11 | https://csv-processor-f7wgmun2nq-uc.a.run.app |
| pg-reference-extractor | HTTP (Cloud Scheduler) | Python 3.11 | https://pg-reference-extractor-f7wgmun2nq-uc.a.run.app |
| data-generator | HTTP | Python 3.11 | (via gcloud functions list) |

**Console:** https://console.cloud.google.com/functions?project=your-gcp-project-id

```bash
gcloud functions list --project=your-gcp-project-id
gcloud functions logs read csv-processor --project=your-gcp-project-id --region=us-central1 --limit=20
```

---

## 4. Cloud Scheduler

| Job | Horario | Timezone |
|-----|---------|----------|
| pg-reference-extraction | `0 1 * * *` (01:00 BRT) | America/Sao_Paulo |

**Console:** https://console.cloud.google.com/cloudscheduler?project=your-gcp-project-id

---

## 5. BigQuery

**Console:** https://console.cloud.google.com/bigquery?project=your-gcp-project-id

### Datasets

| Dataset | Tabelas | Descricao |
|---------|---------|-----------|
| `mrhealth_bronze` | 6 | Dados brutos ingeridos via csv-processor |
| `mrhealth_silver` | 6 | Dados limpos e dedupados |
| `mrhealth_gold` | 9 | Star schema (Kimball) + agregacoes |
| `mrhealth_monitoring` | 3 | Quality logs, pipeline metrics, free tier usage |

### Tabelas por Layer

**BRONZE (mrhealth_bronze)**

| Tabela | Linhas | Descricao |
|--------|--------|-----------|
| orders | 178 | Pedidos brutos |
| order_items | 496 | Itens dos pedidos |
| products | 30 | Catalogo de produtos (ref) |
| units | 3 | Unidades/restaurantes (ref) |
| states | 3 | Estados (ref) |
| countries | 1 | Paises (ref) |

**SILVER (mrhealth_silver)**

| Tabela | Linhas | Descricao |
|--------|--------|-----------|
| orders | 15 | Pedidos dedupados |
| order_items | 0 | Itens limpos (pendente) |
| products | 30 | Produtos normalizados |
| units | 3 | Unidades normalizadas |
| states | 3 | Estados normalizados |
| countries | 1 | Pais normalizado |

**GOLD (mrhealth_gold) - Star Schema**

| Tabela | Linhas | Tipo |
|--------|--------|------|
| dim_date | 1.095 | Dimensao (3 anos) |
| dim_product | 30 | Dimensao |
| dim_unit | 3 | Dimensao |
| dim_geography | 3 | Dimensao |
| fact_sales | 15 | Fato (grain: pedido) |
| fact_order_items | 0 | Fato (grain: item) |
| agg_daily_sales | 1 | Agregacao |
| agg_unit_performance | 1 | Agregacao |
| agg_product_performance | 0 | Agregacao |

> **Importante sobre o Star Schema:**
> - `fact_sales` NAO tem product_key (grain = pedido). Tem: order_id, date_key, unit_key, order_value
> - `fact_order_items` TEM product_key (grain = item). Tem: item_id, order_id, date_key, unit_key, product_key
> - Colunas Gold usam nomes em ingles: product_name, unit_name (nao nome_produto, nome_unidade)

**MONITORING (mrhealth_monitoring)**

| Tabela | Descricao |
|--------|-----------|
| data_quality_log | Resultados dos 6 checks de qualidade |
| pipeline_metrics | Metricas de execucao do pipeline (duracao, rows) |
| free_tier_usage | Snapshots de uso GCS + BQ vs Free Tier |

### Queries de Validacao
```sql
-- Bronze: total de pedidos
SELECT COUNT(*) FROM `your-gcp-project-id.mrhealth_bronze.orders`;

-- Gold: fact_sales com dimensoes
SELECT
  d.full_date,
  u.unit_name,
  f.order_value
FROM `your-gcp-project-id.mrhealth_gold.fact_sales` f
JOIN `your-gcp-project-id.mrhealth_gold.dim_date` d ON f.date_key = d.date_key
JOIN `your-gcp-project-id.mrhealth_gold.dim_unit` u ON f.unit_key = u.unit_key
LIMIT 10;

-- Quality: ultimos checks
SELECT check_name, result, actual_value, execution_timestamp
FROM `your-gcp-project-id.mrhealth_monitoring.data_quality_log`
ORDER BY execution_timestamp DESC
LIMIT 10;
```

---

## 6. K3s Cluster + PostgreSQL

### Servidor
```
Host: 15.235.61.251
User: arthur
```

> Senha SSH em `docs/CREDENCIAIS_SEGURAS.md`

### Status do Cluster
```bash
ssh arthur@15.235.61.251

# Nodes
kubectl get nodes
# Esperado: k3s-master Ready

# Todos os pods do projeto
kubectl get pods -n mrhealth-db
# Esperado: postgresql, airflow-webserver, airflow-scheduler, airflow-postgres, superset

# Servicos
kubectl get svc -n mrhealth-db
```

### PostgreSQL (Banco de Dados Master)
| Campo | Valor |
|-------|-------|
| Host | 15.235.61.251 |
| Porta | 30432 (NodePort) |
| Database | mrhealth |
| Usuario | mrhealth_admin |

```bash
# Acesso direto no pod
kubectl exec -n mrhealth-db deployment/postgresql -- \
  psql -U mrhealth_admin -d mrhealth -c "SELECT * FROM produto LIMIT 5;"

# Via SSH tunnel (da maquina local)
ssh -L 5432:localhost:30432 arthur@15.235.61.251
# Depois: psql -h localhost -p 5432 -U mrhealth_admin -d mrhealth
```

| Tabela PG | Linhas |
|-----------|--------|
| produto | 30 |
| unidade | 3 |
| estado | 3 |
| pais | 1 |

---

## 7. Airflow (Orquestracao)

**URL:** http://15.235.61.251:30180
**Login:** Ver `docs/CREDENCIAIS_SEGURAS.md`

### Arquitetura de Deploy
- **Executor:** LocalExecutor (sem Celery, zero overhead)
- **Scheduler Memory:** 2Gi limits / 1Gi requests (1Gi causa OOM com paralelismo)
- **Persistencia:** hostPath volumes montando `/home/arthur/case_mrHealth/` diretamente nos pods
- **GCP Credentials:** `/home/arthur/case_mrHealth/keys/gcp.json` (montado como `/opt/airflow/keys/gcp.json`)

### Volumes montados (hostPath)

| Container Path | Host Path | Conteudo |
|----------------|-----------|----------|
| /opt/airflow/dags/ | /home/arthur/case_mrHealth/dags/ | 5 DAG files |
| /opt/airflow/plugins/ | /home/arthur/case_mrHealth/plugins/ | mrhealth package |
| /opt/airflow/config/ | /home/arthur/case_mrHealth/config/ | project_config.yaml |
| /opt/airflow/sql/ | /home/arthur/case_mrHealth/sql/ | 15 SQL scripts |
| /opt/airflow/keys/ | /home/arthur/case_mrHealth/keys/ | gcp.json |

> **Importante:** Alteracoes nos arquivos do servidor sao refletidas imediatamente nos pods (sem rebuild).

### 5 DAGs Deployed

| DAG | Schedule | Descricao |
|-----|----------|-----------|
| `mrhealth_daily_pipeline` | `0 2 * * *` (02:00 BRT) | Pipeline Medallion completo: Bronze->Silver->Gold->Agg |
| `mrhealth_data_quality` | `0 3 * * *` (03:00 BRT) | 6 checks de qualidade + alertas |
| `mrhealth_reference_refresh` | `0 1 * * *` (01:00 BRT) | Sync PG reference data para Bronze |
| `mrhealth_data_retention` | `0 4 * * 0` (dom 04:00) | Limpeza Bronze >90d, GCS >60d, Free Tier monitor |
| `mrhealth_backfill_monitor` | `0 6 * * 1` (seg 06:00) | Detecta gaps e regenera dados faltantes |

### Data Quality Checks (6 verificacoes)

| Check | Categoria | O que verifica |
|-------|-----------|----------------|
| freshness_fact_sales | freshness | Dados de hoje existem em fact_sales |
| completeness_all_units | completeness | Todas as unidades reportaram dados |
| accuracy_cross_layer_totals | accuracy | Totais Silver vs Gold batem |
| uniqueness_order_id | uniqueness | Sem order_id duplicados |
| referential_integrity_product | referential | Todos product_key existem em dim_product |
| volume_anomaly_detection | volume | Volume de hoje dentro de 2 std_dev |

### Operacoes Airflow
```bash
# Verificar DAGs
ssh arthur@15.235.61.251 'kubectl exec -n mrhealth-db deployment/airflow-scheduler -- airflow dags list'

# Trigger manual
ssh arthur@15.235.61.251 'kubectl exec -n mrhealth-db deployment/airflow-scheduler -- airflow dags trigger mrhealth_data_quality'

# Ver logs de um task
ssh arthur@15.235.61.251 'kubectl logs -n mrhealth-db deployment/airflow-scheduler --tail=50'

# Reserializar DAGs (apos editar arquivos)
ssh arthur@15.235.61.251 'kubectl exec -n mrhealth-db deployment/airflow-scheduler -- airflow dags reserialize'
```

### Licoes de Deploy Importantes
1. Imports Airflow: usar `from mrhealth.xxx` (NAO `from plugins.mrhealth.xxx`) pois plugins/ e auto-adicionado ao PYTHONPATH
2. Sensor correto: `GCSObjectsWithPrefixExistenceSensor` (NAO `GCSObjectsWithPrefixSensor`) no providers-google 10.13.1
3. `kubectl cp` e efemero: arquivos copiados se perdem no restart do pod. Usar hostPath volumes.
4. DAGs novos precisam: `airflow dags reserialize` + set `is_active=True` na primeira vez
5. LocalExecutor com 5 DAGs simultaneos precisa >= 2Gi de memoria no scheduler

---

## 8. Grafana (Monitoramento)

**URL:** http://15.235.61.251:30300
**Login:** Ver `docs/CREDENCIAIS_SEGURAS.md`

### Status
- Grafana OSS 11.4.0 no K3s namespace `mrhealth-db`
- Plugin BigQuery (grafana-bigquery-datasource v3.0.4) instalado
- Datasource "BigQuery MR Health" provisionado e testado: `Data source is working`
- Anonymous access habilitado para visualizacao de dashboards (portfolio)

### Dashboards Planejados
- Pipeline Health (metricas do daily_pipeline)
- Data Quality (resultados dos 6 checks)
- Free Tier Usage (GCS + BQ storage vs limites)
- Airflow Metrics (duracao, status)

### Verificar
```bash
ssh arthur@15.235.61.251 'kubectl get pods -n mrhealth-db -l app=grafana'
curl -s http://15.235.61.251:30300/api/health
```

---

## 9. Superset (Dashboards)

**URL:** http://15.235.61.251:30188
**Login:** Ver `docs/CREDENCIAIS_SEGURAS.md`

### Status
- Deploy no K3s namespace `mrhealth-db`
- BigQuery driver instalado (sqlalchemy-bigquery 1.16.0)
- Conexao "BigQuery MR Health" configurada e testada (fact_sales: 15, dim_product: 30)

### Verificar
```bash
ssh arthur@15.235.61.251 'kubectl get pods -n mrhealth-db -l app=superset'
ssh arthur@15.235.61.251 'kubectl logs -n mrhealth-db deployment/superset --tail=20'
```

---

## 10. Portainer (Interface Visual K8s)

**URL:** http://15.235.61.251:30777
**Login:** Ver `docs/CREDENCIAIS_SEGURAS.md`

### O que voce pode ver
- **Namespaces:** mrhealth-db, portainer, kube-system
- **Deployments:** postgresql, airflow-webserver, airflow-scheduler, airflow-postgres, superset, portainer
- **Services:** NodePort 30432 (PG), 30180 (Airflow), 30188 (Superset), 30777 (Portainer)
- **Volumes:** postgresql-pvc, airflow-postgres-pvc

---

## 11. Codigo do Projeto

### Estrutura
```
projeto_empresa_data_lakers/
├── cloud_functions/              # 3 Cloud Functions
│   ├── csv_processor/            # Eventarc: GCS upload -> Bronze
│   ├── data_generator/           # HTTP: gera dados fake
│   └── pg_reference_extractor/   # HTTP: PG -> GCS via SSH
├── dags/                         # 5 Airflow DAGs
│   ├── mrhealth_daily_pipeline.py
│   ├── mrhealth_data_quality.py
│   ├── mrhealth_reference_refresh.py
│   ├── mrhealth_data_retention.py
│   └── mrhealth_backfill_monitor.py
├── plugins/mrhealth/             # Airflow plugins package
│   ├── quality/checks.py        # 6 data quality checks
│   ├── config/loader.py         # Config + project_id loader
│   └── callbacks/alerts.py      # Failure + SLA callbacks
├── scripts/                      # 15 scripts operacionais (rodam LOCAL)
├── sql/                          # 15 SQLs por layer
│   ├── bronze/create_tables.sql
│   ├── silver/01-03_*.sql
│   └── gold/01-09_*.sql
├── config/project_config.yaml    # Config centralizada
├── k8s/                          # Manifests K8s
├── tests/                        # 57+ testes (pytest)
├── diagrams/                     # Excalidraw (EN + PT-BR)
└── docs/                         # Este arquivo + credenciais
```

### Scripts Principais (executam LOCALMENTE)

| Script | Funcao |
|--------|--------|
| `scripts/generate_fake_sales.py` | Gera CSVs de teste (Faker) |
| `scripts/upload_fake_data_to_gcs.py` | Upload CSVs para GCS |
| `scripts/seed_postgresql.py` | Popula PostgreSQL no K3s |
| `scripts/deploy_phase1_infrastructure.py` | Cria datasets + tabelas BQ |
| `scripts/build_silver_layer.py` | Executa SQLs Silver |
| `scripts/build_gold_layer.py` | Executa SQLs Gold |
| `scripts/build_aggregations.py` | Cria tabelas agregadas |

---

## 12. Fluxo de Dados End-to-End

```
PostgreSQL (K3s:30432)        CSV Generator (local/CF)
   │                               │
   │ 01:00 BRT (Scheduler)        │ Upload para GCS
   ▼                               ▼
┌──────────────────────────────────────────┐
│        GCS: mrhealth-datalake-485810     │
│  raw/reference_data/   raw/csv_sales/    │
└──────────────────────────────────────────┘
                 │
                 │ Eventarc trigger (automatico)
                 ▼
         ┌──────────────┐
         │ csv-processor │  Cloud Function
         └──────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│     BigQuery: mrhealth_bronze            │
│  orders, order_items, products, etc      │
└──────────────────────────────────────────┘
                 │
                 │ Airflow DAG daily_pipeline (02:00 BRT)
                 ▼
┌──────────────────────────────────────────┐
│     BigQuery: mrhealth_silver            │
│  Dados limpos, dedupados, normalizados   │
└──────────────────────────────────────────┘
                 │
                 │ Airflow DAG (continuacao)
                 ▼
┌──────────────────────────────────────────┐
│     BigQuery: mrhealth_gold              │
│  Star Schema: dim_*, fact_*, agg_*       │
└──────────────────────────────────────────┘
                 │
                 │ Airflow DAG data_quality (03:00 BRT)
                 ▼
┌──────────────────────────────────────────┐
│  mrhealth_monitoring                │
│  data_quality_log, pipeline_metrics      │
└──────────────────────────────────────────┘
                 │
                 ▼
    ┌────────────┐  ┌─────────┐
    │  Superset   │  │ Grafana │
    │  Dashboards │  │ Metrics │
    └────────────┘  └─────────┘
```

---

## 13. Links Rapidos

| O que | URL/Comando |
|-------|-------------|
| GCP Console | https://console.cloud.google.com/?project=your-gcp-project-id |
| BigQuery | https://console.cloud.google.com/bigquery?project=your-gcp-project-id |
| Cloud Storage | https://console.cloud.google.com/storage/browser/mrhealth-datalake-485810 |
| Cloud Functions | https://console.cloud.google.com/functions?project=your-gcp-project-id |
| Airflow | http://15.235.61.251:30180 |
| Grafana | http://15.235.61.251:30300 |
| Superset | http://15.235.61.251:30188 |
| Portainer | http://15.235.61.251:30777 |
| SSH | `ssh arthur@15.235.61.251` |
| PostgreSQL | `ssh -L 5432:localhost:30432 arthur@15.235.61.251` |

---

## 14. Custo Mensal

| Recurso | Uso | Free Tier Limit | Custo |
|---------|-----|-----------------|-------|
| BigQuery Storage | ~0.001 GB | 10 GB | $0.00 |
| BigQuery Queries | ~0.01 TB/mes | 1 TB | $0.00 |
| GCS Storage | ~0.001 GB | 5 GB | $0.00 |
| Cloud Functions | ~100 invocacoes/dia | 2M/mes | $0.00 |
| K3s Server | OVH (separado) | N/A | Custo proprio |
| **Total GCP** | | | **$0.00/mes** |

---

**Documento atualizado em 2026-02-05**

> **Changelog:**
> - 2026-02-05: Grafana OSS deployed (BigQuery plugin), Superset-BigQuery configurado, 4 DAGs restantes testados
> - 2026-02-05: Airflow 5 DAGs deployed (hostPath volumes), data_quality testado end-to-end 8/8 SUCCESS
> - 2026-02-03: Airflow e Superset migrados para Kubernetes (namespace mrhealth-db)
