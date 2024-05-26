from pathlib import Path
import subprocess

from typing import List

def run(
    cmds: List[List[str]],
    cwd: Path = Path(__file__).parent,
    allow_error: bool=False
) -> str:
    proc = None
    for cmd in cmds:
        proc = subprocess.Popen(
            cmd,
            stdin=proc.stdout if proc else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            text=True,
        )
    if proc is None:
        raise ValueError("cmds must be a list of at least one command")
    stdout, stderr = proc.communicate()
    if proc.returncode != 0 and not allow_error:
        print(f"{stdout}")
        print(f"{stderr}")
        print(f"{proc.returncode}")
        # raise BashError(
        #     message=stderr,
        #     status=proc.returncode,
        # )
    return stdout


def exec(
    cmds: List[str],
    cwd: Path = Path(__file__).parent,
    allow_error: bool = False,
) -> str:
    proc = None
    for cmd in cmds:
        proc = subprocess.Popen(
            cmd.split(),
            stdin=proc.stdout if proc else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            text=True,
        )
    if proc is None:
        raise ValueError("cmds must be a list of at least one command")
    stdout, stderr = proc.communicate()
    if proc.returncode != 0 and not allow_error:
        print(f"{stdout}")
        print(f"{stderr}")
        print(f"{proc.returncode}")
        # raise BashError(
        #     message=stderr,
        #     status=proc.returncode,
        # )
    return stdout