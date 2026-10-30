"""Create a PRIVATE repository using the user's locally authenticated gh CLI.

Never asks for a token in chat or writes one to a source file. The remote is only
created when the user explicitly runs this script. Uses argv, never shell=True.
"""
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
if not shutil.which("gh") or not shutil.which("git"):
    sys.exit("Instala Git y GitHub CLI desde git-scm.com y cli.github.com. Después ejecuta: gh auth login")
def run(args):
    return subprocess.run(args, cwd=root, check=True)
try:
    run(["gh", "auth", "status"])
    if not (root/".git").exists():
        run(["git", "init", "-b", "main"])
        run(["git", "add", "."])
        run(["git", "commit", "-m", "Crear Estudio Multicanal"])
    existing = subprocess.run(["git", "remote", "get-url", "origin"], cwd=root, capture_output=True)
    if existing.returncode == 0:
        sys.exit("Este proyecto ya tiene un repositorio remoto. Usa git push cuando quieras subir cambios.")
    run(["gh", "repo", "create", "estudio-multicanal", "--private", "--source", str(root), "--remote", "origin", "--push",
         "--description", "Producción de reels y videos largos con APIs, proyectos persistentes y montaje local"])
except subprocess.CalledProcessError:
    sys.exit("No se pudo crear el repositorio. Revisa el acceso a GitHub, el nombre y la configuración de Git.")
