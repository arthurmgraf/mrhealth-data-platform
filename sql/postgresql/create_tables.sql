-- MR. HEALTH - PostgreSQL Schema Definition
-- Tabelas de referência da matriz (K3s)
--
-- Ordem de criação respeita foreign keys:
-- 1. pais (nenhuma dependência)
-- 2. estado (depende de pais)
-- 3. unidade (depende de estado)
-- 4. produto (nenhuma dependência)

BEGIN;

CREATE TABLE IF NOT EXISTS pais (
    id_pais   INTEGER PRIMARY KEY,
    nome_pais VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS estado (
    id_estado   INTEGER PRIMARY KEY,
    id_pais     INTEGER NOT NULL REFERENCES pais(id_pais),
    nome_estado VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS unidade (
    id_unidade   INTEGER PRIMARY KEY,
    nome_unidade VARCHAR(200) NOT NULL,
    id_estado    INTEGER NOT NULL REFERENCES estado(id_estado)
);

CREATE TABLE IF NOT EXISTS produto (
    id_produto   INTEGER PRIMARY KEY,
    nome_produto VARCHAR(200) NOT NULL
);

COMMIT;
