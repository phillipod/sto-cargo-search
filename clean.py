import shutil
from pathlib import Path

def clean():
    paths = [
        Path('build'),
        Path('dist'),
        Path('src/sto_cargo_search.egg-info'),
    ]
    for path in paths:
        if path.exists():
            print(f"Removing {path}")
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

if __name__ == '__main__':
    clean()
