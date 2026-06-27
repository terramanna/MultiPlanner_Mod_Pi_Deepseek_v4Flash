# Export network overlay GeoJSON from the NSP inventory DB to a static file.
# Usage: python apps/api/scripts/export_network_geojson.py <db_path> <out_path>

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from multiplanner_api.network_overlay import load_network_geojson

if len(sys.argv) != 3:
    print(__doc__)
    sys.exit(1)

db_path, out_path = sys.argv[1], sys.argv[2]
fc = load_network_geojson(db_path)
out = Path(out_path)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(fc, separators=(",", ":")), encoding="utf-8")
print(f"Wrote {len(fc['features'])} features to {out}")
