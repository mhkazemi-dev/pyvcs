import sys
from pathlib import Path
from PySide6 import QtWidgets
from .vcs import Repo
from .ui import MainWindow


def main():
    import argparse
    parser = argparse.ArgumentParser(description='pyvcs GUI')
    parser.add_argument('--init', help='Initialize repository at target path (absolute or relative)')
    parser.add_argument('--path', help='Path to repository (defaults to current dir)')
    args = parser.parse_args()

    target = Path(args.path) if args.path else Path('.')

    if args.init:
        t = Path(args.init)
        if not t.exists() or not t.is_dir():
            print('Provided --init path does not exist or is not a directory')
            return
        repo = Repo(t)
        repo.init()
        print('Initialized repo at', t)
        # After init, continue to run UI against this repo
        target = t

    repo = Repo(target)
    if not repo.exists():
        print('No repository found. Run with --init <path> first.')
        return

    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow(repo)
    w.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
