"""Entry points. `serve` runs the catalog; `seed` loads sample skills."""

import argparse
from pathlib import Path

from .repository import SqliteRepository
from .server import build_server
from .service import CatalogService

DEFAULT_DB = Path("catalog.db")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="skills-catalog", description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="catalog database path")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="run the catalog as an MCP server over HTTP")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)
    service = CatalogService(SqliteRepository(args.db))

    if args.command == "serve":
        print(f"skills-catalog listening on http://{args.host}:{args.port}/mcp (db: {args.db})")
        build_server(service).run(transport="streamable-http", host=args.host, port=args.port)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
