"""
Carga y valida la configuracion del importador desde variables de
entorno (.env). Ver README.md para el detalle de cada variable.
"""

import getpass
import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Configuracion:
    azdo_url: str
    project: str
    test_plan_name: str
    plan_id: int
    suite_id: int
    excel_file: str
    excel_sheet_name: str
    solo_primer_caso: bool
    api_version: str


def _env_int(nombre):
    valor = os.environ.get(nombre, "").strip()
    try:
        return int(valor)
    except ValueError:
        return 0


def _env_bool(nombre, default=False):
    valor = os.environ.get(nombre, "").strip().lower()
    if not valor:
        return default
    return valor in ("1", "true", "si", "sí", "yes")


def cargar_configuracion():
    """
    Carga las variables desde .env, arma la Configuracion y valida que
    las obligatorias esten completas. Si falta alguna, imprime el
    detalle y corta la ejecucion.
    """
    load_dotenv()

    cfg = Configuracion(
        azdo_url=os.environ.get("AZDO_URL", "").strip().rstrip("/"),
        project=os.environ.get("PROJECT", "").strip(),
        test_plan_name=os.environ.get("TEST_PLAN_NAME", "").strip(),
        plan_id=_env_int("PLAN_ID"),
        suite_id=_env_int("SUITE_ID"),
        excel_file=os.environ.get("EXCEL_FILE", "").strip(),
        excel_sheet_name=os.environ.get("EXCEL_SHEET_NAME", "Casos de prueba").strip(),
        solo_primer_caso=_env_bool("SOLO_PRIMER_CASO", default=False),
        api_version=os.environ.get("API_VERSION", "5.1").strip(),
    )

    faltantes = []
    if not cfg.azdo_url:
        faltantes.append("AZDO_URL")
    if not cfg.project:
        faltantes.append("PROJECT")
    if not cfg.plan_id:
        faltantes.append("PLAN_ID")
    if not cfg.suite_id:
        faltantes.append("SUITE_ID")
    if not cfg.excel_file:
        faltantes.append("EXCEL_FILE")

    if faltantes:
        print("ERROR: Faltan variables de configuración en tu archivo .env:")
        for nombre in faltantes:
            print(f"- {nombre}")
        print()
        print(
            "Copiá .env.example a .env y completá los valores "
            "(ver README.md, sección \"Antes de empezar\")."
        )
        sys.exit(1)

    return cfg


def obtener_pat():
    """
    Resuelve el Personal Access Token: primero desde la variable de
    entorno AZDO_PAT (o .env); si no esta definida, lo pide por
    consola de forma oculta.
    """
    pat = os.environ.get("AZDO_PAT", "").strip()
    if not pat:
        pat = getpass.getpass(
            "Pega tu Personal Access Token (PAT) de Azure DevOps: "
        ).strip()

    if not pat:
        print("ERROR: No se ingreso ningun PAT.")
        print()
        print("Permisos requeridos:")
        print("- Work Items: Read & Write")
        print("- Test Management: Read & Write")
        sys.exit(1)

    return pat