"""Comprobaciones del entorno de feature/setup (D-12 a D-17, D-63, D-69).

Sin simulaciones: usan PostgreSQL real (`docker compose up -d --wait`), `uv` y `latexmk`.
"""

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

RAIZ = Path(__file__).parent.parent
# Credenciales solo de desarrollo, las de docker-compose.yml.
DSN = os.environ.get("DATABASE_URL", "postgresql://tfm:tfm@127.0.0.1:55432/tfm")


@pytest.fixture
def conexion() -> Iterator[psycopg.Connection]:
    # Tablas temporales: desaparecen con la conexión y no tocan nada de la base de datos.
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute(
            "CREATE TEMP TABLE sesiones (id int PRIMARY KEY, version int NOT NULL)"
        )
        c.execute("CREATE TEMP TABLE registro (id int PRIMARY KEY)")
        yield c


def test_uv_sync_deja_un_entorno_limpio_e_importable(tmp_path: Path) -> None:
    """D-12, D-13, D-17: entorno nuevo desde uv.lock, con Python 3.14 y A2A 1.0."""
    venv = tmp_path / "venv"
    subprocess.run(
        ["uv", "sync", "--locked"],
        cwd=RAIZ,
        env={**os.environ, "UV_PROJECT_ENVIRONMENT": str(venv)},
        check=True,
    )
    comprobacion = (
        "import sys, orquestador, psycopg\n"
        "from a2a.utils.constants import PROTOCOL_VERSION_CURRENT\n"
        "assert sys.version_info[:2] == (3, 14)\n"
        "assert PROTOCOL_VERSION_CURRENT == '1.0'\n"
    )
    resultado = subprocess.run(
        [venv / "bin" / "python", "-c", comprobacion],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert resultado.returncode == 0, resultado.stderr


def test_conexion_a_la_version_fijada_de_postgresql(
    conexion: psycopg.Connection,
) -> None:
    """D-69: la versión fijada en docker-compose.yml."""
    fila = conexion.execute("SHOW server_version").fetchone()
    assert fila is not None
    assert fila[0].startswith("18.6")


def test_transaccion_entre_dos_tablas_se_deshace_entera(
    conexion: psycopg.Connection,
) -> None:
    """D-63, D-69: un fallo en la segunda tabla deshace también la primera."""
    with pytest.raises(psycopg.errors.UniqueViolation):
        with conexion.transaction():
            conexion.execute("INSERT INTO sesiones VALUES (1, 1)")
            conexion.execute("INSERT INTO registro VALUES (1)")
            conexion.execute("INSERT INTO registro VALUES (1)")

    fila = conexion.execute(
        "SELECT (SELECT count(*) FROM sesiones) + (SELECT count(*) FROM registro)"
    ).fetchone()
    assert fila == (0,)


def test_escritura_condicional_rechaza_la_segunda_con_la_misma_version(
    conexion: psycopg.Connection,
) -> None:
    """D-63: la segunda escritura con la misma versión no afecta a ninguna fila."""
    conexion.execute("INSERT INTO sesiones VALUES (1, 1)")
    actualizar = "UPDATE sesiones SET version = 2 WHERE id = 1 AND version = 1"

    assert conexion.execute(actualizar).rowcount == 1
    assert conexion.execute(actualizar).rowcount == 0


def test_lectura_del_reloj_del_servidor(conexion: psycopg.Connection) -> None:
    """D-69: el servidor da la hora con zona horaria y su reloj avanza."""
    primera = conexion.execute("SELECT clock_timestamp()").fetchone()
    segunda = conexion.execute("SELECT clock_timestamp()").fetchone()
    assert primera is not None and segunda is not None
    assert primera[0].tzinfo is not None
    assert segunda[0] > primera[0]


@pytest.mark.parametrize("documento", ["manual", "tecnica"])
def test_documento_latex_compila(documento: str, tmp_path: Path) -> None:
    """proceso.md §9: los dos documentos compilan con latexmk y LuaLaTeX."""
    resultado = subprocess.run(
        [
            "latexmk",
            "-lualatex",
            "-halt-on-error",
            "-interaction=nonstopmode",
            f"-outdir={tmp_path}",
            f"{documento}.tex",
        ],
        cwd=RAIZ / "docs" / "latex" / documento,
        capture_output=True,
        text=True,
    )
    assert resultado.returncode == 0, resultado.stdout[-2000:]
    assert (tmp_path / f"{documento}.pdf").exists()
