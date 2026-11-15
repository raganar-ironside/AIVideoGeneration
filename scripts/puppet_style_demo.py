"""Generate two independent styles of procedural Maratha puppet art."""
import argparse
from pathlib import Path
from historyforgeai.infrastructure.assets.puppet_generator import STYLES, generate_puppet


def main():
    parser = argparse.ArgumentParser(description="Generate Maratha puppet cutout art")
    parser.add_argument("--style", choices=(*STYLES, "both"), default="both")
    parser.add_argument("--output-dir", type=Path, default=Path("workspace/puppet_art"))
    args = parser.parse_args()
    styles = STYLES if args.style == "both" else (args.style,)
    for style in styles:
        output = generate_puppet(style, args.output_dir / style)
        print(f"{style}: {output.resolve()}")


if __name__ == "__main__":
    main()
