#!/usr/bin/env python3
"""
Setup Superset Dashboards via REST API.

Creates 4 dashboards, 25 datasets (virtual SQL), and 25 charts
from a YAML definitions file. Idempotent: re-running deletes
existing assets and recreates them.

Usage:
    python scripts/setup_superset_dashboards.py
    python scripts/setup_superset_dashboards.py --dry-run
    python scripts/setup_superset_dashboards.py --password MyPass123

Requirements:
    pip install requests pyyaml

Author: Arthur Graf
Date: February 2026
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import quote

import requests
import yaml

DEFINITIONS_PATH = Path(__file__).parent.parent / "superset" / "dashboards" / "definitions.yaml"


def load_definitions(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_session(base_url: str, username: str, password: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    login_resp = session.post(
        f"{base_url}/api/v1/security/login",
        json={"username": username, "password": password, "provider": "db"},
        timeout=30,
    )
    if login_resp.status_code != 200:
        print(f"  [ERROR] Login failed ({login_resp.status_code}): {login_resp.text[:200]}")
        sys.exit(1)

    access_token = login_resp.json()["access_token"]
    session.headers.update({"Authorization": f"Bearer {access_token}"})

    csrf_resp = session.get(f"{base_url}/api/v1/security/csrf_token/", timeout=10)
    if csrf_resp.status_code == 200:
        csrf_token = csrf_resp.json()["result"]
        session.headers.update({"X-CSRFToken": csrf_token})

    session.headers.update({"Referer": base_url})
    return session


def find_database_id(session: requests.Session, base_url: str, db_name: str) -> int | None:
    resp = session.get(f"{base_url}/api/v1/database/", timeout=10)
    resp.raise_for_status()
    for db in resp.json().get("result", []):
        if db.get("database_name") == db_name:
            return db["id"]
    return None


def find_resource_by_name(
    session: requests.Session, base_url: str, resource: str, name_field: str, name: str
) -> int | None:
    page_size = 100
    page = 0
    while True:
        url = f"{base_url}/api/v1/{resource}/?q=(page_size:{page_size},page:{page})"
        resp = session.get(url, timeout=30)
        if resp.status_code != 200:
            return None
        results = resp.json().get("result", [])
        if not results:
            return None
        for item in results:
            if item.get(name_field) == name:
                return item["id"]
        if len(results) < page_size:
            return None
        page += 1


def delete_resource(session: requests.Session, base_url: str, resource: str, rid: int) -> bool:
    resp = session.delete(f"{base_url}/api/v1/{resource}/{rid}", timeout=10)
    return resp.status_code in (200, 204)


def create_dataset(
    session: requests.Session, base_url: str, name: str, sql: str, database_id: int
) -> int | None:
    existing_id = find_resource_by_name(session, base_url, "dataset", "table_name", name)
    if existing_id:
        delete_resource(session, base_url, "dataset", existing_id)
        print(f"    [DEL] Deleted existing dataset: {name}")

    payload = {
        "database": database_id,
        "schema": "mrhealth_gold",
        "table_name": name,
        "sql": sql.strip(),
        "owners": [1],
    }
    resp = session.post(f"{base_url}/api/v1/dataset/", json=payload, timeout=30)
    if resp.status_code in (200, 201):
        dataset_id = resp.json()["id"]
        print(f"    [OK] Dataset created: {name} (id={dataset_id})")
        return dataset_id
    else:
        print(f"    [ERROR] Dataset failed: {name} -> {resp.status_code}: {resp.text[:200]}")
        return None


def build_chart_params(viz_type: str, params: dict, columns: list[str] | None = None) -> str:
    base = {
        "color_scheme": params.get("color_scheme", "supersetColors"),
        "extra_form_data": {},
    }

    if viz_type == "big_number_total":
        metric_name = params.get("metric", "value")
        base.update({
            "metric": {
                "expressionType": "SIMPLE",
                "column": {"column_name": metric_name, "type": "FLOAT"},
                "aggregate": "MAX",
                "label": metric_name,
            },
            "subheader": params.get("subheader", ""),
            "y_axis_format": params.get("y_axis_format", "SMART_NUMBER"),
            "header_font_size": 0.4,
            "subheader_font_size": 0.15,
        })

    elif viz_type == "echarts_timeseries_line":
        metrics = []
        for m in params.get("metrics", []):
            metrics.append({
                "expressionType": "SIMPLE",
                "column": {"column_name": m, "type": "FLOAT"},
                "aggregate": "MAX",
                "label": m,
            })
        base.update({
            "x_axis": params.get("x_axis", "order_date"),
            "time_grain_sqla": "P1D",
            "metrics": metrics,
            "groupby": [],
            "rich_tooltip": params.get("rich_tooltip", True),
            "show_legend": params.get("show_legend", True),
            "truncate_metric": True,
            "row_limit": 10000,
        })

    elif viz_type == "pie":
        metric_name = params.get("metric", "value")
        base.update({
            "metric": {
                "expressionType": "SIMPLE",
                "column": {"column_name": metric_name, "type": "FLOAT"},
                "aggregate": "MAX",
                "label": metric_name,
            },
            "groupby": params.get("groupby", []),
            "show_labels": params.get("show_labels", True),
            "label_type": params.get("label_type", "key_value_percent"),
            "innerRadius": params.get("innerRadius", 0),
            "row_limit": 100,
        })

    elif viz_type == "dist_bar":
        metrics = []
        for m in params.get("metrics", []):
            metrics.append({
                "expressionType": "SIMPLE",
                "column": {"column_name": m, "type": "FLOAT"},
                "aggregate": "MAX",
                "label": m,
            })
        base.update({
            "metrics": metrics,
            "groupby": params.get("groupby", []),
            "show_bar_value": params.get("show_bar_value", True),
            "row_limit": 50,
            "order_desc": True,
        })

    elif viz_type == "table":
        base.update({
            "all_columns": params.get("all_columns", []),
            "order_by_cols": params.get("order_by_cols", []),
            "page_length": params.get("page_length", 50),
            "include_search": True,
            "row_limit": 1000,
        })

    elif viz_type == "histogram":
        base.update({
            "all_columns_x": [params.get("column", "value")],
            "link_length": params.get("bins", 10),
            "cumulative": params.get("cumulative", False),
            "normalized": params.get("normalized", False),
            "row_limit": 10000,
        })

    elif viz_type in ("bubble_v2", "bubble"):
        base.update({
            "x": {
                "expressionType": "SIMPLE",
                "column": {"column_name": params.get("x", "x"), "type": "FLOAT"},
                "aggregate": "MAX",
                "label": params.get("x", "x"),
            },
            "y": {
                "expressionType": "SIMPLE",
                "column": {"column_name": params.get("y", "y"), "type": "FLOAT"},
                "aggregate": "MAX",
                "label": params.get("y", "y"),
            },
            "size": {
                "expressionType": "SIMPLE",
                "column": {"column_name": params.get("size", "size"), "type": "FLOAT"},
                "aggregate": "MAX",
                "label": params.get("size", "size"),
            },
            "entity": params.get("entity", "entity"),
            "row_limit": 100,
        })

    else:
        base.update(params)

    return json.dumps(base)


def create_chart(
    session: requests.Session,
    base_url: str,
    name: str,
    viz_type: str,
    datasource_id: int,
    params: dict,
) -> int | None:
    existing_id = find_resource_by_name(session, base_url, "chart", "slice_name", name)
    if existing_id:
        delete_resource(session, base_url, "chart", existing_id)
        print(f"    [DEL] Deleted existing chart: {name}")

    params_json = build_chart_params(viz_type, params)

    payload = {
        "slice_name": name,
        "viz_type": viz_type,
        "datasource_id": datasource_id,
        "datasource_type": "table",
        "params": params_json,
        "owners": [1],
    }
    resp = session.post(f"{base_url}/api/v1/chart/", json=payload, timeout=30)
    if resp.status_code in (200, 201):
        chart_id = resp.json()["id"]
        print(f"    [OK] Chart created: {name} (id={chart_id})")
        return chart_id
    else:
        print(f"    [ERROR] Chart failed: {name} -> {resp.status_code}: {resp.text[:200]}")
        return None


def build_position_json(chart_ids: list[int]) -> str:
    position = {"DASHBOARD_VERSION_KEY": "v2"}
    row_children = []

    for i, chart_id in enumerate(chart_ids):
        row = i // 3
        col = i % 3
        chart_key = f"CHART-{chart_id}"
        position[chart_key] = {
            "type": "CHART",
            "id": chart_key,
            "children": [],
            "meta": {
                "chartId": chart_id,
                "width": 4,
                "height": 50,
            },
        }
        row_key = f"ROW-{row}"
        if row_key not in position:
            position[row_key] = {
                "type": "ROW",
                "id": row_key,
                "children": [],
                "meta": {"background": "BACKGROUND_TRANSPARENT"},
            }
            row_children.append(row_key)
        position[row_key]["children"].append(chart_key)

    position["ROOT_ID"] = {
        "type": "ROOT",
        "id": "ROOT_ID",
        "children": ["GRID_ID"],
    }
    position["GRID_ID"] = {
        "type": "GRID",
        "id": "GRID_ID",
        "children": row_children,
    }
    position["HEADER_ID"] = {
        "type": "HEADER",
        "id": "HEADER_ID",
        "meta": {"text": "Dashboard"},
    }

    return json.dumps(position)


def create_dashboard(
    session: requests.Session,
    base_url: str,
    title: str,
    slug: str,
    chart_ids: list[int],
) -> int | None:
    existing_id = find_resource_by_name(session, base_url, "dashboard", "slug", slug)
    if existing_id:
        delete_resource(session, base_url, "dashboard", existing_id)
        print(f"    [DEL] Deleted existing dashboard: {slug}")

    position_json = build_position_json(chart_ids)

    payload = {
        "dashboard_title": title,
        "slug": slug,
        "owners": [1],
        "position_json": position_json,
        "json_metadata": json.dumps({
            "color_scheme": "supersetColors",
            "refresh_frequency": 0,
            "expanded_slices": {},
            "label_colors": {},
            "shared_label_colors": {},
            "timed_refresh_immune_slices": [],
        }),
        "published": True,
    }
    resp = session.post(f"{base_url}/api/v1/dashboard/", json=payload, timeout=30)
    if resp.status_code in (200, 201):
        dash_id = resp.json()["id"]
        print(f"    [OK] Dashboard created: {title} (id={dash_id})")
        return dash_id
    else:
        print(f"    [ERROR] Dashboard failed: {title} -> {resp.status_code}: {resp.text[:200]}")
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Setup Superset dashboards via API")
    parser.add_argument("--dry-run", action="store_true", help="Parse config and validate only")
    parser.add_argument("--password", type=str, help="Superset admin password")
    parser.add_argument("--definitions", type=str, default=str(DEFINITIONS_PATH), help="Path to definitions YAML")
    args = parser.parse_args()

    print("=" * 60)
    print("MR. HEALTH - Superset Dashboard Setup")
    print("=" * 60)

    config_path = Path(args.definitions)
    if not config_path.exists():
        print(f"  [ERROR] Definitions file not found: {config_path}")
        return 1

    config = load_definitions(config_path)
    superset_cfg = config["superset"]
    base_url = superset_cfg["base_url"]
    username = superset_cfg["username"]

    password = args.password or os.environ.get(
        superset_cfg.get("password_env", "SUPERSET_PASSWORD"), ""
    )
    if not password:
        print(f"  [ERROR] Password not provided. Use --password or set ${superset_cfg.get('password_env', 'SUPERSET_PASSWORD')}")
        return 1

    dashboards = superset_cfg.get("dashboards", [])
    total_datasets = sum(len(d.get("datasets", [])) for d in dashboards)

    print(f"  Base URL:   {base_url}")
    print(f"  User:       {username}")
    print(f"  Dashboards: {len(dashboards)}")
    print(f"  Datasets:   {total_datasets}")
    print(f"  Charts:     {total_datasets}")

    if args.dry_run:
        print("\n  [DRY RUN] Config parsed successfully. No API calls made.")
        for dash in dashboards:
            print(f"\n  Dashboard: {dash['title']} ({dash['name']})")
            for ds in dash.get("datasets", []):
                print(f"    - {ds['name']} -> {ds['chart_name']} [{ds['viz_type']}]")
        return 0

    print(f"\n--- Authenticating with Superset ---")
    session = get_session(base_url, username, password)
    print("  [OK] Authenticated")

    print(f"\n--- Finding BigQuery database ---")
    db_name = superset_cfg.get("database_name", "BigQuery MR Health")
    database_id = find_database_id(session, base_url, db_name)
    if not database_id:
        print(f"  [ERROR] Database '{db_name}' not found in Superset. Create it first.")
        return 1
    print(f"  [OK] Database found: {db_name} (id={database_id})")

    stats = {"datasets_ok": 0, "datasets_fail": 0, "charts_ok": 0, "charts_fail": 0, "dashboards_ok": 0, "dashboards_fail": 0}

    for dash_def in dashboards:
        dash_name = dash_def["name"]
        dash_title = dash_def["title"]
        dash_slug = dash_def["slug"]
        datasets_def = dash_def.get("datasets", [])

        print(f"\n{'=' * 60}")
        print(f"Dashboard: {dash_title} ({dash_name})")
        print(f"{'=' * 60}")

        chart_ids = []

        for ds_def in datasets_def:
            ds_name = ds_def["name"]
            chart_name = ds_def["chart_name"]
            viz_type = ds_def["viz_type"]
            sql = ds_def["sql"]
            params = ds_def.get("params", {})

            print(f"\n  [{viz_type}] {ds_name}")

            dataset_id = create_dataset(session, base_url, ds_name, sql, database_id)
            if not dataset_id:
                stats["datasets_fail"] += 1
                stats["charts_fail"] += 1
                continue
            stats["datasets_ok"] += 1

            chart_id = create_chart(session, base_url, chart_name, viz_type, dataset_id, params)
            if chart_id:
                chart_ids.append(chart_id)
                stats["charts_ok"] += 1
            else:
                stats["charts_fail"] += 1

        if chart_ids:
            print(f"\n  --- Creating dashboard: {dash_title} ---")
            dash_id = create_dashboard(session, base_url, dash_title, dash_slug, chart_ids)
            if dash_id:
                stats["dashboards_ok"] += 1
            else:
                stats["dashboards_fail"] += 1
        else:
            print(f"\n  [WARN] No charts created for {dash_title}, skipping dashboard")
            stats["dashboards_fail"] += 1

    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Datasets:   {stats['datasets_ok']} OK / {stats['datasets_fail']} FAIL")
    print(f"  Charts:     {stats['charts_ok']} OK / {stats['charts_fail']} FAIL")
    print(f"  Dashboards: {stats['dashboards_ok']} OK / {stats['dashboards_fail']} FAIL")

    total_fail = stats["datasets_fail"] + stats["charts_fail"] + stats["dashboards_fail"]
    if total_fail == 0:
        print(f"\n  [SUCCESS] All assets created! Access at {base_url}")
        return 0
    else:
        print(f"\n  [PARTIAL] {total_fail} failures. Check errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
