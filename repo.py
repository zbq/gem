#!/usr/bin/python3
"""
usage: repo.py [-h] [-r REPO] [-i]

optional arguments:
  -h, --help            show this help message and exit
  -r REPO, --repo REPO  local repo path
  -i, --installed       get installed packages
"""

import os
import os.path
import sys
from pathlib import Path
from io import StringIO
import subprocess
from argparse import ArgumentParser

def shell(cmdline, capture_output=False):
    proc = subprocess.run(cmdline, shell=True, capture_output=capture_output,
                          encoding='utf-8', errors='ignore')
    return proc

def dnf(repo):
    if repo:
        return f"dnf --quiet --refresh --repofrompath \"local,{repo}\" --repo local "
    else:
        return f"dnf --quiet --refresh "

def as_lines(stdout, *, skip=0):
    lines = []
    with StringIO(stdout) as file:
        for i in range(skip):
            file.readline()
        for line in file:
            lines.append(line.rstrip("\n"))
    return lines

def installed_pkgs():
    proc = shell("dnf --quiet list --installed", True)
    return {line.split()[0] for line in as_lines(proc.stdout, skip=1)}

def pkgs_of_repo(repo):
    # RPM: <NAME>-<VERSION>-<RELEASE>.<ARCH>.rpm
    proc = shell(f"{dnf(repo)} repoquery --qf '%{{NAME}} %{{VERSION}} %{{RELEASE}} %{{ARCH}}'", True)
    pkgs = {}
    for line in as_lines(proc.stdout):
        tmp = line.split()
        assert len(tmp) == 4
        id = f"{tmp[0]}.{tmp[3]}"
        pkgs[id] = {"id": id, "name": tmp[0], "version": tmp[1], "release": tmp[2], "arch": tmp[3]}
    return pkgs

def depends_of(repo, pkgs):
    # include depends, enhances, recommends, suggests, supplements
    proc = shell(f"{dnf(repo)} repoquery --depends --resolve --qf %{{NAME}}.%{{ARCH}} {pkgs}", True)
    return set(as_lines(proc.stdout))

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument('-r', '--repo', help='local repo path')
    parser.add_argument('-i', '--installed', action='store_true', help='get installed packages')
    args = parser.parse_args()

    this_dir = os.path.abspath(os.path.dirname(__file__))
    os.chdir(this_dir)
    try:
        if args.installed:
            for pkg in sorted(installed_pkgs()):
                print(pkg, flush=True)
        else:
            if args.repo and not (Path(args.repo) / "Packages").is_dir():
                print(f'"{args.repo}" is not a repo path\n', file=sys.stderr)
                parser.print_help(sys.stderr)
                sys.exit(1)
            pkgs = pkgs_of_repo(args.repo)
            for n in sorted(pkgs.keys()):
                pkg = pkgs[n]
                print(f"{n} : {pkg['name']} {pkg['version']} {pkg['release']} {pkg['arch']}", flush=True)
                print(f"{n} -> {' '.join(sorted(depends_of(args.repo, n)))}")
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception:
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

