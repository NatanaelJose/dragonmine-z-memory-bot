# DragonMine Z: Perfect Recall

### A lightweight computer-vision autoplayer for **Shadow Boxing and Rhythm**

DragonMine Z: Perfect Recall automates two DragonMine Z minigames entirely on
your computer. It memorizes and replays *Boxe Sombrio* (Shadow Boxing)
sequences, and its **Rhythm Drive** tracks notes approaching from both sides,
taps regular notes, and holds sustain notes until completion.

The bot needs no manually calibrated screen region. It finds the DragonMine
window, captures only its client area, scans the entire frame, and separates
the real symbols from HUD elements, titles, menus, and background noise.

> This is an unofficial fan-made accessibility and automation project. It is
> not affiliated with DragonMine Z, Minecraft, Mojang, or Microsoft. Respect
> the rules of the server or environment where you use it.

## Highlights

- Automatic DragonMine window discovery by title
- Client-area capture without the Windows title bar
- Fixed color-to-direction recognition; no fragile sprite-shape matching
- Single-frame memorization for fast response
- Multi-row sequence reading for advanced levels
- Up to 32 symbols per sequence
- Automatic start/end prompt handling
- Native arrow-key input through `pynput`
- Real-time two-sided rhythm-lane tracking
- Predictive tap timing and key-down/key-up sustain control
- Rhythm autoplay validated through level 76 in real gameplay
- Live diagnostic overlay with accepted and rejected contour explanations
- Synthetic regression tests for real bugs found during gameplay

## Direction mapping

DragonMine Z uses a consistent color for each direction:

| Symbol color | Direction | Key |
| --- | --- | --- |
| Yellow | Up | `Up Arrow` |
| Green | Down | `Down Arrow` |
| Cyan | Left | `Left Arrow` |
| Magenta | Right | `Right Arrow` |

The yellow symbol can look like a cross rather than a conventional arrow.
For that reason, the detector reads the dominant HSV hue instead of trying to
infer direction from sprite geometry.

## How it works

The runtime is a small state machine driven entirely by visual state:

1. **Find the game.** The bot searches for a window whose title contains
   `DragonMine` and resolves its real client-area coordinates through Win32.
2. **Capture the frame.** `mss` captures only the game content, excluding the
   title bar and window borders.
3. **Build a color mask.** OpenCV keeps vivid, bright pixels and joins small
   gaps with a morphological close operation.
4. **Filter candidates.** Contours are checked for area, width, height, aspect
   ratio, dominant hue, and consistent symbol size.
5. **Read rows.** Symbols are sorted left-to-right inside each row. Nearby rows
   with compatible symbol sizes are joined top-to-bottom, so wrapped sequences
   continue in the correct order.
6. **Reject noise.** Implausible lengths and sequences made entirely from one
   repeated direction are discarded. This prevents yellow title text such as
   `Boxe Sombrio` from being interpreted as many `up` symbols.
7. **Memorize once.** As soon as a valid sequence appears, the bot stores that
   single reading. It does not wait for multi-frame stabilization.
8. **Wait for Repeat.** Inputs are sent only after the symbols disappear,
   marking the transition from `Memorize!` to `Repita!`.
9. **Handle prompts.** A wide green prompt panel with bright inner text is
   recognized separately and advanced automatically.

## Requirements

- Windows 10 or Windows 11
- Python 3.11 or newer
- Minecraft running DragonMine Z in a visible window
- The game window title must contain `DragonMine`

The capture and focus code uses Windows APIs, so other operating systems are
not currently supported.

## Desktop app

Perfect Recall also includes a lightweight native Windows control panel built
with Tauri 2. The desktop app keeps the proven Python/OpenCV detector, runs it
as a hidden local process, and presents its status through a gamer-style HUD.

The interface provides:

- one-click start and stop controls;
- dark and light themes saved between sessions;
- `Fast`, `Safe`, and custom input timing profiles;
- live detector state and runtime telemetry;
- a color-coded view of the last memorized sequence;
- a dedicated **Rhythm Drive** mode for taps and sustains;
- fully local processing with no frame uploads.

End users only need the generated Windows installer. Python, Node.js, and Rust
are build-time dependencies and are not required after installation.

### Desktop development

Install the Python dependencies, including the desktop packager, then install
the frontend packages:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
cd desktop
npm install
npm run tauri dev
```

The development app automatically finds `main.py` and the project `venv` in a
parent directory. `DRAGONMINE_BOT_ROOT` can point it at another checkout.

### Build the Windows installer

From `desktop/`, run:

```powershell
npm run bundle
```

This command creates a self-contained Python vision runtime, embeds it as a
Tauri resource, and produces an NSIS installer under
`desktop/src-tauri/target/release/bundle/nsis/`.

### Rhythm Drive

Select **Rhythm Drive**, open the rhythm minigame, leave its green start
prompt visible, and choose **Start rhythm bot**. Perfect Recall focuses the
DragonMine window, starts the song, and watches the narrow horizontal lane in
real time.

Direction is read from each note's fixed color. Motion determines which of the
two receptors it is approaching. The tracker predicts the center crossing,
sends a short arrow-key tap for regular notes, and keeps the key down for a
sustain until its trail completes. Receptor coordinates are normalized to the
game window, so the detector works across window sizes without a manual crop.

The tuned default uses an 8 ms prediction lead and a narrow hit tolerance. It
was validated in real gameplay through level 76. Keep the game window steady
while Rhythm Drive is active.

The rhythm bot can also be started directly:

```powershell
.\venv\Scripts\python.exe main.py --game rhythm
```

### Rhythm diagnostic capture

Developers can still record a twelve-second timing sample without sending
gameplay input:

```powershell
.\venv\Scripts\python.exe main.py --game rhythm-capture
```

Each session is saved under
`Documents/DragonMine Perfect Recall/rhythm_captures/<timestamp>/` with:

- `lane.avi` - the cropped horizontal note lane in MJPG format;
- `timestamps.csv` - the measured time of every captured frame;
- `reference.png` - one full game frame for locating the hit zones;
- `metadata.json` - resolution, normalized crop, frame count, and measured FPS.

For a useful diagnostic sample, include all four directions and at least one
sustain note. The files remain local and are intended for offline detector and
timing analysis.

## Installation

Clone the repository and create a virtual environment:

```powershell
git clone https://github.com/NatanaelJose/dragonmine-z-memory-bot.git
cd dragonmine-z-memory-bot
python -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Running the bot

1. Start Minecraft and open the DragonMine Z world or server.
2. Enter the Shadow Boxing memory minigame.
3. Run:

```powershell
.\venv\Scripts\python.exe main.py
```

The bot waits until it finds the game window. Stop it at any time with
`Ctrl+C` in the terminal.

### Input speed

The default `fast` profile is the fastest timing confirmed reliable during
real gameplay:

```powershell
.\venv\Scripts\python.exe main.py --speed fast
```

Use `safe` if a machine or game instance occasionally misses inputs:

```powershell
.\venv\Scripts\python.exe main.py --speed safe
```

| Profile | Key hold | Delay between keys | Status |
| --- | ---: | ---: | --- |
| `fast` | 0.03 s | 0.03 s | Default; tested successfully |
| `safe` | 0.05 s | 0.05 s | More timing margin |

Advanced users can override either value directly:

```powershell
.\venv\Scripts\python.exe main.py --hold-time 0.04 --key-delay 0.04
```

Values of `0.02/0.02` were tested and dropped inputs, so they are not provided
as a built-in profile. The selected timing is printed when the bot starts, and
the measured send duration is logged after each sequence.

## Live detector

Use the live overlay before changing detection thresholds or when a new visual
false positive appears:

```powershell
.\venv\Scripts\python.exe debug_live.py
```

The overlay displays:

- green rectangles for accepted symbols;
- red rectangles for rejected contours;
- the rejection reason beside each contour;
- the final ordered direction sequence;
- prompt-screen detection state.

Global shortcuts work while Minecraft keeps keyboard focus:

| Shortcut | Action |
| --- | --- |
| `F8` | Freeze and save the current frame |
| `F9` | Resume live capture |
| `F10` | Save without pausing |

With the preview focused, `Space`, `R`, `S`, and `Q`/`Esc` provide equivalent
controls. Saved snapshots are written to `debug_frames/` as three files with a
shared timestamp:

- `*_original.png` - untouched captured frame
- `*_overlay.png` - annotated detector decisions
- `*_mask.png` - binary color mask

On Windows the preview is excluded from screen capture to prevent recursive
feedback. It can appear transparent when focused; use the global function-key
shortcuts without clicking it.

## One-shot diagnostic capture

For a simple delayed screenshot without a live preview:

```powershell
.\venv\Scripts\python.exe debug_capture.py
```

After a five-second countdown it writes `debug_window.png` and
`debug_window_mask.png` in the project directory.

## Input-only test

To verify that the game accepts `pynput` events independently from vision:

```powershell
.\venv\Scripts\python.exe test_keys.py 10 left,left,down 0.05 0.05
```

The arguments are the countdown in seconds, a comma-separated direction
sequence, key hold time, and delay between keys. The final two values are
optional and default to `config.py`. Try lower values here before changing the
bot defaults; repeated directions are the best stress test.

## Configuration

Runtime timing and key bindings live in `config.py`:

| Setting | Purpose |
| --- | --- |
| `KEY_MAP` | Maps detected directions to keyboard directions |
| `SPEED_PROFILES` | Named key-hold and inter-key timing profiles |
| `DEFAULT_SPEED_PROFILE` | Profile used when `--speed` is omitted |
| `POLL_INTERVAL` | Delay between visual checks |

Vision thresholds live in `arrow_detector.py`:

| Setting | Purpose |
| --- | --- |
| `SAT_MIN`, `VAL_MIN` | Minimum color saturation and brightness |
| `MIN_BLOB_AREA` | Minimum contour area |
| `MIN_BLOB_WIDTH`, `MIN_BLOB_HEIGHT` | Small-symbol rejection thresholds |
| `MAX_BLOB_WIDTH`, `MAX_BLOB_HEIGHT` | Oversized-HUD rejection thresholds |
| `MAX_ASPECT_RATIO` | Rejects very thin bars and panels |
| `MIN_SEQUENCE_LENGTH` | Minimum complete sequence length |
| `MAX_SEQUENCE_LENGTH` | Maximum complete sequence length; currently 32 |
| `COLOR_HUE_RANGES` | HSV hue range for each direction |

Prefer saving a real original/overlay/mask set before adjusting these values.
Every confirmed visual bug should become a regression test.

## Tests

Run the full offline regression suite after any detector change:

```powershell
.\venv\Scripts\python.exe -m py_compile arrow_detector.py capture.py config.py debug_capture.py debug_live.py main.py rhythm_bot.py rhythm_capture.py rhythm_detector.py window.py
.\venv\Scripts\python.exe test_detector.py
.\venv\Scripts\python.exe test_noise.py
.\venv\Scripts\python.exe test_prompt.py
.\venv\Scripts\python.exe test_sanity.py
.\venv\Scripts\python.exe -m unittest test_rhythm_detector.py
```

The tests cover:

- all four color-to-direction mappings;
- scattered colored HUD noise;
- the real yellow-title false-positive pattern;
- prompt panels versus other green menus;
- entirely repeated noise sequences;
- valid nine-symbol sequences containing repeated directions;
- wrapped sequences read across multiple rows.

## Project structure

```text
arrow_detector.py  Computer-vision pipeline and prompt detection
capture.py         Shared MSS capture helper
config.py          Key bindings and runtime timing
main.py            Bot state machine and keyboard output
rhythm_bot.py      Real-time rhythm capture and native keyboard output
rhythm_detector.py Note geometry, prediction, and sustain state tracking
rhythm_capture.py  Developer timing-sample recorder
window.py          DragonMine window discovery, focus, and client rectangle
debug_live.py      Live annotated detector preview
debug_capture.py   Delayed one-shot screenshot tool
test_*.py          Offline regression and input tests
requirements.txt   Python dependencies
```

## Troubleshooting

### The game window is not found

Confirm that the visible window title contains `DragonMine`. Minimized windows
cannot provide a useful capture; restore the game before starting the bot.

### The sequence is detected but the game ignores inputs

Run `test_keys.py`. If inputs are missed, increase `KEY_HOLD_TIME` or
`KEY_PRESS_DELAY` in `config.py`. Some privilege combinations require the
terminal and Minecraft to run at the same elevation level.

### The detector returns an empty sequence

Run `debug_live.py`, save a frame during `Memorize!`, and inspect the rejection
labels. Do not change hue mappings based only on a text log - use the clean
`*_original.png` and `*_mask.png` files together.

### The preview captures itself

Restart `debug_live.py` and confirm that the terminal prints
`Preview protegido contra recaptura.` Keep Minecraft focused and use
`F8`/`F9`/`F10` instead of clicking the preview.

## Privacy

The bot runs locally. It does not upload screenshots, gameplay data, or input
history. Network access is not required after dependencies are installed.
