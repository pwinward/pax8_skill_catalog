"""Entry points. `serve` runs the catalog; `seed` loads sample skills into it."""

import argparse
from pathlib import Path

from .repository import SqliteRepository
from .server import build_server
from .service import CatalogService

DEFAULT_DB = Path("catalog.db")
SEED_DIR = Path(__file__).resolve().parents[2] / "seed_data"


def load_skill_directory(directory: Path) -> dict[str, str]:
    """Read a skill directory into the path-to-content map the catalog speaks.

    This is the same thing a publishing assistant does on the client side: walk the
    directory, read each file, key it by its path relative to the skill root.
    """
    files: dict[str, str] = {}
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            files[path.relative_to(directory).as_posix()] = path.read_text(encoding="utf-8")
    return files


def seed(service: CatalogService, source: Path) -> int:
    if not source.is_dir():
        print(f"No seed directory at {source}")
        return 1
    for directory in sorted(p for p in source.iterdir() if p.is_dir()):
        result = service.publish(load_skill_directory(directory), publisher="seed")
        if result.published:
            print(f"published {result.name} v{result.version} ({result.file_count} files)")
        else:
            print(f"rejected {directory.name}: {result.message}")
            return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="skills-catalog", description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="catalog database path")
    sub = parser.add_subparsers(dest="command", required=True)

    serve_parser = sub.add_parser("serve", help="run the catalog as an MCP server over HTTP")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)

    seed_parser = sub.add_parser("seed", help="publish the sample skills into the catalog")
    seed_parser.add_argument("--from", dest="source", type=Path, default=SEED_DIR)

    args = parser.parse_args(argv)
    service = CatalogService(SqliteRepository(args.db))

    if args.command == "seed":
        return seed(service, args.source)

    print(f"skills-catalog listening on http://{args.host}:{args.port}/mcp (db: {args.db})")
    build_server(service).run(transport="streamable-http", host=args.host, port=args.port)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
