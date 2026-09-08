"""Command-line entry points using the same analyses as the guided interface."""

import argparse
import json
import sys
from pathlib import Path

from . import core
from .common import InputError, read_table
from .reporting import save_result


def project_info():
    return json.loads(Path(__file__).with_name("project.json").read_text(encoding="utf-8"))


def example_path(name=None):
    info = project_info()
    name = name or info["examples"][0]
    if name not in info["examples"]:
        raise InputError("Choose a bundled example listed by --help.")
    return Path(__file__).with_name("examples") / name


def example_config(name):
    slug = project_info()["slug"]
    if slug == "matcheddoe":
        if name == "banana_design.csv":
            return {
                "factors": ["time_h", "temperature_C"],
                "responses": ["moisture_percent", "colour_deltaE"],
                "model": "additive_quadratic",
                "directions": {"moisture_percent": "minimise", "colour_deltaE": "minimise"},
                "independent_runs": True,
            }
        return {
            "factors": ["dose_g_L", "concentration_ppm", "pH"],
            "responses": ["response"],
            "model": "2fi",
            "independent_runs": True,
        }
    return {}


def example_context(name):
    catalog = json.loads(Path(__file__).with_name("provenance.json").read_text(encoding="utf-8"))
    record = catalog["examples"][name]
    return {
        "input_name": name,
        "column_metadata": record["column_metadata"],
        "provenance": {"kind": "bundled_example", "example": name},
    }


def main(argv=None):
    info = project_info()
    parser = argparse.ArgumentParser(description=info["summary"])
    parser.add_argument("command", choices=["demo", "analyse", "app"])
    parser.add_argument("--input", type=Path, help="CSV or XLSX table")
    parser.add_argument("--config", type=Path, help="JSON object of analysis arguments")
    parser.add_argument("--example", choices=info["examples"], default=info["examples"][0])
    parser.add_argument("--output", type=Path, default=Path("runs") / "latest")
    args = parser.parse_args(argv)
    if args.command == "app":
        from streamlit.web import cli as stcli

        app = Path(__file__).with_name("web_entry.py")
        sys.argv = ["streamlit", "run", str(app), "--server.address=127.0.0.1", "--browser.gatherUsageStats=false"]
        return stcli.main()
    try:
        if args.command == "analyse" and args.input is None:
            raise InputError("Provide --input with a CSV or XLSX file.")
        path = example_path(args.example) if args.command == "demo" else args.input
        config = example_config(args.example) if args.command == "demo" else {}
        if args.config:
            supplied = json.loads(args.config.read_text(encoding="utf-8-sig"))
            if not isinstance(supplied, dict):
                raise InputError("config: the JSON top level must be an object of named analysis settings.")
            config.update(supplied)
        import_options = config.pop("import_options", {})
        if not isinstance(import_options, dict):
            raise InputError("import_options: use a JSON object of parser settings.")
        frame = read_table(path, **import_options)
        context = example_context(args.example) if args.command == "demo" else {"input_name": path.name}
        result = core.analyse(frame, **(context | config))
        result.settings["import_options"] = import_options
        result.settings["export_config"] = result.settings.get("call_parameters", {}) | {
            "import_options": import_options
        }
        directory = save_result(result, args.output)
        print(f"{info['title']}: {result.status}. Open {directory.resolve() / 'report.html'}")
        return 0
    except (InputError, json.JSONDecodeError, OSError) as exc:
        print(f"Input/output problem: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
