"""Recreate compact examples from versioned public data. See DATA_SOURCES.json."""

import hashlib
import json
import re
from pathlib import Path

import pandas as pd

DATA = DEST = Path(".")


def temperature():
    frame = pd.read_csv(DATA / "4p63x5r852" / "Temperature_Variation_Dataset.csv")
    features = [c for c in frame if re.fullmatch(r"\d+(?:\.\d+)?", c)]
    averaged = frame.groupby(["subset", "sample"], sort=True)[features + ["Conc"]].mean().reset_index()
    result = pd.DataFrame(
        {
            "sample_id": averaged["subset"] + "_" + averaged["sample"].astype(str),
            "group": averaged["sample"].astype(str),
            "domain": averaged["subset"],
            "target": averaged["Conc"],
        }
    )
    result = pd.concat([result, averaged[features].rename(columns={f: f"NIR__{f}" for f in features})], axis=1)
    result.to_csv(DEST / "temperature_transfer.csv", index=False)
    bands = result[result.domain.eq("X1")].drop(columns="domain").copy()
    bands = bands.rename(columns={f"NIR__{f}": f"{'LOW' if float(f) < 1300 else 'HIGH'}__{f}" for f in features})
    bands.to_csv(DEST / "temperature_bands.csv", index=False)
    (DEST / "temperature_preparation.json").write_text(
        json.dumps(
            {
                "source_doi": "10.17632/4p63x5r852.1",
                "license": "CC-BY-4.0",
                "creators": ["Ahmed Ramadan", "Nicolas Abatzoglou", "Ryan Gosselin"],
                "changes": "3141 spectra averaged within nine formulation IDs and four acquisition domains, producing 36 rows. No fitted preprocessing at preparation stage.",
                "target": "Acetaminophen % w/w",
                "group": "Formulation ID; all conditions of a held-out formulation excluded from fitting and adaptation.",
                "bands_example": "X1 only, fixed split at 1300 nm. Two wavelength bands of one device, not independent instruments; only nine groups.",
                "limitations": "Fixed measurement order, nine formulations, no independent preparation replication. Public benchmark, not reproduction of the paper's scan-level validation.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def main():
    import argparse
    import urllib.request

    global DATA, DEST
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Recreate the bundled examples from checksum-verified public measurements."
    )
    parser.add_argument("--raw-dir", type=Path, default=root / "user_data" / "public_raw")
    parser.add_argument("--output", type=Path, default=root / "runs" / "recreated_examples")
    parser.add_argument("--download", action="store_true", help="Fetch missing CC BY 4.0 source files over HTTPS.")
    args = parser.parse_args()
    DATA, DEST = args.raw_dir.resolve(), args.output.resolve()
    if DEST.exists() and any(DEST.iterdir()):
        parser.error("Choose a new or empty output directory; existing files are preserved.")
    sources = json.loads((root / "DATA_SOURCES.json").read_text(encoding="utf-8"))
    for source in sources:
        if source["license"] != "CC-BY-4.0":
            parser.error("This adapter only accepts the reviewed CC BY 4.0 source manifest.")
        for item in source["downloads"]:
            path = DATA / source["repository_id"] / item["file"]
            if not path.exists():
                if not args.download:
                    parser.error(f"Missing {path}. Supply --download or place the original file there.")
                print(f"Downloading {source['doi']} ({source['license']}): {item['file']}")
                request = urllib.request.Request(
                    item["url"], headers={"User-Agent": "Research-example-reproduction/0.1"}
                )
                with urllib.request.urlopen(request, timeout=60) as response:
                    data = response.read()
                if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
                    parser.error(f"Download checksum mismatch for {item['file']}; no source file was saved.")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            data = path.read_bytes()
            if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
                parser.error(
                    f"Source checksum mismatch for {path}. Check the dataset version; the file was not modified."
                )
    DEST.mkdir(parents=True, exist_ok=True)
    temperature()
    manifest = {
        p.name: {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
        for p in DEST.iterdir()
        if p.is_file() and p.name != "manifest.json"
    }
    (DEST / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        f"Examples recreated in {DEST}. Compare numeric CSV values with examples/; float formatting can vary with library versions."
    )


if __name__ == "__main__":
    main()
