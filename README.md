# Proyecto de Agentes de IA Colaborativos

## Descripción
Este proyecto implementa un sistema de agentes de IA colaborativos que interactúan entre sí para desarrollar soluciones de software de manera iterativa. Los agentes incluyen:

- **SME (Subject Matter Expert)**: Genera requerimientos funcionales y verifica su implementación.
- **Architect**: Diseña soluciones técnicas basadas en los requerimientos.
- **Developer**: Implementa el código basado en el diseño del Architect.

El sistema funciona en un ciclo iterativo donde los agentes colaboran hasta que todos los requerimientos están completamente implementados.

## Requisitos Previos
- Python 3.8 o superior
- UV (gestor de paquetes y entornos virtuales para Python)
- OpenAI API Key (para acceder a los modelos de IA)

## Instalación

1. Clona el repositorio:
   ```bash
   git clone <URL_DEL_REPOSITORIO>
   cd <NOMBRE_DEL_REPOSITORIO>
   ```

2. Instala UV si aún no lo tienes:
   ```bash
   curl -sSf https://install.ultraviolet.rs | sh
   ```

3. Crea un entorno virtual e instala las dependencias con UV:
   ```bash
   uv venv
   source .venv/bin/activate  # En macOS/Linux
   .venv\Scripts\activate     # En Windows
   uv pip install -r requirements.txt
   ```

4. Configura tus API Keys:
   - Crea un archivo `.env` en la raíz del proyecto
   - Añade tus API Keys:
     ```
     OPENAI_API_KEY=tu_api_key_de_openai_aquí
     ANTHROPIC_API_KEY=tu_api_key_de_anthropic_aquí
     ```
   - Si solo vas a usar uno de los proveedores, puedes omitir la API Key del otro

5. Instala la biblioteca Anthropic (opcional, solo si vas a usar Claude):
   ```bash
   uv pip install anthropic
   ```

## Ejecución del Código
Para ejecutar la aplicación, utiliza el siguiente comando:
```bash
uv run -m src.main
```

Este comando iniciará el ciclo de desarrollo colaborativo donde los agentes trabajarán juntos para implementar los requerimientos del proyecto.

## Visualización de Outputs
Los agentes generarán archivos de salida en el directorio `src/outputs/` después de cada iteración. Los nombres de los archivos seguirán el formato:

- `sme-id-<timestamp>.txt`: Requerimientos funcionales y análisis
- `architect-id-<timestamp>.txt`: Diseños técnicos
- `developer-id-<timestamp>.txt`: Código implementado (formato texto)

Además, el agente Developer generará los archivos de código fuente en la carpeta `src/output/source_code/`, organizados en una estructura de directorios que separa el frontend y el backend. Estos archivos son completamente funcionales y listos para ser ejecutados.

## Funcionamiento
1. El SME analiza la descripción del proyecto y genera requerimientos funcionales
2. El Architect diseña una solución técnica para implementar los requerimientos
3. El Developer implementa el código basado en el diseño
4. El SME verifica si todos los requerimientos están implementados
5. Si hay requerimientos pendientes, el ciclo continúa
6. Cuando todos los requerimientos están completos, el ciclo termina

## Contribuciones
Las contribuciones son bienvenidas. Si deseas contribuir, por favor abre un issue o envía un pull request.

## Licencia
Este proyecto está bajo la Licencia MIT.
# Proyecto de Agentes de IA Colaborativos

## Descripción
Este proyecto implementa un sistema de agentes de IA colaborativos que interactúan entre sí para desarrollar soluciones de software de manera iterativa. Los agentes incluyen:

- **SME (Subject Matter Expert)**: Genera requerimientos funcionales y verifica su implementación.
- **Architect**: Diseña soluciones técnicas basadas en los requerimientos.
- **Developer**: Implementa el código basado en el diseño del Architect.

El sistema funciona en un ciclo iterativo donde los agentes colaboran hasta que todos los requerimientos están completamente implementados.

## Requisitos Previos
- Python 3.8 o superior
- UV (gestor de paquetes y entornos virtuales para Python)
- OpenAI API Key (para acceder a los modelos de IA)

## Instalación

1. Clona el repositorio:
   ```bash
   git clone <URL_DEL_REPOSITORIO>
   cd <NOMBRE_DEL_REPOSITORIO>
   ```

2. Instala UV si aún no lo tienes:
   ```bash
   curl -sSf https://install.ultraviolet.rs | sh
   ```

3. Crea un entorno virtual e instala las dependencias con UV:
   ```bash
   uv venv
   source .venv/bin/activate  # En macOS/Linux
   .venv\Scripts\activate     # En Windows
   uv pip install -r requirements.txt
   ```

4. Configura tus API Keys:
   - Crea un archivo `.env` en la raíz del proyecto
   - Añade tus API Keys:
     ```
     OPENAI_API_KEY=tu_api_key_de_openai_aquí
     ANTHROPIC_API_KEY=tu_api_key_de_anthropic_aquí
     ```
   - Si solo vas a usar uno de los proveedores, puedes omitir la API Key del otro

5. Instala la biblioteca Anthropic (opcional, solo si vas a usar Claude):
   ```bash
   uv pip install anthropic
   ```

## Ejecución del Código
Para ejecutar la aplicación, utiliza el siguiente comando:
```bash
uv run -m src.main
```

Este comando iniciará el ciclo de desarrollo colaborativo donde los agentes trabajarán juntos para implementar los requerimientos del proyecto.

## Visualización de Outputs
Los agentes generarán archivos de salida en el directorio `src/outputs/` después de cada iteración. Los nombres de los archivos seguirán el formato:

- `sme-id-<timestamp>.txt`: Requerimientos funcionales y análisis
- `architect-id-<timestamp>.txt`: Diseños técnicos
- `developer-id-<timestamp>.txt`: Código implementado (formato texto)

Además, el agente Developer generará los archivos de código fuente en la carpeta `src/output/source_code/`, organizados en una estructura de directorios que separa el frontend y el backend. Estos archivos son completamente funcionales y listos para ser ejecutados.

## Funcionamiento
1. El SME analiza la descripción del proyecto y genera requerimientos funcionales
2. El Architect diseña una solución técnica para implementar los requerimientos
3. El Developer implementa el código basado en el diseño
4. El SME verifica si todos los requerimientos están implementados
5. Si hay requerimientos pendientes, el ciclo continúa
6. Cuando todos los requerimientos están completos, el ciclo termina

## Contribuciones
Las contribuciones son bienvenidas. Si deseas contribuir, por favor abre un issue o envía un pull request.

## Licencia
Este proyecto está bajo la Licencia MIT.
