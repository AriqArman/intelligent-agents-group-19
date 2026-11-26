import builtins
from pathlib import Path

new = True

def print(*args):
    """Like normal print but prints to a file."""
    global new
    if new:
        with open(Path(__file__).parent / "output.txt", "w") as f:
            f.write("")
        new = False
    with open(Path(__file__).parent / "output.txt", "a") as f:
        builtins.print(*args, file=f)