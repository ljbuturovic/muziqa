#!/usr/bin/env python3
"""Analyze artists and years from artists.txt or directly from MP3/FLAC/WAV/M4A/OGG tags.

Usage:
  muziqa /path/to/music/dir
  muziqa /path/to/music/dir --flat
  muziqa /path/to/music/dir --artists artists.txt
"""

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker


def parse_artists_txt(filepath: str) -> tuple[Counter, Counter]:
    artist_pattern = re.compile(r"Artist:\s*(.+?)\s*,\s*Year:")
    year_pattern = re.compile(r"Year:\s*(\d{4})")
    artists: Counter = Counter()
    years: Counter = Counter()
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            m = artist_pattern.search(line)
            if m:
                name = m.group(1).strip()
                if name:
                    artists[name] += 1
            m = year_pattern.search(line)
            if m:
                years[m.group(1)] += 1
    return artists, years


def _collect_files(folder: Path, recursive: bool) -> list[Path]:
    glob = folder.rglob if recursive else folder.glob
    return [p for ext in ("*.mp3", "*.flac", "*.wav", "*.m4a", "*.ogg") for p in glob(ext)]


def _read_tags(path: Path) -> tuple[str, str]:
    """Return (artist, year) strings from a music file, empty string if not found."""
    from mutagen.id3 import ID3, ID3NoHeaderError
    from mutagen.flac import FLAC
    from mutagen.wave import WAVE
    from mutagen.mp4 import MP4
    from mutagen.oggvorbis import OggVorbis

    suffix = path.suffix.lower()
    try:
        if suffix == ".mp3":
            tags = ID3(path)
            artist = str(tags["TPE1"]).strip() if "TPE1" in tags else ""
            year = str(tags["TDRC"]).strip()[:4] if "TDRC" in tags else ""
        elif suffix == ".flac":
            tags = FLAC(path)
            artist = (tags.get("artist") or [""])[0].strip()
            year = (tags.get("date") or [""])[0].strip()[:4]
        elif suffix == ".wav":
            tags = WAVE(path)
            id3 = tags.tags
            artist = str(id3["TPE1"]).strip() if id3 and "TPE1" in id3 else ""
            year = str(id3["TDRC"]).strip()[:4] if id3 and "TDRC" in id3 else ""
        elif suffix == ".m4a":
            tags = MP4(path)
            artist = (tags.get("©ART") or [""])[0].strip()
            year = (tags.get("©day") or [""])[0].strip()[:4]
        elif suffix == ".ogg":
            tags = OggVorbis(path)
            artist = (tags.get("artist") or [""])[0].strip()
            year = (tags.get("date") or [""])[0].strip()[:4]
        else:
            return "", ""
    except ID3NoHeaderError:
        return "", ""
    except Exception:
        return "", ""
    return artist, year


def parse_artists_folder(directory: str, recursive: bool = False) -> tuple[Counter, Counter]:
    artists: Counter = Counter()
    years: Counter = Counter()
    files = _collect_files(Path(directory), recursive)
    if not files:
        print(f"No MP3/FLAC/WAV/M4A/OGG files found in {directory}")
        sys.exit(1)

    print(f"Reading tags from {len(files):,} files…", flush=True)
    for path in files:
        artist, year = _read_tags(path)
        if artist:
            artists[artist] += 1
        if year.isdigit() and len(year) == 4:
            years[year] += 1

    return artists, years


def _style_ax(ax) -> None:
    ax.set_facecolor("#0f0f1a")
    ax.tick_params(axis="x", colors="#666680", labelsize=9)
    ax.tick_params(axis="y", colors="#666680", labelsize=9)
    ax.tick_params(axis="y", length=0)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#333350")
    ax.set_axisbelow(True)


def plot_charts(
    artists: Counter,
    years: Counter,
    output: str = "muziqa.png",
    top: int = 20,
) -> None:
    fig, (ax_artists, ax_years) = plt.subplots(1, 2, figsize=(22, 9))
    fig.patch.set_facecolor("#0f0f1a")

    # --- Artists (left) ---
    top_artists = artists.most_common(top)
    if len(top_artists) < top:
        print(f"Warning: only {len(top_artists)} artists found.")
    names, a_vals = zip(*top_artists)
    names = names[::-1]
    a_vals = a_vals[::-1]
    n = len(a_vals)

    cmap = plt.colormaps["plasma"]
    colours = [cmap(i / max(n - 1, 1)) for i in range(n)]

    bars = ax_artists.barh(range(n), a_vals, color=colours, edgecolor="none", height=0.72)
    for bar, val in zip(bars, a_vals):
        ax_artists.text(
            bar.get_width() + 0.15,
            bar.get_y() + bar.get_height() / 2,
            str(val),
            va="center", ha="left", color="#e0e0e0", fontsize=9, fontweight="bold",
        )
    ax_artists.set_yticks(range(n))
    ax_artists.tick_params(axis="y", length=0)
    ax_artists.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax_artists.set_xlabel("Tracks", labelpad=8, color="#888899")
    ax_artists.xaxis.grid(True, color="#222240", linewidth=0.6)
    _style_ax(ax_artists)
    ax_artists.set_yticklabels(names, fontsize=10.5, color="#ffffff", fontweight="bold")

    total = sum(artists.values())
    unique = len(artists)
    ax_artists.set_title(
        f"Top {top} Artists  ·  {total:,} tracks  ·  {unique:,} unique artists",
        fontsize=13, fontweight="bold", color="#c8c8e0", pad=14,
    )

    # --- Years (right) ---
    sorted_years = sorted(years.items(), key=lambda x: x[0])
    yr_labels, yr_vals = zip(*sorted_years) if sorted_years else ([], [])

    y_n = len(yr_vals)
    yr_colours = [cmap(i / max(y_n - 1, 1)) for i in range(y_n)]

    ax_years.bar(range(y_n), yr_vals, color=yr_colours, edgecolor="none", width=0.72)
    ax_years.set_xticks(range(y_n))
    ax_years.set_xticklabels(yr_labels, rotation=45, ha="right", fontsize=9, color="#e0e0e0")
    ax_years.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax_years.set_ylabel("Tracks", labelpad=8, color="#888899")
    ax_years.yaxis.grid(True, color="#222240", linewidth=0.6)
    _style_ax(ax_years)
    ax_years.tick_params(axis="x", length=0, colors="#e0e0e0")
    ax_years.spines["left"].set_visible(False)

    ax_years.set_title(
        f"Tracks by Year  ·  {len(years):,} years",
        fontsize=13, fontweight="bold", color="#c8c8e0", pad=14,
    )

    plt.tight_layout()
    plt.savefig(output, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"Saved → {output}")
    plt.show()


def main() -> None:
    from importlib.metadata import version as pkg_version
    v = pkg_version("muziqa")
    parser = argparse.ArgumentParser(
        description=f"muziqa {v} — plot top artists and tracks by year from a music folder"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {v}")
    parser.add_argument("folder", metavar="DIR", help="Directory of MP3/FLAC/WAV/M4A/OGG files (reads tags)")
    parser.add_argument("--artists", metavar="FILE", help=argparse.SUPPRESS)
    parser.add_argument("--flat", action="store_true", help="Search only the given folder, not subfolders")
    parser.add_argument("--output", metavar="FILE", default="muziqa.png", help="Output image file (default: muziqa.png)")
    parser.add_argument("--top", metavar="N", type=int, default=20, help="Number of top artists to plot (default: 20)")
    args = parser.parse_args()

    if args.artists:
        artists, years = parse_artists_txt(args.artists)
    else:
        artists, years = parse_artists_folder(args.folder, recursive=not args.flat)

    if not artists:
        print("No artist data found.")
        sys.exit(1)

    plot_charts(artists, years, args.output, args.top)


if __name__ == "__main__":
    main()
