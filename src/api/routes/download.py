import csv
import io
from flask import Blueprint, request, jsonify, Response

from ..store import STORE

download_bp = Blueprint("download", __name__, url_prefix="/download")


@download_bp.route("", methods=["GET"])
def download():
    fmt = (request.args.get("format") or "json").lower()
    min_score = request.args.get("min_score")
    since = request.args.get("since")

    items = STORE.list()

    # filter: min_score
    if min_score is not None:
        try:
            ms = float(min_score)
            items = [m for m in items if float(m.get("metrics", {}).get("net_score", 0.0)) >= ms]
        except Exception:
            pass

    # filter: since timestamp
    if since is not None:
        try:
            s = int(since)
            items = [m for m in items if int(m.get("created_at", 0)) >= s]
        except Exception:
            pass

    # JSON response
    if fmt == "json":
        return jsonify({"items": items, "count": len(items)}), 200

    # CSV response
    output = io.StringIO()
    writer = csv.writer(output)

    # find common fields
    # we will flatten metrics.* into separate CSV columns for clarity
    if items:
        base_fields = ["id", "name", "created_at", "updated_at"]
        metric_fields = sorted(items[0].get("metrics", {}).keys())
        header = base_fields + [f"metric.{m}" for m in metric_fields]
        writer.writerow(header)

        for m in items:
            row = [
                m.get("id"),
                m.get("name"),
                m.get("created_at"),
                m.get("updated_at"),
            ]
            for mf in metric_fields:
                row.append(m.get("metrics", {}).get(mf))
            writer.writerow(row)

    csv_bytes = output.getvalue().encode("utf-8")
    return Response(csv_bytes, mimetype="text/csv")
