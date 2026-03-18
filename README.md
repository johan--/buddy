# ascii_play

Live terminal video player with true 24-bit color rendering.  
Like `mpv -vo caca` — but actually good.

```
ascii_play video.mp4
```

![demo](https://via.placeholder.com/800x400?text=ascii_play+demo)

---

## How it works

Instead of caca's 256-color palette, ascii_play uses **24-bit true color ANSI escapes** (`\033[38;2;R;G;Bm`) — one per terminal cell, every frame. Combined with Unicode half-block characters (`▀`) it gets **2× vertical resolution** out of the terminal grid with full RGB fidelity.

Three render modes:

| Mode | Technique | Resolution | Best for |
|------|-----------|------------|----------|
| `half` *(default)* | `▀` fg+bg color | 2× vertical | Everything |
| `ascii` | Density chars `@%#*+=-:. ` + color | 1× | Classic look |
| `braille` | Braille dots `⣿` + color | 2×4 per cell | High contrast, detail |

---

## Install

**From PyPI (once published):**
```bash
pip install ascii_play
```

**From source:**
```bash
git clone https://github.com/yourname/ascii_play
cd ascii_play
pip install -e .
```

Now the `ascii_play` command is available anywhere in your terminal.

---

## Usage

```
ascii_play [OPTIONS] filename

Arguments:
  filename    Video file to play (any format FFmpeg supports)

Options:
  -m, --mode   MODE   Render mode: half (default) | ascii | braille
  -q, --quality N     Render quality 1-3 (default: 2)
  -s, --scale F       Fraction of terminal to use, 0.1–1.0 (default: 1.0)
  --loop              Loop video indefinitely
  --no-info           Hide the status bar
  --list-modes        Print available render modes and exit
  --version           Print version and exit
  -h, --help          Show this message and exit
```

**Examples:**

```bash
# Play with defaults (half-block, quality 2)
ascii_play video.mp4

# Best quality
ascii_play video.mp4 -q 3

# Braille mode, looping
ascii_play video.mp4 -m braille --loop

# Use 80% of the terminal, hide status bar
ascii_play video.mp4 -s 0.8 --no-info

# Classic ASCII art look
ascii_play video.mp4 -m ascii
```

---

## Quality levels

| Level | Method | Speed | Quality |
|-------|--------|-------|---------|
| `-q 1` | Nearest-neighbor | Fastest | Aliased, shimmers |
| `-q 2` | 4-tap supersample | Fast (default) | Smooth, no shimmer |
| `-q 3` | Full box filter | Slower | Best, like a real downscaler |

---

## Terminal requirements

Your terminal must support **24-bit true color**. Most modern terminals do:

- ✅ Windows Terminal
- ✅ iTerm2
- ✅ Kitty / WezTerm / Alacritty
- ✅ GNOME Terminal (3.36+)
- ✅ WSL with Windows Terminal
- ❌ macOS default Terminal.app (256 colors only — use iTerm2)
- ❌ old PuTTY

To check: `echo $COLORTERM` — should print `truecolor` or `24bit`.

---

## Standalone binary (no Python required)

Build a single self-contained executable that users can just download and run:

```bash
pip install pyinstaller
bash build_release.sh
# → dist/ascii_play  (~30MB, includes Python + numpy + FFmpeg)
```

To release on GitHub: upload `dist/ascii_play` as a release asset.  
Users download it, `chmod +x ascii_play`, and run it — no pip, no Python.

---

## Repo structure

```
ascii_play/
├── ascii_play/
│   ├── __init__.py     # package version + public API
│   ├── ansi.py         # ANSI escape helpers
│   ├── resize.py       # frame downscaling (3 quality levels)
│   ├── renderers.py    # half / ascii / braille renderers
│   ├── player.py       # decode + render loop
│   └── cli.py          # argparse CLI entrypoint
├── pyproject.toml      # package metadata + console_scripts
├── build_release.sh    # PyInstaller bundle script
└── README.md
```

---

## License

MIT
