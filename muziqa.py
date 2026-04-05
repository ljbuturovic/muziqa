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
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker


def parse_artists_txt(filepath: str) -> tuple[Counter, Counter, dict[str, set]]:
    artist_pattern = re.compile(r"Artist:\s*(.+?)\s*,\s*Year:")
    year_pattern = re.compile(r"Year:\s*(\d{4})")
    artists: Counter = Counter()
    years: Counter = Counter()
    year_artists: defaultdict[str, set] = defaultdict(set)
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            artist_match = artist_pattern.search(line)
            year_match = year_pattern.search(line)
            name = artist_match.group(1).strip() if artist_match else ""
            year = year_match.group(1) if year_match else ""
            if name:
                artists[name] += 1
            if year:
                years[year] += 1
                if name:
                    year_artists[year].add(name)
    return artists, years, dict(year_artists)


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


def parse_artists_folder(directory: str, recursive: bool = False) -> tuple[Counter, Counter, dict[str, set]]:
    artists: Counter = Counter()
    years: Counter = Counter()
    year_artists: defaultdict[str, set] = defaultdict(set)
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
            if artist:
                year_artists[year].add(artist)

    return artists, years, dict(year_artists)


def _aggregate_decades(
    years: Counter, year_artists: dict[str, set]
) -> tuple[Counter, dict[str, int]]:
    decades: Counter = Counter()
    decade_artists: defaultdict[str, set] = defaultdict(set)
    for year, count in years.items():
        decade = year[:3] + "0s"
        decades[decade] += count
        decade_artists[decade] |= year_artists.get(year, set())
    return decades, {d: len(s) for d, s in decade_artists.items()}


def _style_ax(ax) -> None:
    ax.set_facecolor("#0f0f1a")
    ax.tick_params(axis="x", colors="#666680", labelsize=9)
    ax.tick_params(axis="y", colors="#666680", labelsize=9)
    ax.tick_params(axis="y", length=0)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#333350")
    ax.set_axisbelow(True)


def _plot_artists(ax, artists: Counter, top: int, cmap) -> None:
    top_artists = artists.most_common(top)
    if len(top_artists) < top:
        print(f"Warning: only {len(top_artists)} artists found.")
    names, a_vals = zip(*top_artists)
    names = names[::-1]
    a_vals = a_vals[::-1]
    n = len(a_vals)
    colours = [cmap(i / max(n - 1, 1)) for i in range(n)]

    bars = ax.barh(range(n), a_vals, color=colours, edgecolor="none", height=0.72)
    for bar, val in zip(bars, a_vals):
        ax.text(
            bar.get_width() + 0.15, bar.get_y() + bar.get_height() / 2,
            str(val), va="center", ha="left", color="#e0e0e0", fontsize=9, fontweight="bold",
        )
    ax.set_yticks(range(n))
    ax.tick_params(axis="y", length=0)
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.set_xlabel("Tracks", labelpad=8, color="#888899")
    ax.xaxis.grid(True, color="#222240", linewidth=0.6)
    _style_ax(ax)
    ax.set_yticklabels(names, fontsize=10.5, color="#ffffff", fontweight="bold")

    total = sum(artists.values())
    unique = len(artists)
    ax.set_title(
        f"Top {top} Artists  ·  {total:,} tracks  ·  {unique:,} unique artists",
        fontsize=13, fontweight="bold", color="#c8c8e0", pad=14,
    )


def _plot_time_bars(ax, labels, vals, title: str, cmap,
                    unique_counts: dict[str, int] | None = None, rolling: bool = False) -> None:
    """Bar chart, with an optional mean-tracks-per-artist line on a twin axis."""
    n = len(vals)
    colours = [cmap(i / max(n - 1, 1)) for i in range(n)]

    ax.bar(range(n), vals, color=colours, edgecolor="none", width=0.72)
    ax.set_xticks(range(n))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=9, color="#e0e0e0")
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.set_ylabel("Tracks", labelpad=8, color="#888899")
    ax.yaxis.grid(True, color="#222240", linewidth=0.6)
    _style_ax(ax)
    ax.tick_params(axis="x", length=0, colors="#e0e0e0")
    ax.spines["left"].set_visible(False)
    ax.set_title(title, fontsize=13, fontweight="bold", color="#c8c8e0", pad=14)

    if unique_counts is None:
        return

    mean_vals = [vals[i] / unique_counts[labels[i]] if unique_counts.get(labels[i]) else None for i in range(n)]

    if rolling:
        window = 5
        line_vals = []
        for i in range(n):
            chunk = [v for v in mean_vals[max(0, i - window // 2):i + window // 2 + 1] if v is not None]
            line_vals.append(sum(chunk) / len(chunk) if chunk else None)
    else:
        line_vals = mean_vals

    ax_twin = ax.twinx()
    ax_twin.set_facecolor("none")
    ax_twin.plot(range(n), line_vals, color="#00e5ff", linewidth=2.5, zorder=5)
    ax_twin.set_ylabel("Mean tracks per artist", labelpad=8, color="#00e5ff")
    ax_twin.tick_params(axis="y", colors="#00e5ff", labelsize=9, length=0)
    ax_twin.spines["top"].set_visible(False)
    ax_twin.spines["left"].set_visible(False)
    ax_twin.spines["bottom"].set_visible(False)
    ax_twin.spines["right"].set_color("#00e5ff")
    ax_twin.spines["right"].set_alpha(0.4)


def _years_output(output: str) -> str:
    p = Path(output)
    return str(p.with_stem(p.stem + "_years"))


def plot_main(
    artists: Counter,
    decades: Counter,
    output: str = "muziqa.png",
    top: int = 20,
) -> None:
    fig, (ax_artists, ax_decades) = plt.subplots(1, 2, figsize=(22, 9))
    fig.patch.set_facecolor("#0f0f1a")
    cmap = plt.colormaps["plasma"]

    _plot_artists(ax_artists, artists, top, cmap)

    sorted_decades = sorted(decades.items())
    d_labels, d_vals = zip(*sorted_decades) if sorted_decades else ([], [])
    _plot_time_bars(
        ax_decades, d_labels, d_vals,
        f"Tracks by Decade  ·  {len(decades):,} decades",
        cmap,
    )

    plt.tight_layout()
    plt.savefig(output, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"Saved → {output}")
    plt.show()


def plot_years(
    years: Counter,
    year_artists: dict[str, set],
    output: str = "muziqa_years.png",
) -> None:
    year_unique = {y: len(s) for y, s in year_artists.items()}
    sorted_years = sorted(years.items())
    yr_labels, yr_vals = zip(*sorted_years) if sorted_years else ([], [])

    fig, ax = plt.subplots(figsize=(14, 7))
    fig.patch.set_facecolor("#0f0f1a")
    cmap = plt.colormaps["plasma"]

    _plot_time_bars(
        ax, yr_labels, yr_vals,
        f"Tracks by Year  ·  {len(years):,} years  ·  5-yr rolling avg",
        cmap, unique_counts=year_unique, rolling=True,
    )

    plt.tight_layout()
    plt.savefig(output, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"Saved → {output}")
    plt.show()


def main() -> None:
    from importlib.metadata import version as pkg_version
    v = pkg_version("muziqa")
    parser = argparse.ArgumentParser(
        description=f"muziqa {v} — plot top artists and tracks by decade/year from a music folder"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {v}")
    parser.add_argument("folder", metavar="DIR", help="Directory of MP3/FLAC/WAV/M4A/OGG files (reads tags)")
    parser.add_argument("--artists", metavar="FILE", help=argparse.SUPPRESS)
    parser.add_argument("--flat", action="store_true", help="Search only the given folder, not subfolders")
    parser.add_argument("--output", metavar="FILE", default="muziqa.png", help="Output image file (default: muziqa.png)")
    parser.add_argument("--top", metavar="N", type=int, default=20, help="Number of top artists to plot (default: 20)")
    args = parser.parse_args()

    if args.artists:
        artists, years, year_artists = parse_artists_txt(args.artists)
    else:
        artists, years, year_artists = parse_artists_folder(args.folder, recursive=not args.flat)

    if not artists:
        print("No artist data found.")
        sys.exit(1)

    decades, _ = _aggregate_decades(years, year_artists)
    plot_main(artists, decades, args.output, args.top)
    plot_years(years, year_artists, _years_output(args.output))


if __name__ == "__main__":
    main()
