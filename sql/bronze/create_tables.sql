-- MR. HEALTH Data Platform -- Bronze Layer Table DDL
-- Project: {PROJECT_ID}
-- Dataset: mrhealth_bronze

-- Bronze: Orders
CREATE TABLE IF NOT EXISTS `{PROJECT_ID}.mrhealth_bronze.orders` (
  id_unidade INT64 NOT NULL,
  id_pedido STRING NOT NULL,
  tipo_pedido STRING,
  data_pedido DATE,
  vlr_pedido NUMERIC(10,2),
  endereco_entrega STRING,
  taxa_entrega NUMERIC(10,2),
  status STRING,
  _source_file STRING,
  _ingest_timestamp TIMESTAMP,
  _ingest_date DATE
)
PARTITION BY _ingest_date
OPTIONS(
  description="Bronze layer: raw orders from unit CSV files",
  labels=[("layer", "bronze"), ("source", "csv")]
);

-- Bronze: Order Items
CREATE TABLE IF NOT EXISTS `{PROJECT_ID}.mrhealth_bronze.order_items` (
  id_pedido STRING NOT NULL,
  id_item_pedido STRING NOT NULL,
  id_produto INT64,
  qtd INT64,
  vlr_item NUMERIC(10,2),
  observacao STRING,
  _source_file STRING,
  _ingest_timestamp TIMESTAMP,
  _ingest_date DATE
)
PARTITION BY _ingest_date
OPTIONS(
  description="Bronze layer: raw order items from unit CSV files",
  labels=[("layer", "bronze"), ("source", "csv")]
);

-- Bronze: Products (reference)
CREATE TABLE IF NOT EXISTS `{PROJECT_ID}.mrhealth_bronze.products` (
  id_produto INT64 NOT NULL,
  nome_produto STRING,
  _ingest_timestamp TIMESTAMP
)
OPTIONS(
  description="Bronze layer: product reference data",
  labels=[("layer", "bronze"), ("source", "reference")]
);

-- Bronze: Units (reference)
CREATE TABLE IF NOT EXISTS `{PROJECT_ID}.mrhealth_bronze.units` (
  id_unidade INT64 NOT NULL,
  nome_unidade STRING,
  id_estado INT64,
  _ingest_timestamp TIMESTAMP
)
OPTIONS(
  description="Bronze layer: unit reference data",
  labels=[("layer", "bronze"), ("source", "reference")]
);

-- Bronze: States (reference)
CREATE TABLE IF NOT EXISTS `{PROJECT_ID}.mrhealth_bronze.states` (
  id_estado INT64 NOT NULL,
  id_pais INT64,
  nome_estado STRING,
  _ingest_timestamp TIMESTAMP
)
OPTIONS(
  description="Bronze layer: state reference data",
  labels=[("layer", "bronze"), ("source", "reference")]
);

-- Bronze: Countries (reference)
CREATE TABLE IF NOT EXISTS `{PROJECT_ID}.mrhealth_bronze.countries` (
  id_pais INT64 NOT NULL,
  nome_pais STRING,
  _ingest_timestamp TIMESTAMP
)
OPTIONS(
  description="Bronze layer: country reference data",
  labels=[("layer", "bronze"), ("source", "reference")]
);
