# Importador de Test Cases a Azure DevOps

Script genérico para cargar casos de prueba desde un Excel a un Test Plan / Test Suite de Azure DevOps, creando un Work Item de tipo **Test Case** por cada fila.

## Estructura del proyecto

El script está separado en módulos por responsabilidad. Los 4 archivos `.py` tienen que estar siempre juntos en la misma carpeta (uno importa a los otros); no hace falta abrirlos para usar el script, alcanza con `importador_azure.py`:

| Archivo | Responsabilidad |
|---|---|
| `importador_azure.py` | Punto de entrada. Orquesta el flujo completo (`main()`). Es el único que se ejecuta directamente. |
| `config.py` | Carga y valida la configuración desde `.env`, y resuelve el PAT. |
| `azure_devops_client.py` | Toda la comunicación con la API REST de Azure DevOps (`AzureDevOpsClient`). |
| `excel_reader.py` | Lectura y validación del Excel, y armado del XML de steps para el Test Case. |

A esto se suman `requirements.txt` (dependencias), `.env.example` (plantilla de configuración), `.gitignore` y este `README.md`.

## Antes de empezar: cómo conseguir los datos de Azure DevOps

Para completar tu archivo `.env` necesitás estos datos: la organización, el proyecto, el Test Plan/Suite destino y un Personal Access Token (PAT). Así se consigue cada uno.

### 1. Organización y proyecto (`AZDO_URL` y `PROJECT`)

- Entrá a Azure DevOps con tu usuario. La URL de tu organización tiene la forma `https://dev.azure.com/tu-organizacion` (Azure DevOps Services) o `https://tu-servidor/tu-coleccion` (Azure DevOps Server on-premise). Eso es `AZDO_URL` (sin la barra final).
- El nombre del proyecto aparece en la barra superior al entrar a un proyecto, y también en la URL: `https://dev.azure.com/tu-organizacion/NOMBRE_DEL_PROYECTO`. Eso es `PROJECT` — respetá mayúsculas, minúsculas y espacios exactos.

### 2. Test Plan y Test Suite (`PLAN_ID`, `SUITE_ID`, `TEST_PLAN_NAME`)

1. Dentro del proyecto, andá al menú lateral izquierdo → **Test Plans**.
2. Si ya existe el Test Plan donde querés cargar los casos, abrilo. Si no existe, creá uno con **+ New Test Plan** y agregá una Test Suite dentro (con el botón **+** al lado del árbol de suites, a la izquierda).
3. Con el Test Plan abierto y la Test Suite destino seleccionada en el árbol de la izquierda, mirá la URL del navegador: vas a ver algo como `.../_testPlans/execute?planId=65547&suiteId=65548`.
   - El número de `planId` es tu `PLAN_ID`.
   - El número de `suiteId` es tu `SUITE_ID`.
4. El título que aparece arriba del Test Plan es tu `TEST_PLAN_NAME` (solo se usa en los logs, no afecta la carga).

### 3. Personal Access Token (PAT)

1. En Azure DevOps, hacé clic en el ícono de usuario/engranaje (arriba a la derecha) y elegí **Personal access tokens**.
2. Hacé clic en **+ New Token**.
3. Completá:
   - **Name**: un nombre descriptivo (ej. "Carga de Test Cases").
   - **Organization**: la organización donde vas a cargar los casos.
   - **Expiration**: una fecha de vencimiento razonable (evitá dejarlo sin vencimiento).
4. En **Scopes**, elegí "Custom defined" y activá:
   - **Work Items**: Read & Write
   - **Test Management**: Read & Write
5. Hacé clic en **Create**. Azure DevOps muestra el token una sola vez: copialo y guardalo en un lugar seguro (un gestor de contraseñas) porque no se puede volver a ver.
6. Nunca lo pegues en el código, en el Excel ni lo compartas por chat o mail. Poné el valor en tu `.env` (variable `AZDO_PAT`) o dejalo vacío para que el script te lo pida por consola cada vez (ver "Autenticación (PAT)" más abajo). Si un PAT quedó expuesto por error (pegado en un chat, un commit, etc.), revocalo en esta misma pantalla y generá uno nuevo.

### 4. El Excel

Completá la plantilla que se distribuye junto con este script, o armá uno propio con las mismas columnas (ver "Formato del Excel" más abajo).

## Requisitos

```
pip install -r requirements.txt
```

Instala `pandas`, `requests`, `openpyxl` y `python-dotenv` (versiones mínimas listadas en `requirements.txt`).

## Configuración

El script **no se edita** para usarlo: toda la configuración de tu organización/proyecto vive en un archivo `.env` separado, que nunca se comparte ni se sube a un repositorio (`.gitignore` ya lo excluye).

1. Copiá `.env.example` a `.env` (mismo directorio que el script).
2. Completá cada variable en `.env`:

| Variable | Qué va ahí |
|---|---|
| `AZDO_URL` | URL base de tu organización de Azure DevOps.<br>Azure DevOps Services: `https://dev.azure.com/TU_ORGANIZACION`<br>Azure DevOps Server (on-premise): `https://TU_SERVIDOR/TU_COLECCION` |
| `PROJECT` | Nombre del proyecto de Azure DevOps. |
| `TEST_PLAN_NAME` | Nombre del Test Plan. Solo se usa para mostrarlo en los logs, no afecta la carga. |
| `PLAN_ID` / `SUITE_ID` | IDs del Test Plan y la Test Suite destino (ver "Antes de empezar" más arriba). |
| `EXCEL_FILE` | Ruta completa al Excel con los casos de prueba. |
| `EXCEL_SHEET_NAME` | Nombre de la hoja del Excel que contiene los casos de prueba (por defecto `Casos de prueba`). |
| `SOLO_PRIMER_CASO` | `false` procesa todos los casos del Excel. `true` procesa solo el primero — útil para probar la configuración antes de correr todo. |
| `API_VERSION` | Versión de la API REST de Azure DevOps (por defecto `5.1`). |
| `AZDO_PAT` | Opcional — ver "Autenticación (PAT)" abajo. |

`config.py` carga `.env` automáticamente al arrancar (con `python-dotenv`) y no continúa hasta que `AZDO_URL`, `PROJECT`, `PLAN_ID`, `SUITE_ID` y `EXCEL_FILE` estén completos: si falta alguno, corta y te dice cuál.

## Autenticación (PAT)

El script nunca guarda el Personal Access Token en el código. Lo toma en este orden:

1. De la variable `AZDO_PAT` en tu `.env`, si la completaste.
2. Si no está definida (o la dejaste vacía), la pide de forma interactiva por consola con un campo oculto (no queda visible en pantalla ni guardada en ningún archivo).

Dejarla vacía en `.env` y tipearla cada vez es lo más seguro cuando varias personas comparten la misma carpeta o máquina.

El PAT necesita estos permisos en Azure DevOps:

- **Work Items**: Read & Write
- **Test Management**: Read & Write

## Formato del Excel

El Excel debe tener una hoja con el nombre configurado en `EXCEL_SHEET_NAME` y, como mínimo, estas columnas (nombres exactos):

| Columna | Contenido |
|---|---|
| `ID caso de prueba` | Identificador único del caso dentro del Excel (ej: `CP-001`). No puede repetirse ni quedar vacío. Se usa como tag del Test Case y para detectar si el caso ya fue cargado antes. |
| `Módulo` | Módulo o área funcional del caso. |
| `Funcionalidad` | Funcionalidad puntual dentro del módulo. |
| `Nombre del caso de prueba` | Título corto del caso. Junto con el ID arma el título del Work Item: `[ID] Nombre`. |
| `Descripción del caso de prueba` | Objetivo del caso: qué se quiere validar. |
| `Instrucciones de ejecución` | Los pasos a ejecutar, uno por línea dentro de la misma celda (Alt+Enter para saltar de línea). La numeración inicial (`1.`, `2)`, etc.) es opcional: se quita automáticamente. |
| `Resultado esperado` | El resultado esperado de cada paso, en el mismo orden que `Instrucciones de ejecución` (también una línea por paso). La línea 1 es el resultado del paso 1, la línea 2 del paso 2, etc. Si hay menos líneas que pasos, los pasos restantes quedan sin resultado esperado en Azure DevOps (no se pierden pasos). |

Se pueden agregar columnas propias a la derecha de las siete requeridas: el script las ignora.

Una plantilla lista para usar (con hoja de instrucciones y fila de ejemplo) se distribuye junto con este script.

## Cómo se evita duplicar Test Cases

El script **solo reutiliza** un Test Case existente si ya está agregado a la misma suite destino (`PLAN_ID` / `SUITE_ID` configurados). Esto cubre el caso de que una corrida se corte a mitad de camino y se vuelva a ejecutar. Nunca busca ni reutiliza Test Cases de otras suites o Test Plans.

Esto es intencional: si buscara un Test Case existente por su ID/tag en todo el proyecto (sin filtrar por Suite/Plan), podría encontrar y reutilizar por error un Test Case que pertenece a otro Test Plan/Suite (por ejemplo, de otro proyecto o de una etapa anterior). Eso haría que el "nuevo" caso comparta Work Item ID, resultados y evidencias ya cargadas con el caso viejo — algo difícil de detectar después.

**Antes de correr el script por primera vez en una suite**, confirmá que la suite destino esté vacía, o que los Test Cases que ya tiene sean realmente los que querés reutilizar.

## Cómo ejecutarlo

Necesitás los 4 archivos `.py` (`importador_azure.py`, `config.py`, `azure_devops_client.py`, `excel_reader.py`) juntos en la misma carpeta, más `requirements.txt` y `.env.example`:

```
pip install -r requirements.txt
cp .env.example .env      # completar los valores en .env
python importador_azure.py
```

El script, en orden:

1. Carga la configuración desde `.env` y valida que no falte nada.
2. Valida el PAT y que el proyecto exista.
3. Valida que `PLAN_ID` sea un Test Plan y `SUITE_ID` una Test Suite.
4. Lee el Excel y valida las columnas requeridas (sin IDs vacíos ni duplicados).
5. Revisa qué casos ya están en la suite destino, para no duplicarlos.
6. Por cada caso: crea el Test Case (o reutiliza el existente en esa suite) y lo agrega a la suite.
7. Imprime un resumen final con creados, reutilizados, agregados y errores, y un detalle fila por fila.