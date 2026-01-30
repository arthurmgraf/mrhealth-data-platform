# Diagrams Style Guide - v3 Clean & Technical

**Status:** Production Standard
**Tool:** Excalidraw
**Style:** Clean & Technical (Maximum Information Density)

---

## 📋 Overview

This guide defines the **v3 Clean & Technical** style for creating professional architecture diagrams for the MR. HEALTH Data Platform project. This style prioritizes **maximum information density** while maintaining **clean readability**.

---

## 🎨 Visual Characteristics

### Typography
- **Title Font:** Monospace (Courier/Courier New), Size 32px
- **Section Headers:** Monospace, Size 14-20px
- **Body Text:** Monospace, Size 10-11px
- **Metadata:** Monospace, Size 11px, Color: #868e96

### Colors
- **Primary Text:** #1e1e1e (black)
- **Secondary Text:** #495057 (dark gray)
- **Metadata:** #868e96 (gray)
- **Accent Colors:**
  - Data Sources: #fa5252 (red)
  - Ingestion: #FBBC04 (yellow)
  - Warehouse: #4285F4 (blue)
  - BI: #2f9e44 (green)

### Layout
- **Background:** #ffffff (white)
- **Grid:** 20px (invisible but strict alignment)
- **Boxes:** 1px solid borders, subtle fills (#f8f9fa)
- **Roughness:** 0 (perfect geometric shapes)
- **Spacing:** Consistent 15-20px between elements

---

## 📐 Structure Template

```
[HEADER]
  - Title (32px monospace)
  - Metadata line (11px, gray)
  - Divider line (1px solid #dee2e6)

[MAIN CONTENT ZONES]
  - Zone containers (stroke: #ced4da, fill: #f8f9fa)
  - Zone labels ([N] ZONE_NAME, 14px)
  - Component boxes (stroke: accent color, fill: #ffffff)
  - Component details (10-11px monospace)

[CONNECTORS]
  - Arrows (1px solid #495057, simple)
  - Labels (10px, positioned above/beside arrows)

[FOOTER]
  - Technical metrics box
  - Extended specifications
  - Performance data
```

---

## 📊 Information Density Guidelines

### High Priority (Always Include)
- **Service names** with version info
- **Resource specifications** (memory, CPU, timeout)
- **Data volumes** (size, throughput, latency)
- **SLAs and metrics** (P50, P95, P99)
- **Error rates** and retry logic
- **Cost information** (precise values)
- **Partitioning/clustering** strategies
- **Security details** (encryption, IAM)

### Medium Priority (Context Dependent)
- Table schemas and row counts
- Network topology details
- Monitoring and alerting thresholds
- Compliance information

### Low Priority (Optional)
- Future state items (mark as "future")
- Nice-to-have features

---

## 🔧 Component Templates

### Data Source Box
```
DATA_SOURCE_NAME
type: [technology] [version]
location: [physical location]
size: [data volume]
latency: [D+X or real-time]
format: [file format, encoding]
sla: [availability %]
```

### Processing Component Box
```
COMPONENT_NAME
service: [GCP service]
gen: [generation]
runtime: [language + version]
memory: [MB/GB]
cpu: [vCPU count]
timeout: [seconds]
max_instances: [N]
min_instances: [N]
concurrency: [requests/instance]
retry: [strategy]
error_handling: [approach]
operations: [list]
```

### Storage Layer Box
```
LAYER_NAME
layer: [purpose]
tables: [count + list]
ops: [operations]
size: [volume]
partition: [strategy]
cluster: [fields]
retention: [days/policy]
sla: [accuracy/performance]
```

### BI/Reporting Box
```
BI_TOOL_NAME
service: [tool name]
dashboards: [count]
types: [list]
refresh: [strategy]
caching: [policy]
users: [concurrent/limit]
connection: [method]
performance: [load time]
sla: [uptime %]
```

---

## 📏 Sizing Standards

### Containers
- **Zone containers:** Width: 240-650px, Height: 400-700px
- **Component boxes:** Width: 150-300px, Height: 80-180px

### Spacing
- **Between zones:** 40-60px
- **Between components:** 15-20px
- **Margin from container edge:** 15-20px

---

## 🎯 Best Practices

### DO ✅
- Use **precise numeric values** (not "~" unless truly approximate)
- Include **units** (MB, ms, %, requests/s)
- Specify **percentiles** (P50, P95, P99) not just averages
- Add **context** (e.g., "Free Tier", "STRICT mode", "exponential backoff")
- Use **abbreviations consistently** (e.g., "dedup" not "deduplication")
- Include **version numbers** (Python 3.11, Gen2, PostgreSQL 14.x)
- Show **trade-offs** and **constraints**

### DON'T ❌
- Use emojis (keep it professional)
- Use colors for decoration (only for semantic meaning)
- Add unnecessary rounded corners (roughness: 0)
- Include marketing language ("amazing", "best-in-class")
- Omit critical technical details
- Use vague terms ("fast", "scalable" without numbers)

---

## 📂 File Naming Convention

```
[diagram_type]_v3.excalidraw

Examples:
- pilot_v3_clean_technical.excalidraw
- pilot_v3_clean_technical_enhanced.excalidraw
- antes_depois_v3.excalidraw
- modelo_dados_v3.excalidraw
- roadmap_v3.excalidraw
- data_flow_v3.excalidraw
```

---

## 🔄 Update Process

When creating new v3 diagrams:

1. **Copy existing v3 template** (e.g., `pilot_v3_clean_technical_enhanced.excalidraw`)
2. **Maintain exact styling** (fonts, colors, spacing)
3. **Update content** with project-specific details
4. **Verify information density** (every box should be 80%+ filled with useful data)
5. **Export to PNG** (2x resolution for presentations)
6. **Save to** `diagrams/generated/architecture/`

---

## 📸 Export Settings

For presentations and documentation:

1. Open diagram in Excalidraw.com
2. Export as PNG
3. Scale: 2x (high resolution)
4. Background: White
5. Padding: Medium
6. Theme: Light

---

## 🎓 Reference Examples

**Best Examples:**
- `pilot_v3_clean_technical_enhanced.excalidraw` - Architecture overview with security
- `antes_depois_v3.excalidraw` - Process comparison with ROI

**Key Features:**
- Maximum information density (every element earns its space)
- Monospace typography for technical credibility
- Precise specifications (versions, sizes, SLAs)
- Clean geometric layout (no hand-drawn aesthetic)
- Functional use of color (semantic, not decorative)

---

## 🔗 Tools & Resources

- **Excalidraw:** https://excalidraw.com
- **Google Cloud Icons:** Official GCP logos (SVG)
- **Monospace Fonts:** Courier, Courier New, Monaco, Consolas
- **Color Palette:** GCP official colors + grayscale

---

**Created:** 2026-01-30
**Last Updated:** 2026-01-30
**Owner:** Arthur Maia Graf
**Style Version:** v3 Clean & Technical
