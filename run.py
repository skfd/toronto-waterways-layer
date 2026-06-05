"""CLI entry point for the Toronto waterways tile layer build."""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import config


def _banner(text):
    print()
    print(f"=== {text} ===")


def cmd_download(args):
    _banner("Download")
    from src.download import download
    status, path = download(force=args.force)
    print(f"{status}: {path}")


def cmd_slim(args):
    _banner("Slim")
    from src.slim import slim
    slim(_latest_geojson())


def cmd_vector(args):
    _banner("Vector tiles")
    from src.vector import build_vector
    build_vector()


def cmd_publish(args):
    _banner("Publish")
    from src.publish import publish
    publish()


def cmd_build(args):
    cmd_download(args)
    cmd_slim(args)
    cmd_vector(args)


def cmd_update(args):
    cmd_build(args)
    cmd_publish(args)


def _latest_geojson():
    """Return the newest downloaded TCL centreline GeoJSON in data/."""
    if not os.path.isdir(config.DATA_DIR):
        raise RuntimeError("No data/ directory. Run 'download' first.")
    files = sorted(
        f for f in os.listdir(config.DATA_DIR)
        if f.startswith("centreline-") and f.endswith(".geojson")
    )
    if not files:
        raise RuntimeError("No centreline GeoJSON in data/. Run 'download' first.")
    return os.path.join(config.DATA_DIR, files[-1])


COMMANDS = {
    "download": (cmd_download, "Download the latest TCL centreline GeoJSON"),
    "slim": (cmd_slim, "Filter to watercourses + convert into slim GeoJSONL"),
    "vector": (cmd_vector, "Build vector (MVT) tiles via WSL tippecanoe"),
    "publish": (cmd_publish, "Force-push the site to the gh-pages branch"),
    "build": (cmd_build, "download + slim + vector"),
    "update": (cmd_update, "build + publish (daily scheduled-task entry point)"),
}


def main():
    parser = argparse.ArgumentParser(
        description="Toronto Waterways Tile Layer builder"
    )
    sub = parser.add_subparsers(dest="command")
    for name, (_, help_text) in COMMANDS.items():
        p = sub.add_parser(name, help=help_text)
        if name in ("download", "build", "update"):
            p.add_argument(
                "--force", action="store_true",
                help="Re-download even if the remote file is unchanged",
            )

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return
    if not hasattr(args, "force"):
        args.force = False

    COMMANDS[args.command][0](args)


if __name__ == "__main__":
    main()
