# Template: /generate-diagrams

Template completo para reutilizar o comando `/generate-diagrams` do Claude Code em qualquer projeto.
Gera diagramas profissionais em formato Excalidraw seguindo o padrão **v3 Clean & Technical**.

## Setup Rapido

Para adicionar esta funcionalidade a outro projeto, copie os seguintes diretórios para a raiz do projeto destino:

```bash
# Na raiz do projeto destino, copie:
cp -r .claude/commands/generate-diagrams.md   <PROJETO>/.claude/commands/
cp -r .claude/agents/diagram-generator-agent.md <PROJETO>/.claude/agents/
cp -r .claude/kb/diagram-generation/           <PROJETO>/.claude/kb/
cp -r docs/DIAGRAMS_STYLE_GUIDE.md             <PROJETO>/docs/
mkdir -p <PROJETO>/diagrams/generated/{architecture,data-flow,data-model}
```

Ou simplesmente copie toda a estrutura:

```bash
# Copiar tudo de uma vez
cp -r template/generate-diagrams/.claude/* <PROJETO>/.claude/
cp -r template/generate-diagrams/docs/*    <PROJETO>/docs/
mkdir -p <PROJETO>/diagrams/generated/{architecture,data-flow,data-model}
```

## Estrutura de Arquivos

```
.claude/
├── commands/
│   └── generate-diagrams.md          # Definicao do comando (slash command)
├── agents/
│   └── diagram-generator-agent.md    # Agente gerador (logica principal)
└── kb/
    └── diagram-generation/
        ├── excalidraw-format.md      # Spec do formato JSON Excalidraw
        ├── v3-logo-flow-style.md     # Spec da variante logo-flow
        ├── style-guide.md            # Guia de estilo (referencia legacy)
        ├── layout-patterns.md        # Templates de layout espacial
        ├── icon-library.md           # Biblioteca de icones/emojis
        ├── creative-style-guide.md   # Estilo criativo (deprecated)
        ├── examples/
        │   └── alt2_handcrafted.md   # Analise de diagrama referencia
        └── logos/
            ├── README.md             # Guia do sistema de logos
            ├── gcp.md               # Logos GCP (BigQuery, GCS, etc.)
            ├── general.md           # Logos gerais (PostgreSQL, Python, etc.)
            └── custom.md            # Logos custom (cresce sob demanda)

docs/
└── DIAGRAMS_STYLE_GUIDE.md          # Guia de estilo v3 (producao)

diagrams/
└── generated/                        # Output dos diagramas gerados
    ├── architecture/
    ├── data-flow/
    └── data-model/
```

## Uso

Depois de copiar os arquivos para o projeto destino:

```bash
# Gerar todos os diagramas do projeto
/generate-diagrams complete

# Gerar apenas arquitetura
/generate-diagrams architecture

# Gerar apenas data-flow (medallion, pipelines)
/generate-diagrams data-flow

# Gerar modelo de dados (star schema)
/generate-diagrams data-model
```

## Tipos de Diagrama

| Tipo | Descricao |
|------|-----------|
| `architecture` | Infraestrutura e componentes do sistema |
| `data-flow` | Pipelines e fluxo de dados (Medallion, ETL) |
| `data-model` | Star schema, entidade-relacionamento |
| `agents` | Arquitetura multi-agente |
| `pipeline` | Pipeline de processamento |
| `complete` | Todos os tipos acima |

## Caracteristicas

- **Dual Generation**: Gera variante `_technical` (detalhada) e `_logo_flow` (logos only)
- **15+ Logos Embutidos**: GCP, PostgreSQL, Python, Kafka, Redis, MongoDB, etc.
- **LinkedIn-Optimized**: Canvas 1080x1350 (portrait) e 1200x627 (landscape)
- **v3 Clean & Technical**: Fontes monospace, cores semanticas, padding obrigatorio
- **Project-Aware**: Detecta patterns (Medallion, Event-Driven, Microservices)

## Exemplos de Output

Os diagramas de exemplo estao em `diagrams/generated/` neste template:
- `architecture/infrastructure_v3_technical.excalidraw`
- `architecture/infrastructure_v3_logo_flow.excalidraw`
- `data-flow/medallion_pipeline_v3_technical.excalidraw`
- `data-flow/medallion_pipeline_v3_logo_flow.excalidraw`
- `data-model/star_schema_v3_technical.excalidraw`

Abra qualquer um em [excalidraw.com](https://excalidraw.com) para visualizar.
