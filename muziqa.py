#!/usr/bin/env python3
"""Analyze artists and years from artists.txt or directly from MP3/FLAC/WAV/M4A/OGG tags.

Usage:
  muziqa /path/to/music/dir
  muziqa /path/to/music/dir --flat
  muziqa /path/to/music/dir --country
"""

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# ISO 3166-1 alpha-2 → full country name (common music markets)
_ISO_NAMES = {
    "AD": "Andorra", "AE": "UAE", "AF": "Afghanistan", "AL": "Albania",
    "AM": "Armenia", "AO": "Angola", "AR": "Argentina", "AT": "Austria",
    "AU": "Australia", "AZ": "Azerbaijan", "BA": "Bosnia", "BB": "Barbados",
    "BD": "Bangladesh", "BE": "Belgium", "BF": "Burkina Faso", "BG": "Bulgaria",
    "BJ": "Benin", "BO": "Bolivia", "BR": "Brazil", "BS": "Bahamas",
    "BY": "Belarus", "BZ": "Belize", "CA": "Canada", "CD": "DR Congo",
    "CG": "Congo", "CH": "Switzerland", "CI": "Côte d'Ivoire", "CL": "Chile",
    "CM": "Cameroon", "CN": "China", "CO": "Colombia", "CR": "Costa Rica",
    "CU": "Cuba", "CV": "Cape Verde", "CY": "Cyprus", "CZ": "Czech Republic",
    "DE": "Germany", "DJ": "Djibouti", "DK": "Denmark", "DO": "Dominican Rep.",
    "DZ": "Algeria", "EC": "Ecuador", "EE": "Estonia", "EG": "Egypt",
    "ES": "Spain", "ET": "Ethiopia", "FI": "Finland", "FJ": "Fiji",
    "FR": "France", "GA": "Gabon", "GB": "United Kingdom", "GE": "Georgia",
    "GH": "Ghana", "GM": "Gambia", "GN": "Guinea", "GQ": "Equatorial Guinea",
    "GR": "Greece", "GT": "Guatemala", "GW": "Guinea-Bissau", "GY": "Guyana",
    "HN": "Honduras", "HR": "Croatia", "HT": "Haiti", "HU": "Hungary",
    "ID": "Indonesia", "IE": "Ireland", "IL": "Israel", "IN": "India",
    "IQ": "Iraq", "IR": "Iran", "IS": "Iceland", "IT": "Italy",
    "JM": "Jamaica", "JO": "Jordan", "JP": "Japan", "KE": "Kenya", "KR": "South Korea",
    "KG": "Kyrgyzstan", "KH": "Cambodia", "KZ": "Kazakhstan", "LB": "Lebanon",
    "LK": "Sri Lanka", "LT": "Lithuania", "LU": "Luxembourg", "LV": "Latvia",
    "LY": "Libya", "MA": "Morocco", "MD": "Moldova", "ME": "Montenegro",
    "MG": "Madagascar", "MK": "North Macedonia", "ML": "Mali", "MM": "Myanmar",
    "MN": "Mongolia", "MR": "Mauritania", "MT": "Malta", "MU": "Mauritius",
    "MW": "Malawi", "MX": "Mexico", "MY": "Malaysia", "MZ": "Mozambique",
    "NA": "Namibia", "NE": "Niger", "NG": "Nigeria", "NI": "Nicaragua",
    "NL": "Netherlands", "NO": "Norway", "NP": "Nepal", "NZ": "New Zealand",
    "OM": "Oman", "PA": "Panama", "PE": "Peru", "PG": "Papua New Guinea",
    "PH": "Philippines", "PK": "Pakistan", "PL": "Poland", "PT": "Portugal",
    "PY": "Paraguay", "QA": "Qatar", "RO": "Romania", "RS": "Serbia",
    "RU": "Russia", "RW": "Rwanda", "SA": "Saudi Arabia", "SC": "Seychelles",
    "SD": "Sudan", "SE": "Sweden", "SG": "Singapore", "SI": "Slovenia",
    "SK": "Slovakia", "SL": "Sierra Leone", "SN": "Senegal", "SO": "Somalia",
    "SR": "Suriname", "SS": "South Sudan", "ST": "São Tomé", "SV": "El Salvador",
    "SY": "Syria", "SZ": "Eswatini", "TD": "Chad", "TG": "Togo",
    "TH": "Thailand", "TJ": "Tajikistan", "TL": "East Timor", "TM": "Turkmenistan",
    "TN": "Tunisia", "TO": "Tonga", "TR": "Turkey", "TT": "Trinidad & Tobago",
    "TW": "Taiwan", "TZ": "Tanzania", "UA": "Ukraine", "UG": "Uganda",
    "US": "United States", "UY": "Uruguay", "UZ": "Uzbekistan", "VE": "Venezuela",
    "VN": "Vietnam", "XC": "Czechoslovakia", "XE": "England", "XG": "East Germany",
    "XI": "Northern Ireland", "XS": "Scotland", "XW": "Wales",
    "XY": "Yugoslavia", "YE": "Yemen", "YU": "Yugoslavia", "PR": "Puerto Rico", "ZA": "South Africa", "ZM": "Zambia",
    "ZW": "Zimbabwe",
}


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


def _mb_lookup(artist: str, user_agent: str) -> dict[str, str]:
    """Return {"country": iso_code, "genre": name} for artist from MusicBrainz."""
    query = urllib.parse.urlencode({"query": f'artist:"{artist}"', "fmt": "json", "limit": 1})
    url = f"https://musicbrainz.org/ws/2/artist/?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            hits = data.get("artists", [])
            if hits:
                hit = hits[0]
                country = hit.get("country", "")
                tags = sorted(hit.get("tags", []), key=lambda t: t.get("count", 0), reverse=True)
                genre = tags[0]["name"].title() if tags else ""
                return {"country": country, "genre": genre}
    except Exception:
        pass
    return {"country": "", "genre": ""}


def fetch_mb_data(artists: Counter, cache_path: Path, version: str,
                  need_country: bool, need_genre: bool) -> dict[str, dict[str, str]]:
    """Return {artist: {"country": ..., "genre": ...}}, using and updating a local cache."""
    cache: dict[str, dict[str, str]] = {}
    if cache_path.exists():
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
        # migrate old string-valued cache (country only)
        for k, v in raw.items():
            cache[k] = v if isinstance(v, dict) else {"country": v, "genre": ""}

    def needs_fetch(artist: str) -> bool:
        if artist not in cache:
            return True
        if need_genre and not cache[artist].get("genre") and cache[artist].get("genre") != "__none__":
            return True
        return False

    user_agent = f"muziqa/{version} ( https://pypi.org/project/muziqa/ )"
    to_fetch = [a for a in artists if needs_fetch(a)]

    if to_fetch:
        print(f"Fetching data for {len(to_fetch):,} artists from MusicBrainz…", flush=True)
        for i, artist in enumerate(to_fetch, 1):
            result = _mb_lookup(artist, user_agent)
            # preserve existing country if new lookup returned nothing
            if artist in cache and not result["country"]:
                result["country"] = cache[artist].get("country", "")
            # mark genre as explicitly empty to avoid re-fetching
            if not result["genre"]:
                result["genre"] = "__none__"
            cache[artist] = result
            if i % 50 == 0 or i == len(to_fetch):
                print(f"  {i:,}/{len(to_fetch):,}", flush=True)
                cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
            time.sleep(1)

    return cache


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


def _infix_output(output: str, infix: str) -> str:
    p = Path(output)
    return str(p.with_stem(p.stem + infix))


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
    plt.close()


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
    plt.close()


def _plot_hbar(ax, labels, vals, title: str, cmap, matched: int, total: int) -> None:
    """Shared horizontal bar chart for country and genre plots."""
    n = len(vals)
    colours = [cmap(i / max(n - 1, 1)) for i in range(n)]
    bars = ax.barh(range(n), vals, color=colours, edgecolor="none", height=0.72)
    for bar, val in zip(bars, vals):
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
    ax.set_yticklabels(labels, fontsize=10.5, color="#ffffff", fontweight="bold")
    ax.set_title(
        f"{title}  ·  {matched:,}/{total:,} tracks matched",
        fontsize=13, fontweight="bold", color="#c8c8e0", pad=14,
    )


def plot_country(
    artists: Counter,
    mb_cache: dict[str, dict[str, str]],
    output: str = "muziqa_country.png",
    top: int = 20,
) -> None:
    country_tracks: Counter = Counter()
    for artist, count in artists.items():
        iso = mb_cache.get(artist, {}).get("country", "")
        name = _ISO_NAMES.get(iso, iso) if iso else "Unknown"
        country_tracks[name] += count

    top_countries = country_tracks.most_common(top)
    c_names, c_vals = zip(*top_countries)

    fig, ax = plt.subplots(figsize=(12, 8))
    fig.patch.set_facecolor("#0f0f1a")
    _plot_hbar(
        ax, c_names[::-1], c_vals[::-1], f"Top {top} Countries",
        plt.colormaps["plasma"],
        matched=sum(v for k, v in country_tracks.items() if k != "Unknown"),
        total=sum(country_tracks.values()),
    )
    plt.tight_layout()
    plt.savefig(output, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"Saved → {output}")
    plt.close()


def plot_genre(
    artists: Counter,
    mb_cache: dict[str, dict[str, str]],
    output: str = "muziqa_genre.png",
    top: int = 20,
) -> None:
    genre_tracks: Counter = Counter()
    for artist, count in artists.items():
        genre = mb_cache.get(artist, {}).get("genre", "")
        if genre == "__none__":
            genre = ""
        name = genre if genre else "Unknown"
        genre_tracks[name] += count

    top_genres = genre_tracks.most_common(top)
    g_names, g_vals = zip(*top_genres)

    fig, ax = plt.subplots(figsize=(12, 8))
    fig.patch.set_facecolor("#0f0f1a")
    _plot_hbar(
        ax, g_names[::-1], g_vals[::-1], f"Top {top} Genres",
        plt.colormaps["plasma"],
        matched=sum(v for k, v in genre_tracks.items() if k != "Unknown"),
        total=sum(genre_tracks.values()),
    )
    plt.tight_layout()
    plt.savefig(output, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"Saved → {output}")
    plt.close()


def _read_track_info(path: Path) -> dict | None:
    """Return {artist, title, duration_sec, path} or None if unreadable."""
    from mutagen.id3 import ID3NoHeaderError
    from mutagen.mp3 import MP3
    from mutagen.flac import FLAC
    from mutagen.wave import WAVE
    from mutagen.mp4 import MP4
    from mutagen.oggvorbis import OggVorbis

    suffix = path.suffix.lower()
    try:
        if suffix == ".mp3":
            audio = MP3(path)
            tags = audio.tags or {}
            artist = str(tags.get("TPE1", "")).strip()
            title = str(tags.get("TIT2", "")).strip()
            year = str(tags.get("TDRC", "")).strip()[:4]
            duration = audio.info.length
        elif suffix == ".flac":
            audio = FLAC(path)
            artist = (audio.get("artist") or [""])[0].strip()
            title = (audio.get("title") or [""])[0].strip()
            year = (audio.get("date") or [""])[0].strip()[:4]
            duration = audio.info.length
        elif suffix == ".wav":
            audio = WAVE(path)
            id3 = audio.tags
            artist = str(id3.get("TPE1", "")).strip() if id3 else ""
            title = str(id3.get("TIT2", "")).strip() if id3 else ""
            year = str(id3.get("TDRC", "")).strip()[:4] if id3 else ""
            duration = audio.info.length
        elif suffix == ".m4a":
            audio = MP4(path)
            artist = (audio.get("©ART") or [""])[0].strip()
            title = (audio.get("©nam") or [""])[0].strip()
            year = (audio.get("©day") or [""])[0].strip()[:4]
            duration = audio.info.length
        elif suffix == ".ogg":
            audio = OggVorbis(path)
            artist = (audio.get("artist") or [""])[0].strip()
            title = (audio.get("title") or [""])[0].strip()
            year = (audio.get("date") or [""])[0].strip()[:4]
            duration = audio.info.length
        else:
            return None
    except ID3NoHeaderError:
        return None
    except Exception:
        return None

    return {
        "artist": artist or path.stem,
        "title": title or path.stem,
        "year": year,
        "duration_sec": duration,
        "path": str(path),
    }


def _fmt_duration(secs: float) -> str:
    m, s = divmod(int(secs), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def create_playlist(files: list[Path], description: str, output: str, model: str = "claude-sonnet-4-6") -> None:
    import os
    import warnings

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "This feature requires ANTHROPIC_API_KEY. "
            "Instructions for getting one: "
            "https://github.com/ljbuturovic/refren/blob/main/SETUP.md"
        )
        sys.exit(1)

    try:
        import anthropic
    except ImportError:
        print("Missing dependency: pip install anthropic")
        sys.exit(1)

    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=SyntaxWarning)
            from pydub import AudioSegment
    except ImportError:
        print("Missing dependency: pip install pydub  (also requires ffmpeg)")
        sys.exit(1)

    print(f"Reading track info from {len(files):,} files…", flush=True)
    tracks = [t for f in files if (t := _read_track_info(f)) is not None]

    # Send indices to Claude — avoids Unicode path mangling in the response
    lines = [
        f"{i} | {t['artist']} | {t['title']} | {_fmt_duration(t['duration_sec'])}"
        for i, t in enumerate(tracks)
    ]
    track_list = "\n".join(lines)

    prompt = f"""Here is a music collection with {len(tracks):,} tracks (format: index | artist | title | duration):

{track_list}

Playlist request: {description}

IMPORTANT: Every constraint in the request (duration limit, max songs per artist, lead tune, mood, tempo, etc.) is a HARD rule — not a suggestion. Violating any constraint makes the playlist wrong.

Select tracks from this collection that satisfy ALL constraints. Return ONLY a JSON array of integer indices in playback order, with no other text. Example:
[42, 7, 195, 3]"""

    print("Asking Claude to build the playlist…", flush=True)
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        system=(
            "You are a music expert and playlist curator. "
            "You select and order tracks to match a playlist description. "
            "All constraints (duration, artist limits, mood, tempo, lead tune) are HARD rules — treat them like law, not suggestions. "
            "Do not add more songs by an artist than allowed. Do not exceed the duration limit. "
            "You return only valid JSON — a single array of integer indices, nothing else."
        ),
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text.strip()
    start = response_text.find("[")
    end = response_text.rfind("]") + 1
    if start == -1 or end == 0:
        print("Error: Claude did not return a valid playlist.")
        sys.exit(1)

    indices = json.loads(response_text[start:end])
    if not indices:
        print("Error: Claude returned an empty playlist.")
        sys.exit(1)

    selected = []
    for idx in indices:
        if isinstance(idx, int) and 0 <= idx < len(tracks):
            selected.append(tracks[idx])
        else:
            print(f"  Warning: ignoring invalid index {idx}")

    print(f"\nPlaylist: {len(selected)} tracks")
    for i, t in enumerate(selected, 1):
        print(f"  {i:2}. {t['artist']} — {t['title']}")

    print("\nConcatenating…", flush=True)
    fmt_map = {".mp3": "mp3", ".flac": "flac", ".wav": "wav", ".m4a": "mp4", ".ogg": "ogg"}
    combined = AudioSegment.empty()
    for t in selected:
        path = Path(t["path"])
        fmt = fmt_map.get(path.suffix.lower(), "mp3")
        try:
            combined += AudioSegment.from_file(t["path"], format=fmt)
        except Exception as e:
            print(f"  Warning: skipping {path.name} ({e})")

    combined.export(output, format="mp3")
    print(f"Saved → {output}  ({len(combined) // 60000} min)")

    import csv
    csv_path = Path(output).with_stem(Path(output).stem + "_tracks").with_suffix(".csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["#", "title", "artist", "year", "file"])
        for i, t in enumerate(selected, 1):
            writer.writerow([i, t["title"], t["artist"], t["year"], Path(t["path"]).name])
    print(f"Saved → {csv_path}")


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
    parser.add_argument("--country", action="store_true", help="Fetch artist countries from MusicBrainz and plot by country")
    parser.add_argument("--genre", action="store_true", help="Fetch artist genres from MusicBrainz and plot by genre")
    parser.add_argument("--playlist", metavar="DESC", help="Create a playlist MP3 matching the given description (requires ANTHROPIC_API_KEY and ffmpeg)")
    parser.add_argument("--playlist-output", metavar="FILE", default="playlist.mp3", help="Output file for playlist (default: playlist.mp3)")
    parser.add_argument("--model", metavar="MODEL", default="claude-sonnet-4-6", help="Claude model for --playlist (default: claude-sonnet-4-6). Tip: use 'llm-models -p Anthropic' to list available models --> github.com/ljbuturovic/llm-models")
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
    plot_years(years, year_artists, _infix_output(args.output, "_years"))

    if args.country or args.genre:
        cache_path = Path(args.output).with_name("muziqa_mb_cache.json")
        mb_cache = fetch_mb_data(artists, cache_path, v,
                                 need_country=args.country, need_genre=args.genre)
        if args.country:
            plot_country(artists, mb_cache, _infix_output(args.output, "_country"), args.top)
        if args.genre:
            plot_genre(artists, mb_cache, _infix_output(args.output, "_genre"), args.top)

    if args.playlist:
        files = _collect_files(Path(args.folder), recursive=not args.flat)
        create_playlist(files, args.playlist, args.playlist_output, args.model)


if __name__ == "__main__":
    main()
