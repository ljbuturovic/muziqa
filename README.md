# muziqa

Analyze your music collection and generate interesting charts:
- **Top artists** by track count
- **Tracks by decade**
- **Tracks by year**, with a 5-year rolling average of mean tracks per artist
- **Tracks by country** (optional, see below)

![muziqa chart](muziqa.png)

## Install

```
pipx install muziqa
```

Works on Linux, Mac. Probably Windows too, but I didn't test it

## Usage

Point it at a folder of music files:

```
$ muziqa /path/to/music
```

Reads tags from all supported files in the folder and subfolders, and saves two charts:
- `muziqa.png` — top artists + tracks by decade
- `muziqa_years.png` — tracks by year with rolling average

Supported formats: **MP3, FLAC, WAV, M4A, OGG**

### Country chart

```
$ muziqa /path/to/music --country
```

Looks up each artist's country of origin from [MusicBrainz](https://musicbrainz.org) and saves a third chart:
- `muziqa_country.png` — tracks by country

> **Note:** The first run queries MusicBrainz for every unique artist at 1 request/second (required by their API). For a large collection this can take 30–60 minutes. Results are cached in `muziqa_country_cache.json` so subsequent runs are instant.

### All options

| Option | Description |
|--------|-------------|
| `DIR` | Directory of music files to analyze |
| `--flat` | Search only the given folder, not subfolders |
| `--country` | Fetch artist countries and plot by country |
| `--output FILE` | Output image filename (default: `muziqa.png`) |
| `--top N` | Number of top entries to show (default: 20) |

### Examples

```
$ muziqa ~/Music
$ muziqa ~/Music --flat
$ muziqa ~/Music --country
$ muziqa ~/Music --top 30 --output top30.png
```
