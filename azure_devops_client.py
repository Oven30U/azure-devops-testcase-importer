"""
Cliente HTTP minimo para las operaciones de Azure DevOps que usa el
importador: validar conexion, consultar Work Items, y crear/agregar
Test Cases a una Test Suite.
"""

import re
import sys
from html import escape
from urllib.parse import quote

import requests
from requests.auth import HTTPBasicAuth


def _obtener_mensaje_error(response):
    """
    Obtiene un mensaje entendible desde la respuesta devuelta por
    Azure DevOps.
    """
    try:
        contenido = response.json()
        if isinstance(contenido, dict):
            return contenido.get("message", str(contenido))
        return str(contenido)
    except ValueError:
        return response.text


def _mostrar_error(response, operacion):
    """
    Muestra la información completa de un error.
    """
    print()
    print(f"ERROR DURANTE: {operacion}")
    print(f"HTTP STATUS: {response.status_code}")
    print(f"URL: {response.url}")
    print(f"MENSAJE: {_obtener_mensaje_error(response)}")
    print()


class AzureDevOpsClient:
    """
    Encapsula la sesión HTTP y las llamadas a la API REST de Azure
    DevOps que usa el importador.
    """

    def __init__(self, azdo_url, project, api_version, pat):
        self.azdo_url = azdo_url
        self.project = project
        self.project_encoded = quote(project, safe="")
        self.api_version = api_version
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth("", pat)
        self.session.headers.update({"Accept": "application/json"})

    def validar_conexion(self):
        """
        Valida el PAT y confirma que el proyecto exista.
        """
        url = (
            f"{self.azdo_url}/_apis/projects/"
            f"{self.project_encoded}"
            f"?api-version={self.api_version}"
        )
        response = self.session.get(url, timeout=60)
        if response.status_code != 200:
            _mostrar_error(response, "validar el PAT y el proyecto")
            if response.status_code == 401:
                print(
                    "El PAT es inválido, venció o no tiene "
                    "los permisos necesarios."
                )
            sys.exit(1)
        proyecto = response.json()
        print("Conexión correcta.")
        print(f"Proyecto encontrado: {proyecto.get('name', self.project)}")

    def obtener_work_item(self, work_item_id):
        """
        Obtiene un Work Item por ID.
        """
        url = (
            f"{self.azdo_url}/{self.project_encoded}"
            f"/_apis/wit/workitems/{work_item_id}"
            f"?api-version={self.api_version}"
        )
        response = self.session.get(url, timeout=60)
        if response.status_code != 200:
            _mostrar_error(response, f"consultar Work Item {work_item_id}")
            return None
        return response.json()

    def validar_plan_y_suite(self, plan_id, suite_id):
        """
        Valida que plan_id corresponda a un Test Plan y suite_id a una
        Test Suite.
        """
        plan = self.obtener_work_item(plan_id)
        if plan is None:
            sys.exit(1)
        plan_fields = plan.get("fields", {})
        plan_type = str(plan_fields.get("System.WorkItemType", "")).strip()
        plan_title = str(plan_fields.get("System.Title", "")).strip()
        print()
        print("Test Plan encontrado:")
        print(f"Plan ID: {plan_id}")
        print(f"Tipo: {plan_type}")
        print(f"Título: {plan_title}")
        if plan_type.casefold() != "test plan":
            print()
            print(f"ERROR: El Work Item {plan_id} no es de tipo Test Plan.")
            sys.exit(1)

        suite = self.obtener_work_item(suite_id)
        if suite is None:
            sys.exit(1)
        suite_fields = suite.get("fields", {})
        suite_type = str(suite_fields.get("System.WorkItemType", "")).strip()
        suite_title = str(suite_fields.get("System.Title", "")).strip()
        print()
        print("Test Suite encontrada:")
        print(f"Suite ID: {suite_id}")
        print(f"Tipo: {suite_type}")
        print(f"Título: {suite_title}")
        if suite_type.casefold() != "test suite":
            print()
            print(f"ERROR: El Work Item {suite_id} no es de tipo Test Suite.")
            sys.exit(1)

    def obtener_test_cases_de_esta_suite(self, plan_id, suite_id):
        """
        Devuelve un diccionario {ID caso de prueba: Work Item ID} con
        los Test Cases que ya están agregados a plan_id/suite_id. No
        mira otras suites ni otros Test Plans (ver README.md).
        """
        url = (
            f"{self.azdo_url}/{self.project_encoded}"
            f"/_apis/test/Plans/{plan_id}"
            f"/suites/{suite_id}/testcases"
            f"?api-version={self.api_version}"
        )
        response = self.session.get(url, timeout=60)
        if response.status_code != 200:
            _mostrar_error(
                response,
                "consultar los Test Cases ya agregados a la suite destino",
            )
            return {}
        encontrados = {}
        for item in response.json().get("value", []):
            test_case = item.get("testCase") or {}
            work_item = test_case.get("workItem") or {}
            wi_id = work_item.get("id")
            nombre = str(work_item.get("name", ""))
            coincidencia = re.match(r"^\[([^\]]+)\]", nombre)
            if wi_id and coincidencia:
                tc_id = coincidencia.group(1).strip()
                encontrados[tc_id] = int(wi_id)
        return encontrados

    def validar_test_case_existente(self, tc_id, work_item_id):
        """
        Valida que un Work Item existente sea de tipo Test Case.
        """
        work_item = self.obtener_work_item(work_item_id)
        if work_item is None:
            return False
        fields = work_item.get("fields", {})
        tipo = str(fields.get("System.WorkItemType", "")).strip()
        titulo = str(fields.get("System.Title", "")).strip()
        print(f"Work Item existente para {tc_id}: ID {work_item_id}")
        print(f"Tipo: {tipo}")
        print(f"Título: {titulo}")
        if tipo.casefold() != "test case":
            print(f"ERROR: El Work Item {work_item_id} no es un Test Case.")
            return False
        return True

    def crear_test_case(self, datos, steps_xml):
        """
        Crea un Work Item de tipo Test Case. Cada llamada crea un Work
        Item NUEVO en Azure DevOps (ID nuevo asignado por AzDO), sin
        resultados ni evidencias previas.
        """
        tc_id = datos["ID caso de prueba"]
        modulo = datos["Módulo"]
        funcionalidad = datos["Funcionalidad"]
        nombre = datos["Nombre del caso de prueba"]
        descripcion = datos["Descripción del caso de prueba"]
        titulo = f"[{tc_id}] {nombre}"
        tags = "; ".join(v for v in [tc_id, modulo, funcionalidad] if v)

        body = [
            {"op": "add", "path": "/fields/System.Title", "value": titulo},
            {
                "op": "add",
                "path": "/fields/System.Description",
                "value": escape(descripcion),
            },
            {"op": "add", "path": "/fields/System.Tags", "value": tags},
            {
                "op": "add",
                "path": "/fields/Microsoft.VSTS.TCM.Steps",
                "value": steps_xml,
            },
        ]
        url = (
            f"{self.azdo_url}/{self.project_encoded}"
            "/_apis/wit/workitems/$Test%20Case"
            f"?api-version={self.api_version}"
        )
        response = self.session.post(
            url,
            json=body,
            headers={"Content-Type": "application/json-patch+json"},
            timeout=60,
        )
        if response.status_code not in (200, 201):
            _mostrar_error(response, f"crear el Test Case {tc_id}")
            return None
        resultado = response.json()
        work_item_id = int(resultado["id"])
        print(f"CREADO (Work Item nuevo): {tc_id} | Work Item ID: {work_item_id}")
        return work_item_id

    def agregar_test_case_a_suite(self, plan_id, suite_id, work_item_id, tc_id):
        """
        Agrega el Test Case al Plan/Suite destino.
        """
        url = (
            f"{self.azdo_url}/{self.project_encoded}"
            f"/_apis/test/Plans/{plan_id}"
            f"/suites/{suite_id}"
            f"/testcases/{work_item_id}"
            f"?api-version={self.api_version}"
        )
        response = self.session.post(
            url,
            headers={"Content-Type": "application/json"},
            timeout=60,
        )
        if response.status_code not in (200, 201):
            _mostrar_error(
                response,
                (
                    f"agregar {tc_id}, Work Item {work_item_id}, "
                    f"al Plan {plan_id}, Suite {suite_id}"
                ),
            )
            return False
        print(
            f"AGREGADO A LA SUITE: {tc_id} | "
            f"Work Item ID: {work_item_id} | "
            f"Plan ID: {plan_id} | "
            f"Suite ID: {suite_id}"
        )
        return True