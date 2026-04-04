# muziqa

Analyze your music collection and plot two side-by-side charts: top artists and tracks by year.

![Top 20 Artists chart](muziqa.png)

## Install

```
pipx install muziqa
```

## Usage

Point it at a folder of music files (MP3, FLAC, WAV):

```
$ muziqa /path/to/music
```

This reads the tags from every supported file in the folder (and all subfolders) and saves a bar chart to `muziqa.png` in the current directory.

### Options

| Option | Description |
|--------|-------------|
| `DIR` | Directory of MP3/FLAC/WAV files (reads tags) |
| `--flat` | Search only the given folder, not subfolders |
| `--artists FILE` | Path to a plain-text `artists.txt` file instead |
| `--output FILE` | Output image filename (default: `muziqa.png`) |
| `--top N` | Number of top artists to show (default: 20) |

### Examples

```
$ muziqa ~/Music
$ muziqa ~/Music --flat
$ muziqa ~/Music --top 30 --output top30.png
$ muziqa ~/Music --artists artists.txt
```
