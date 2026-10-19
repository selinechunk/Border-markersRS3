# Border markers — quick guide

This little desktop program draws the **edge** of your unlocked world. You give it a map,
it works out which chunk edges sit between unlocked and locked ground, and it hands you an
import string full of tile markers you can paste into your tile-marker app.

Shared edges between two unlocked chunks are skipped, so you only get the outline. A locked
pocket surrounded by unlocked ground gets its own ring.

## Start it

Double-click **BorderMarkers.exe**. That is all — no Python, no install, nothing to set up.
It is one self-contained file, so you can put it on your desktop or a USB stick.

The first launch takes a few seconds while it unpacks itself. Later launches are quick.

> Windows may warn you that it is from an unknown publisher, because the file is not code
> signed. Choose **More info**, then **Run anyway**.
You can also use the browser version at the repository's GitHub Pages URL. It runs the
existing border and export code locally through Pyodide, and fetches map data from Chunk
Picker. The first generation downloads the Python runtime, so an internet connection is
needed. The Pages workflow deploys from the repository's default branch; enable **GitHub
Actions** as the Pages source in repository settings if it is not already selected.

<details>
<summary>Running from source instead, or on Mac or Linux</summary>

From the repo root:

```bash
python3 app.py
```

You need Python 3.10 or newer with `tkinter`. Nothing else to install.

</details>

<details>
<summary>Building the exe yourself</summary>

On Windows, with Python installed:

```powershell
powershell -ExecutionPolicy Bypass -File Border-markersRS3\build_exe.ps1
```

The exe lands in `Border-markersRS3\dist\`. The script puts its build tool in a throwaway venv
under `Border-markersRS3\build`, which you can delete afterwards.

</details>

## Mode 1 — from a Chunk Picker map code

Use this when your map already lives on the Chunk Picker site.

1. Type your map code in **Map code** (for example `BQE`). Case does not matter.
2. Leave **Markers per 64 tiles** at `4`, or change it — see [Marker count](#marker-count).
3. Click **Generate**. It downloads your unlocked chunks, so give it a second.
4. Click **Copy** under the first box, and paste it into your tile-marker app.

Click **Copy chunk IDs** to copy the unlocked chunks as a space-separated list of IDs, such
as `13850 13851`.

If a second box fills in as well, paste that one too. Your border was too long for one
string, so it was split in two.

The status line tells you how it went: `Loaded 48 tiles.` means you got 48 markers.

## Mode 2 — Enklumpman mode

Use this for a 150-tile block game instead of 64-tile chunks. There is no map code — you
just colour in the blocks you have.

1. Tick **Enklumpman mode (150-tile blocks)**. A grid appears.
2. Click the blocks you own. They turn green. Click again to clear one.
   Hold the mouse down and drag to paint a whole run at once.
3. Click **Generate**, then **Copy**.

Things worth knowing about the grid:

- **The gold block is your start block** and is always included. Clicking it does nothing.
- **North is up**, same as the world map.
- **The pale blue dots are landmarks** (Varrock, Falador, Lumbridge and so on), placed where
  they really sit inside their block. They are only there so you can find your bearings.
- **Hover any block** to read its coordinates and tile range at the bottom, for example
  `(19, 23)  x 2857-3006  y 3457-3606  · Burthorpe`.
- **The Blocks box** lists what you have picked, like `19,23 20,23`. Copy it somewhere safe
  to keep a layout, then paste it back and press **Apply** to restore it. **Clear** puts you
  back to just the start block.

Two boxes change their labels in this mode:

- **Map code** becomes **Marker name** — whatever you type names the marker group in your
  tile-marker app. Leave it empty and it is called `ENKLUMPMAN`.
- **Markers per 64 tiles** becomes **Markers per block edge**.

## Marker count

This is how many markers get placed along each edge, counting both corners.

- In map-code mode it is per 64-tile chunk edge. `4` gives a marker every 21 tiles.
- In Enklumpman mode it is per 150-tile block edge. `4` gives a marker every 50 tiles.

Higher means a more solid-looking line, but more markers. Your tile-marker app only holds
**232 markers in total**, and each import string carries at most 127, which is why big maps
come out as two strings.

## If something goes wrong

The status line explains everything. The ones you are most likely to see:

| Status line | What to do |
| --- | --- |
| `Enter a map code.` | The map code box is empty. Not needed in Enklumpman mode. |
| `Enter a marker count from 2 through 64.` | Put a whole number from 2 to 64 in the count box. |
| `No map found for that code.` | Check the code. |
| `That map has no unlocked chunks.` | The map exists but nothing is unlocked on it. |
| `Could not load the map.` | Usually no internet. Try again. |
| `Too many tiles (310). Try a marker count of 3 or less.` | Lower the marker count to the number it suggests. |
| `That map is too big, sorry.` | Your border is too long even at a count of 2. Nothing to be done. |
| `Blocks look like 19,23 20,23.` | The Blocks box has something it cannot read. |
| `Block 99,99 is off the map.` | That block is outside the world. |
| `Nothing to copy.` | You pressed Copy on an empty box. |

A failed Generate leaves your previous strings alone, so you never lose a good result by
mistyping something.
