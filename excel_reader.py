"""
Lectura del Excel de casos de prueba y armado del XML de steps que
espera Azure DevOps (campo Microsoft.VSTS.TCM.Steps).
"""

import re
import sys
from html import escape

import pandas as pd

COLUMNAS_REQUERIDAS = [
    "ID caso de prueba",
    "Módulo",
    "Funcionalidad",
    "Nombre del caso de prueba",
    "Descripción del caso de prueba",
    "Instrucciones de ejecución",
    "Resultado esperado",
]


def limpiar_valor(valor):
    """
    Convierte una celda del Excel en texto limpio.
    Los valores vacíos se convierten en cadena vacía.
    """
    if pd.isna(valor):
        return ""
    return str(valor).strip()


def quitar_numeracion(texto):
    """
    Quita la numeración inicial de cada instrucción.
    Ejemplos:
    1. Acceder al módulo -> Acceder al módulo
    2) Seleccionar       -> Seleccionar
    """
    return re.sub(r"^\s*\d+\s*[\.\)\-:]\s*", "", texto).strip()


def construir_steps_xml(instrucciones, resultados_esperados):
    """
    Arma un ActionStep por cada línea de 'Instrucciones de ejecución',
    emparejada por posición con la línea correspondiente de
    'Resultado esperado' (paso 1 con paso 1, paso 2 con paso 2, etc.).
    """
    lineas_accion = [
        quitar_numeracion(linea)
        for linea in instrucciones.splitlines()
        if linea.strip()
    ]
    lineas_resultado = [
        quitar_numeracion(linea)
        for linea in resultados_esperados.splitlines()
        if linea.strip()
    ]
    if not lineas_accion:
        lineas_accion = ["Ejecutar el caso de prueba según la descripción."]
    # Completar la lista más corta con celdas vacías para poder
    # emparejar acción y resultado esperado paso a paso.
    while len(lineas_resultado) < len(lineas_accion):
        lineas_resultado.append("")
    ultimo_step_id = len(lineas_accion) + 1
    partes = [f'<steps id="0" last="{ultimo_step_id}">']
    for step_id, (accion_texto, resultado_texto) in enumerate(
        zip(lineas_accion, lineas_resultado),
        start=2,
    ):
        accion = escape(accion_texto)
        resultado = escape(resultado_texto)
        partes.append(
            f'<step id="{step_id}" type="ActionStep">'
            '<parameterizedString isformatted="true">'
            f'{accion}'
            '</parameterizedString>'
            '<parameterizedString isformatted="true">'
            f'{resultado}'
            '</parameterizedString>'
            '<description/>'
            '</step>'
        )
    partes.append("</steps>")
    return "".join(partes)


def cargar_excel(excel_file, sheet_name, solo_primer_caso):
    """
    Lee sheet_name del Excel y conserva únicamente las columnas
    indicadas en COLUMNAS_REQUERIDAS.
    """
    try:
        df = pd.read_excel(
            excel_file,
            sheet_name=sheet_name,
            engine="openpyxl",
            dtype=str,
        )
    except FileNotFoundError:
        print()
        print("ERROR: No se encontró el Excel:")
        print(excel_file)
        sys.exit(1)
    except ValueError as error:
        print()
        print("ERROR leyendo la hoja del Excel:")
        print(error)
        sys.exit(1)
    except Exception as error:
        print()
        print("ERROR leyendo el Excel:")
        print(error)
        sys.exit(1)

    print()
    print("Columnas encontradas:")
    print(df.columns.tolist())
    columnas_faltantes = [
        columna for columna in COLUMNAS_REQUERIDAS if columna not in df.columns
    ]
    if columnas_faltantes:
        print()
        print("ERROR: Faltan columnas requeridas:")
        for columna in columnas_faltantes:
            print(f"- {columna}")
        sys.exit(1)

    # Utilizar solamente las columnas requeridas.
    df = df[COLUMNAS_REQUERIDAS].copy()
    # Eliminar filas sin ID de caso de prueba.
    df = df[df["ID caso de prueba"].notna()].copy()
    df["ID caso de prueba"] = df["ID caso de prueba"].astype(str).str.strip()
    df = df[df["ID caso de prueba"] != ""].copy()

    # Evitar procesar IDs duplicados dentro del mismo Excel.
    duplicados = df[df["ID caso de prueba"].duplicated(keep=False)]
    if not duplicados.empty:
        print()
        print("ERROR: Hay IDs duplicados en el Excel:")
        for tc_id in sorted(duplicados["ID caso de prueba"].unique()):
            print(f"- {tc_id}")
        sys.exit(1)

    if solo_primer_caso:
        df = df.head(1)
    return df