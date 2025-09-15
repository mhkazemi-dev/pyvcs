# pyvcs

A simple, lightweight version control system (VCS) written in Python. It provides basic snapshot-based tracking of file changes in a directory, with automatic detection of modifications and a graphical user interface (GUI) for viewing history, diffs, and file structures.

## Description

pyvcs is designed as a minimalistic VCS tool for local directories. It creates "snapshots" of your project's files, storing hashed blobs of file contents and JSON manifests for each snapshot. Changes are detected automatically via a file watcher, triggering auto-snapshots, or you can create them manually. The GUI allows browsing snapshots on a timeline, comparing changes, viewing diffs, and exporting overviews.

This tool is ideal for small projects, personal use, or educational purposes to understand VCS basics. It does not support advanced features like branching, merging, or remote repositories.

## Features

- **Automatic Snapshots**: Monitors the directory for changes and creates snapshots after a debounce period (default: 2 seconds).
- **Manual Snapshots**: Trigger snapshots on demand via the GUI.
- **Snapshot Timeline**: Visual timeline in the GUI to select and compare up to two snapshots.
- **File Tree View**: Displays files with color-coded highlights for added (green), removed (red), or modified (blue) files between snapshots.
- **Diff Views**: Unified diffs for text files; supports whole-snapshot diffs or per-file diffs.
- **Edit Snapshot Messages**: Add or edit custom messages for snapshots.
- **Export Overview**: Generate a CSV summary of changes between two snapshots, including added/removed/modified files and diffs.
- **Snapshot Viewer**: Display exported overviews as HTML tables in the GUI.
- **Efficient Storage**: Uses SHA1 hashing to avoid duplicating unchanged files across snapshots.

## Requirements

- Python 3.8 or higher
- PySide6 (for the GUI)
- watchdog (for file watching)

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd pyvcs
   ```

2. Install dependencies:
   ```
   pip install PySide6 watchdog
   ```

## Usage

### Initializing a Repository

To initialize a new pyvcs repository in a directory (creates a `.pyvcs` folder and launches the GUI):
```
python main.py --init /path/to/your/project
```

### Opening an Existing Repository

To launch the GUI for an existing repository (defaults to current directory if `--path` is omitted):
```
python main.py --path /path/to/your/project
```

Or, from the current directory:
```
python main.py
```

### GUI Controls

- **Manual Snapshot**: Click to create a new snapshot with an optional message.
- **Timeline**: Click circles to select up to two snapshots. The latest is auto-selected if none are chosen.
- **File Tree**: Browse files in the selected snapshot(s). Colors indicate changes; click a file to view its diff.
- **Summary View**: Shows snapshot metadata (e.g., timestamp, message).
- **Diff View**: Displays changes between selected snapshots or for a clicked file.
- **Edit Message**: Edit the message for the selected snapshot (visible when one snapshot is selected).
- **Export Overview**: Exports a CSV of changes between two selected snapshots (to `snapshot_overview.csv` in the repo root).
- **Show Snapshot**: Displays the exported CSV as an HTML table in the diff view.

### Command-Line Options

- `--init <path>`: Initialize a repo at the specified path and launch the GUI.
- `--path <path>`: Open the GUI for the repo at the specified path (optional; defaults to `.`).

## How It Works

### Core Components

- **Repo Initialization**: Creates `.pyvcs/blobs` for file contents (hashed with SHA1) and `.pyvcs/manifests` for JSON snapshot metadata. A `HEAD` file tracks the current snapshot fingerprint.
- **Snapshots**: 
  - Collects all files in the directory (excluding `.pyvcs`).
  - Computes SHA1 hashes and sizes for each file.
  - Generates a unique fingerprint for the set of files.
  - If the fingerprint differs from `HEAD`, creates a new manifest JSON (e.g., `<fingerprint>-<timestamp>.json`) and stores new blobs.
  - Supports custom messages; auto-snapshots use "Auto snapshot".
- **File Watcher**: Uses `watchdog` to monitor directory events (create/modify/delete). Debounces events to avoid rapid snapshots.
- **Storage**:
  - Blobs are stored only if unique (based on hash), saving space.
  - Manifests include file paths, hashes, sizes, timestamps, and messages.
- **Diffs**: Uses `difflib` for text-based unified diffs; binary files are noted but not diffed.
- **Config**: Optional `.pyvcs_config.json` for future extensions (currently minimal use).

### Limitations

- No support for branches, merges, or conflicts.
- No remote synchronization or collaboration features.
- Diffs are text-only; binary files are handled but not diffed.
- Ignores the `.pyvcs` directory and any errors during file reading.
- Performance may degrade in very large directories (walks the entire tree for each snapshot).
- No undo or revert functionality.

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests for bug fixes, features, or improvements.

1. Fork the repository.
2. Create a feature branch.
3. Commit your changes.
4. Push to the branch.
5. Open a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details (if not present, assume standard MIT terms).
