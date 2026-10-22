"""Copy the native extension into one explicitly selected Hermes home.

Never patches core, installs dependencies, changes config, or restarts anything.
Existing destinations (including symlinks) are never overwritten.
"""
from pathlib import Path
import argparse
import shutil

SOURCE = Path(__file__).resolve().parents[1] / 'slack_board'


def install(home: Path) -> Path:
    target = home.expanduser().resolve() / 'plugins' / 'slack-board'
    if target.exists() or target.is_symlink():
        raise FileExistsError(f'{target} already exists; back it up/remove it explicitly before updating')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', required=True, type=Path, help='Exact target Hermes profile home')
    args = parser.parse_args()
    try:
        target = install(args.home)
    except FileExistsError as exc:
        parser.exit(1, str(exc) + '\n')
    print(f'Copied native plugin to {target}. No configuration or gateway changes made.')
    print('Next: use this profile to run `hermes plugins enable slack-board`, then `hermes plugins doctor slack-board`.')


if __name__ == '__main__':
    main()
