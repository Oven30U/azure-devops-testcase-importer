"""
Importador generico de Test Cases desde Excel a Azure DevOps.

Orquesta el flujo completo usando config.py (configuracion desde
.env), azure_devops_client.py (API de Azure DevOps) y excel_reader.py
(lectura del Excel y armado de los steps). Ver README.md para
instrucciones de uso, configuracion, formato del Excel y el
comportamiento de reutilizacion de Test Cases.
"""

# IMPORTANTE: esto tiene que ir antes de cualquier import que termine
# usando `requests`/`urllib3` (azure_devops_client, por ejemplo), para
# que las conexiones HTTPS usen el almacen de certificados de Windows
# (donde ya esta confiada la CA interna de Deloitte) en vez del bundle
# de certifi que trae Python por defecto. Soluciona el
# SSLCertVerificationError: unable to get local issuer certificate.
import truststore

truststore.inject_into_ssl()

from azure_devops_client import AzureDevOpsClient
from config import cargar_configuracion, obtener_pat
from excel_reader import (
    COLUMNAS_REQUERIDAS,
    cargar_excel,
    construir_steps_xml,
    limpiar_valor,
)


def main():
    print("=" * 70)
    print("IMPORTACION DE TEST CASES A AZURE DEVOPS")
    print("=" * 70)

    # 1. Cargar y validar configuracion (.env) y PAT.
    cfg = cargar_configuracion()
    pat = obtener_pat()
    client = AzureDevOpsClient(cfg.azdo_url, cfg.project, cfg.api_version, pat)

    # 2. Validar PAT y proyecto.
    client.validar_conexion()

    # 3. Validar IDs configurados.
    client.validar_plan_y_suite(cfg.plan_id, cfg.suite_id)

    # 4. Leer Excel.
    df = cargar_excel(cfg.excel_file, cfg.excel_sheet_name, cfg.solo_primer_caso)

    # 5. Ver qué casos ya están agregados a la suite destino, para no
    #    duplicarlos si esta corrida se repite. No mira ninguna otra
    #    suite ni Test Plan.
    test_cases_en_suite = client.obtener_test_cases_de_esta_suite(
        cfg.plan_id, cfg.suite_id
    )

    print()
    print("=" * 70)
    print("CONFIGURACION")
    print("=" * 70)
    print(f"Proyecto: {cfg.project}")
    print(f"Test Plan: {cfg.test_plan_name}")
    print(f"Plan ID: {cfg.plan_id}")
    print(f"Suite ID: {cfg.suite_id}")
    print(f"Casos a procesar: {len(df)}")
    print(f"Solo primer caso: {cfg.solo_primer_caso}")
    print(
        "Test Cases ya presentes en la suite destino: "
        f"{len(test_cases_en_suite)}"
    )
    if test_cases_en_suite:
        print(
            "-> Estos se van a reutilizar (mismo Work Item) para no "
            "duplicarlos. Si la suite debería estar vacía y ves "
            "casos acá, pará y revisalos primero en Azure DevOps."
        )
    print("=" * 70)

    creados = 0
    reutilizados = 0
    agregados = 0
    errores = 0
    resultados = []

    for _, row in df.iterrows():
        datos = {
            columna: limpiar_valor(row[columna]) for columna in COLUMNAS_REQUERIDAS
        }
        tc_id = datos["ID caso de prueba"]
        nombre = datos["Nombre del caso de prueba"]

        print()
        print("-" * 70)
        print(f"Procesando: {tc_id} - {nombre}")

        # Solo se reutiliza si el caso ya está agregado a la suite
        # destino configurada arriba. Nunca se reutiliza un Test Case
        # de otra suite/Test Plan.
        work_item_id = test_cases_en_suite.get(tc_id)
        origen = "ya estaba en esta suite" if work_item_id else None

        if work_item_id is not None:
            if not client.validar_test_case_existente(tc_id, work_item_id):
                errores += 1
                resultados.append({
                    "id_caso": tc_id,
                    "work_item_id": work_item_id,
                    "resultado": "ERROR",
                    "detalle": "Work Item existente inválido",
                })
                continue
            reutilizados += 1
            print(
                f"REUTILIZANDO: {tc_id} | "
                f"Work Item ID: {work_item_id} | "
                f"Origen: {origen}"
            )
        else:
            steps_xml = construir_steps_xml(
                datos["Instrucciones de ejecución"],
                datos["Resultado esperado"],
            )
            work_item_id = client.crear_test_case(datos, steps_xml)
            if work_item_id is None:
                errores += 1
                resultados.append({
                    "id_caso": tc_id,
                    "work_item_id": "",
                    "resultado": "ERROR",
                    "detalle": "No se pudo crear",
                })
                continue
            creados += 1

        agregado = client.agregar_test_case_a_suite(
            cfg.plan_id, cfg.suite_id, work_item_id, tc_id
        )
        if agregado:
            agregados += 1
            resultados.append({
                "id_caso": tc_id,
                "work_item_id": work_item_id,
                "resultado": "OK",
                "detalle": (
                    "Creado y agregado"
                    if origen is None
                    else "Reutilizado (ya estaba en esta suite) y agregado"
                ),
            })
        else:
            errores += 1
            resultados.append({
                "id_caso": tc_id,
                "work_item_id": work_item_id,
                "resultado": "ERROR",
                "detalle": "No se pudo agregar a la suite",
            })

    print()
    print("=" * 70)
    print("PROCESO FINALIZADO")
    print("=" * 70)
    print(f"Test Cases nuevos creados: {creados}")
    print(f"Test Cases reutilizados (ya estaban en esta suite): {reutilizados}")
    print(f"Test Cases agregados a la suite: {agregados}")
    print(f"Errores: {errores}")
    print("=" * 70)
    print()
    print("DETALLE DE RESULTADOS")
    print("=" * 70)
    for resultado in resultados:
        print(
            f"{resultado['id_caso']} | "
            f"Work Item: {resultado['work_item_id']} | "
            f"{resultado['resultado']} | "
            f"{resultado['detalle']}"
        )


if __name__ == "__main__":
    main()