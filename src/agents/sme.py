# src/agents/sme.py
import json
import re
import os
from pathlib import Path
from typing import List, Union, Dict, Any
from src.core.messaging import Mensaje
from src.core.agent import OpenAIAssistantAgent
from src.core.config import AgentConfig
from src.core.models import FunctionalRequirement, RequirementsList


class SME(OpenAIAssistantAgent):
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.requirements_list = RequirementsList()

    def run(self, prompt_sme: str) -> RequirementsList:
        """
        Ejecuta el agente SME, procesando la descripción general del proyecto.

        Args:
            prompt_sme: Prompt para el agente SME, generalmente la descripción del proyecto.

        Returns:
            RequirementsList: Lista estructurada de requerimientos funcionales generados.
        """
        iteration_id = self._generate_iteration_id()

        # Modificamos el prompt para solicitar una respuesta estructurada
        prompt_actualizado = f"""
        {prompt_sme}

        Genera una lista completa de requerimientos funcionales basados en la descripción anterior.

        FORMATO DE RESPUESTA:
        Responde con una lista de requerimientos funcionales en formato JSON con la siguiente estructura:
        {{
            "requirements": [
                {{
                    "id": "REQ-01",
                    "description": "Descripción detallada del requerimiento",
                    "priority": "Alta|Media|Baja"
                }},
                ...
            ]
        }}

        IMPORTANTE: 
        - Cada requerimiento debe tener un ID único en formato REQ-XX (donde XX son números)
        - La descripción debe ser clara y específica
        - La prioridad debe ser Alta, Media o Baja
        - Asegúrate de que la respuesta sea un JSON válido
        """

        # Notificar inicio de generación de requerimientos
        if self._sistema_mensajeria:
            self._sistema_mensajeria.publicar(
                Mensaje(
                    emisor=self.config.name,
                    tipo="generando_requerimientos",
                    contenido=f"Generando requerimientos para: {prompt_sme[:100]}...",
                    metadata={
                        "prompt_length": len(prompt_sme)
                    }
                )
            )

        # Usar el nuevo método run_with_thread
        texto = self.run_with_thread(prompt_actualizado)

        # Guardar la salida
        self._save_output(texto, iteration_id)

        # Intentar extraer el JSON de la respuesta
        try:
            # El resto del código sigue igual, procesando la respuesta
            # Buscar el JSON en la respuesta (puede estar en un bloque de código)
            json_match = re.search(r'```json\n(.*?)\n```|```(.*?)```|({.*})', texto, re.DOTALL)

            if json_match:
                json_str = json_match.group(1) or json_match.group(2) or json_match.group(3)
                # Transformar el JSON en objetos de requerimientos
                data = json.loads(json_str)

                # Crear la lista de requerimientos desde el JSON
                self.requirements_list = self._create_requirements_from_json(data)
            else:
                # Si no se pudo extraer el JSON, intentar procesar el texto como requerimientos
                # Buscar líneas que parezcan requerimientos
                lines = texto.split("\n")
                req_lines = [line for line in lines if re.match(r'^REQ-\d+|^\d+\.|^-', line.strip())]

                if req_lines:
                    self.requirements_list = RequirementsList.from_strings(req_lines)
                else:
                    # Si no hay formato claro, usar todo el texto como entrada
                    self.requirements_list = RequirementsList.from_strings(lines)

            # Notificar completado si el sistema de mensajería está disponible
            if self._sistema_mensajeria:
                reqs_dict = [{"id": req.id, "descripcion": req.description, "prioridad": req.priority}
                             for req in self.requirements_list]
                self._sistema_mensajeria.publicar(
                    Mensaje(
                        emisor=self.config.name,
                        tipo="requerimientos_generados",
                        contenido=f"Generados {len(self.requirements_list)} requerimientos",
                        metadata={
                            "requerimientos_count": len(self.requirements_list),
                            "requerimientos": reqs_dict
                        }
                    )
                )

            return self.requirements_list

        except Exception as e:
            # Si falla el procesamiento JSON, recurrir al método anterior
            lines = texto.split("\n")
            self.requirements_list = RequirementsList.from_strings(lines)

            if self.config.verbose:
                print(f"[{self.config.name}] ⚠️ Error al procesar JSON: {str(e)}. Se procesó como texto plano.")

            # Notificar error si el sistema de mensajería está disponible
            if self._sistema_mensajeria:
                self._sistema_mensajeria.publicar(
                    Mensaje(
                        emisor=self.config.name,
                        tipo="error_procesamiento",
                        contenido=f"Error al procesar JSON: {str(e)}",
                        metadata={
                            "error": str(e),
                            "texto_length": len(texto)
                        }
                    )
                )

            return self.requirements_list

    # 3. Actualiza el método verificar_requerimientos para usar run_with_thread:
    def verificar_requerimientos(self, requerimientos_funcionales: Union[List[str], RequirementsList],
                                 codigo_actual: List[str]) -> bool:
        """
        Verifica si todos los requerimientos funcionales están implementados en el código actual.

        Args:
            requerimientos_funcionales: Lista de requerimientos funcionales a verificar.
            codigo_actual: Código actual implementado.

        Returns:
            bool: True si todos los requerimientos están implementados, False en caso contrario.
        """
        iteration_id = self._generate_iteration_id()

        # Convertir requerimientos a RequirementsList si es una lista de strings
        if isinstance(requerimientos_funcionales, list):
            reqs_list = RequirementsList.from_strings(requerimientos_funcionales)
        else:
            reqs_list = requerimientos_funcionales

        # Formatear los requerimientos para el prompt
        reqs_formatted = "\n".join([f"- {req.id}: {req.description}" for req in reqs_list])

        # Preparar el prompt para la verificación
        prompt = f"""
        Evalúa el código desarrollado y determina qué requerimientos se han cumplido y cuáles faltan.

        Requerimientos originales:
        {reqs_formatted}

        Código actual:
        ```
        {'\n'.join(codigo_actual)}
        ```

        Para cada requerimiento, indica claramente si:
        1. CUMPLIDO: El requerimiento está completamente implementado
        2. PARCIAL: El requerimiento está parcialmente implementado (explica qué falta)
        3. PENDIENTE: El requerimiento no ha sido implementado

        FORMATO DE RESPUESTA:
        Responde con un análisis del estado de cada requerimiento en formato JSON:
        {{
            "requirements_status": [
                {{
                    "id": "REQ-01",
                    "status": "CUMPLIDO|PARCIAL|PENDIENTE",
                    "analysis": "Análisis detallado de por qué tiene ese estado"
                }},
                ...
            ],
            "all_complete": true|false
        }}

        IMPORTANTE: Asegúrate de incluir el campo "all_complete" con el valor true solo si TODOS los requerimientos están CUMPLIDOS.
        """

        # Notificar inicio de verificación si el sistema de mensajería está disponible
        if self._sistema_mensajeria:
            self._sistema_mensajeria.publicar(
                Mensaje(
                    emisor=self.config.name,
                    tipo="verificando_requerimientos",
                    contenido=f"Verificando {len(reqs_list)} requerimientos contra {len(codigo_actual)} líneas de código",
                    metadata={
                        "requerimientos_count": len(reqs_list),
                        "codigo_length": len('\n'.join(codigo_actual))
                    }
                )
            )

        # Usar el método run_with_thread
        texto = self.run_with_thread(prompt)

        # El resto del procesamiento queda igual
        # Guardar la salida
        self._save_output(texto, iteration_id)

        # Intentar extraer el JSON de la respuesta
        try:
            # Buscar el JSON en la respuesta (puede estar en un bloque de código)
            json_match = re.search(r'```json\n(.*?)\n```|```(.*?)```|({.*})', texto, re.DOTALL)

            if json_match:
                json_str = json_match.group(1) or json_match.group(2) or json_match.group(3)
                data = json.loads(json_str)

                # ... El resto del procesamiento de JSON ...

                # Verificar si todos los requerimientos están completos
                todos_completos = data.get("all_complete", False)

                # Notificar resultado si el sistema de mensajería está disponible
                if self._sistema_mensajeria:
                    self._sistema_mensajeria.publicar(
                        Mensaje(
                            emisor=self.config.name,
                            tipo="verificacion_completada",
                            contenido=f"Verificación completada: {'Todos completos' if todos_completos else 'Hay pendientes'}",
                            metadata={
                                "todos_completos": todos_completos,
                                "requirements_status": data.get("requirements_status", [])
                            }
                        )
                    )

                return todos_completos

            # Si no se pudo extraer el JSON, usar el método anterior
            return self._confirmar_requerimientos_resueltos(requerimientos_funcionales, texto)

        except Exception as e:
            if self.config.verbose:
                print(f"[{self.config.name}] ⚠️ Error al procesar JSON: {str(e)}. Usando método alternativo.")

            # Notificar error si el sistema de mensajería está disponible
            if self._sistema_mensajeria:
                self._sistema_mensajeria.publicar(
                    Mensaje(
                        emisor=self.config.name,
                        tipo="error_verificacion",
                        contenido=f"Error al procesar JSON de verificación: {str(e)}",
                        metadata={
                            "error": str(e)
                        }
                    )
                )

            # Si falla el procesamiento JSON, recurrir al método anterior
            return self._confirmar_requerimientos_resueltos(requerimientos_funcionales, texto)

    def _create_requirements_from_json(self, data: Dict[str, Any]) -> RequirementsList:
        """
        Crea una lista de requerimientos a partir de datos JSON.

        Args:
            data: Datos JSON con los requerimientos.

        Returns:
            RequirementsList: Lista de requerimientos.
        """
        requirements_list = RequirementsList()

        # Si el JSON tiene una estructura diferente, intentar adaptarla
        if "requirements" in data:
            reqs_data = data["requirements"]
        else:
            # Intentar usar la primera clave que encuentre con una lista
            for key, value in data.items():
                if isinstance(value, list):
                    reqs_data = value
                    break
            else:
                # Si no hay listas, intentar usar el propio diccionario
                reqs_data = [data]

        # Procesar cada requerimiento
        for i, req_data in enumerate(reqs_data):
            try:
                # Si el requerimiento es una cadena, convertirlo a objeto
                if isinstance(req_data, str):
                    req = FunctionalRequirement.from_string(req_data)
                else:
                    # Asegurarse de que tenga los campos necesarios
                    if "id" not in req_data:
                        req_data["id"] = f"REQ-{i + 1:02d}"

                    if "description" not in req_data and "text" in req_data:
                        req_data["description"] = req_data["text"]
                    elif "description" not in req_data:
                        # Si no hay descripción ni texto, usar el requerimiento completo
                        req_data["description"] = str(req_data)

                    req = FunctionalRequirement(**req_data)

                requirements_list.add_requirement(req)
            except Exception as e:
                if self.config.verbose:
                    print(f"[{self.config.name}] ⚠️ Error al procesar requerimiento: {str(e)}")

        return requirements_list

    def verificar_requerimientos(self, requerimientos_funcionales: Union[List[str], RequirementsList],
                                 codigo_actual: List[str]) -> bool:
        """
        Verifica si todos los requerimientos funcionales están implementados en el código actual.

        Args:
            requerimientos_funcionales: Lista de requerimientos funcionales a verificar.
            codigo_actual: Código actual implementado.

        Returns:
            bool: True si todos los requerimientos están implementados, False en caso contrario.
        """
        iteration_id = self._generate_iteration_id()

        # Convertir requerimientos a RequirementsList si es una lista de strings
        if isinstance(requerimientos_funcionales, list):
            reqs_list = RequirementsList.from_strings(requerimientos_funcionales)
        else:
            reqs_list = requerimientos_funcionales

        # Crear un nuevo thread para esta conversación
        thread = self.client.beta.threads.create()

        # Formatear los requerimientos para el prompt
        reqs_formatted = "\n".join([f"- {req.id}: {req.description}" for req in reqs_list])

        # Preparar el prompt para la verificación
        prompt = f"""
        Evalúa el código desarrollado y determina qué requerimientos se han cumplido y cuáles faltan.

        Requerimientos originales:
        {reqs_formatted}

        Código actual:
        ```
        {'\n'.join(codigo_actual)}
        ```

        Para cada requerimiento, indica claramente si:
        1. CUMPLIDO: El requerimiento está completamente implementado
        2. PARCIAL: El requerimiento está parcialmente implementado (explica qué falta)
        3. PENDIENTE: El requerimiento no ha sido implementado

        FORMATO DE RESPUESTA:
        Responde con un análisis del estado de cada requerimiento en formato JSON:
        {{
            "requirements_status": [
                {{
                    "id": "REQ-01",
                    "status": "CUMPLIDO|PARCIAL|PENDIENTE",
                    "analysis": "Análisis detallado de por qué tiene ese estado"
                }},
                ...
            ],
            "all_complete": true|false
        }}

        IMPORTANTE: Asegúrate de incluir el campo "all_complete" con el valor true solo si TODOS los requerimientos están CUMPLIDOS.
        """

        # Agregar mensaje al thread
        self.client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=prompt
        )

        # Ejecutar el asistente en este thread
        run = self.client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=self.assistant.id
        )

        # Esperar a que termine la ejecución
        while run.status in ["queued", "in_progress"]:
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )

        # Obtener los mensajes resultantes
        messages = self.client.beta.threads.messages.list(
            thread_id=thread.id
        )

        # Extraer el contenido del último mensaje (respuesta del asistente)
        assistant_messages = [
            msg for msg in messages.data
            if msg.role == "assistant"
        ]

        if assistant_messages:
            latest_message = assistant_messages[0]
            content_parts = [
                part.text.value for part in latest_message.content
                if hasattr(part, "text") and hasattr(part.text, "value")
            ]
            texto = "\n".join(content_parts)

            # Guardar la salida
            self._save_output(texto, iteration_id)

            # Intentar extraer el JSON de la respuesta
            try:
                # Buscar el JSON en la respuesta (puede estar en un bloque de código)
                json_match = re.search(r'```json\n(.*?)\n```|```(.*?)```|({.*})', texto, re.DOTALL)

                if json_match:
                    json_str = json_match.group(1) or json_match.group(2) or json_match.group(3)
                    data = json.loads(json_str)

                    # Actualizar el estado de los requerimientos
                    if "requirements_status" in data:
                        for req_status in data["requirements_status"]:
                            req_id = req_status.get("id")
                            status = req_status.get("status", "").upper()

                            # Mapear los estados al formato de Pydantic
                            status_map = {
                                "CUMPLIDO": "Completo",
                                "PARCIAL": "Parcial",
                                "PENDIENTE": "Pendiente"
                            }

                            # Actualizar el estado en la lista de requerimientos
                            for req in reqs_list:
                                if req.id == req_id:
                                    req.status = status_map.get(status, "Pendiente")

                    # Verificar si todos los requerimientos están completos
                    return data.get("all_complete", False)

                # Si no se pudo extraer el JSON, usar el método anterior
                return self._confirmar_requerimientos_resueltos(requerimientos_funcionales, texto)

            except Exception as e:
                if self.config.verbose:
                    print(f"[{self.config.name}] ⚠️ Error al procesar JSON: {str(e)}. Usando método alternativo.")

                # Si falla el procesamiento JSON, recurrir al método anterior
                return self._confirmar_requerimientos_resueltos(requerimientos_funcionales, texto)

        return False

    def _confirmar_requerimientos_resueltos(self, requerimientos_funcionales: Union[List[str], RequirementsList],
                                            respuesta: str) -> bool:
        """
        Verifica si todos los requerimientos funcionales están resueltos según la respuesta del agente.

        Args:
            requerimientos_funcionales: Lista de requerimientos funcionales a verificar.
            respuesta: Respuesta del agente que contiene información sobre el estado de los requerimientos.

        Returns:
            bool: True si todos los requerimientos están resueltos, False en caso contrario.
        """
        # Si no hay requerimientos, consideramos que están resueltos
        if not requerimientos_funcionales:
            return True

        # Verificar si la respuesta indica que todos los requerimientos están completos
        if "TODOS LOS REQUERIMIENTOS ESTÁN COMPLETOS" in respuesta.upper() or "ALL REQUIREMENTS ARE COMPLETE" in respuesta.upper():
            return True

        # Convertir a lista de strings si es un RequirementsList
        if isinstance(requerimientos_funcionales, RequirementsList):
            reqs_str = [str(req) for req in requerimientos_funcionales]
        else:
            reqs_str = requerimientos_funcionales

        # Contar cuántos requerimientos están marcados como completos
        requerimientos_completos = 0
        for req in reqs_str:
            req_id = req.split(":")[0].strip() if ":" in req else req.strip()
            if (f"{req_id}: COMPLETO" in respuesta or
                    f"{req_id}: CUMPLIDO" in respuesta or
                    f"{req_id} - COMPLETO" in respuesta or
                    f"{req_id} - CUMPLIDO" in respuesta):
                requerimientos_completos += 1

        # Si todos los requerimientos están completos, retornar True
        return requerimientos_completos == len(reqs_str)

    def __str__(self):
        return f"{self.config.name}: Generador de requerimientos funcionales"

    # Actualización de la clase SME para revisar código del proyecto

    # Método a añadir/actualizar en la clase SME en src/agents/sme.py

    def verificar_requerimientos_proyecto(self, requerimientos_funcionales, project_path):
        """
        Verifica si todos los requerimientos funcionales están implementados
        revisando directamente los archivos en la carpeta del proyecto.

        Args:
            requerimientos_funcionales: Lista de requerimientos funcionales a verificar.
            project_path: Ruta a la carpeta del proyecto.

        Returns:
            bool: True si todos los requerimientos están implementados, False en caso contrario.
            dict: Diccionario con el estado de cada requerimiento.
        """
        iteration_id = self._generate_iteration_id()

        # Convertir requerimientos a RequirementsList si es una lista de strings
        if isinstance(requerimientos_funcionales, list):
            from src.core.models import RequirementsList, FunctionalRequirement
            reqs_list = RequirementsList.from_strings(requerimientos_funcionales)
        else:
            reqs_list = requerimientos_funcionales

        # Verificar que el directorio del proyecto exista
        if not os.path.exists(project_path):
            error_msg = f"La carpeta del proyecto no existe: {project_path}"
            print(f"[{self.config.name}] ⚠️ {error_msg}")
            self._save_output(error_msg, iteration_id)
            return False, {}

        # Recolectar archivos importantes del proyecto
        archivos_codigo = []
        project_path = Path(project_path)

        # Crear un resumen de la estructura del proyecto
        estructura_proyecto = ["# Estructura del proyecto"]
        estructura_proyecto.append(f"\nCarpeta raíz: {project_path}")

        # Listar directorios principales
        estructura_proyecto.append("\n## Directorios principales:")
        for item in project_path.iterdir():
            if item.is_dir():
                estructura_proyecto.append(f"- {item.name}/")

        # Extensiones de archivos relevantes para revisión
        extensiones_codigo = ['.js', '.jsx', '.ts', '.tsx', '.py', '.html', '.css', '.php', '.java', '.go', '.rb']

        # Recolectar archivos de código por tipo
        archivos_frontend = []
        archivos_backend = []
        archivos_config = []

        # Función para determinar la categoría de un archivo
        def categorizar_archivo(ruta):
            if "frontend" in str(ruta) or "client" in str(ruta) or "public" in str(ruta):
                return "frontend"
            elif "backend" in str(ruta) or "server" in str(ruta) or "api" in str(ruta):
                return "backend"
            else:
                # Por extensión
                ext = ruta.suffix.lower()
                if ext in ['.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.vue', '.svelte']:
                    return "frontend"
                elif ext in ['.py', '.java', '.php', '.go', '.rb']:
                    return "backend"
                else:
                    return "config"

        # Buscar recursivamente todos los archivos de código
        for ext in extensiones_codigo:
            for archivo in project_path.glob(f"**/*{ext}"):
                if archivo.is_file() and not any(
                        exclude in str(archivo) for exclude in ["node_modules", "__pycache__", ".git"]):
                    categoria = categorizar_archivo(archivo)
                    ruta_relativa = archivo.relative_to(project_path)

                    try:
                        with open(archivo, "r", encoding="utf-8") as f:
                            contenido = f.read()

                        # Limitar el tamaño de los archivos grandes para evitar problemas de contexto
                        if len(contenido) > 5000:
                            contenido = contenido[
                                        :5000] + f"\n\n... [Archivo truncado, tamaño original: {len(contenido)} caracteres]"

                        # Agregar a la categoría correspondiente
                        if categoria == "frontend":
                            archivos_frontend.append((str(ruta_relativa), contenido))
                        elif categoria == "backend":
                            archivos_backend.append((str(ruta_relativa), contenido))
                        else:
                            archivos_config.append((str(ruta_relativa), contenido))

                    except Exception as e:
                        print(f"Error al leer archivo {archivo}: {str(e)}")

        # Agregar información sobre archivos encontrados a la estructura
        estructura_proyecto.append(f"\n## Frontend ({len(archivos_frontend)} archivos):")
        for ruta, _ in archivos_frontend:
            estructura_proyecto.append(f"- {ruta}")

        estructura_proyecto.append(f"\n## Backend ({len(archivos_backend)} archivos):")
        for ruta, _ in archivos_backend:
            estructura_proyecto.append(f"- {ruta}")

        estructura_proyecto.append(f"\n## Configuración y otros ({len(archivos_config)} archivos):")
        for ruta, _ in archivos_config:
            estructura_proyecto.append(f"- {ruta}")

        # Formatear los archivos para el prompt - seleccionar los más importantes
        archivos_para_prompt = []

        # Agregar README si existe
        readme_path = project_path / "README.md"
        if readme_path.exists():
            try:
                with open(readme_path, "r", encoding="utf-8") as f:
                    contenido = f.read()
                archivos_para_prompt.append(("README.md", contenido))
            except Exception as e:
                print(f"Error al leer README: {str(e)}")

        # Seleccionar los archivos más importantes - limitamos para no exceder el contexto
        # Comenzar con package.json u otros archivos de configuración críticos
        archivos_criticos = []
        for ruta, contenido in archivos_config:
            if "package.json" in ruta or "config" in ruta or "settings" in ruta:
                archivos_criticos.append((ruta, contenido))

        # Combinar archivos frontend y backend, priorizando los más importantes
        frontend_principales = archivos_frontend[:6]  # Limitar a 6 archivos frontend
        backend_principales = archivos_backend[:6]  # Limitar a 6 archivos backend
        config_principales = archivos_criticos[:3]  # Limitar a 3 archivos de configuración

        archivos_para_prompt.extend(frontend_principales)
        archivos_para_prompt.extend(backend_principales)
        archivos_para_prompt.extend(config_principales)

        # Crear un nuevo thread para esta conversación
        thread = self.client.beta.threads.create()

        # Formatear los requerimientos para el prompt
        reqs_formatted = "\n".join([f"- {req.id}: {req.description}" for req in reqs_list])

        # Formato para mostrar los archivos
        archivos_texto = []
        for ruta, contenido in archivos_para_prompt:
            extension = ruta.split('.')[-1] if '.' in ruta else ""
            archivos_texto.append(f"\n### {ruta}")
            archivos_texto.append(f"```{extension}")
            archivos_texto.append(contenido)
            archivos_texto.append("```")

        archivos_texto_str = "\n".join(archivos_texto)
        estructura_proyecto_str = "\n".join(estructura_proyecto)

        # Preparar el prompt para la verificación
        prompt = f"""
        Evalúa el código del proyecto para determinar qué requerimientos se han cumplido y cuáles faltan.

        Requerimientos funcionales a verificar:
        {reqs_formatted}

        {estructura_proyecto_str}

        Código del proyecto (archivos principales):
        {archivos_texto_str}

        TAREAS:
        1. Analiza cada requerimiento y determina su estado actual.
        2. Para cada requerimiento, indica claramente si está:
           - CUMPLIDO: El requerimiento está completamente implementado
           - PARCIAL: El requerimiento está parcialmente implementado (explica qué falta)
           - PENDIENTE: El requerimiento no ha sido implementado
        3. Proporciona evidencia específica en el código para justificar tu evaluación.

        FORMATO DE RESPUESTA:
        Responde con un análisis del estado de cada requerimiento en formato JSON:
        {{
            "requirements_status": [
                {{
                    "id": "REQ-01",
                    "status": "CUMPLIDO|PARCIAL|PENDIENTE",
                    "evidence": "Explicación detallada con referencias al código",
                    "missing": "Lo que falta por implementar (si aplica)"
                }},
                ...
            ],
            "all_complete": true|false,
            "summary": "Resumen general del estado del proyecto"
        }}

        IMPORTANTE: Busca evidencia concreta en el código. Si un archivo no está en la lista pero es mencionado en otros archivos, asume que existe.
        """

        # Agregar mensaje al thread
        self.client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=prompt
        )

        # Ejecutar el asistente en este thread
        run = self.client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=self.assistant.id
        )

        # Esperar a que termine la ejecución
        while run.status in ["queued", "in_progress"]:
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )

        # Obtener los mensajes resultantes
        messages = self.client.beta.threads.messages.list(
            thread_id=thread.id
        )

        # Extraer el contenido del último mensaje (respuesta del asistente)
        assistant_messages = [
            msg for msg in messages.data
            if msg.role == "assistant"
        ]

        if assistant_messages:
            latest_message = assistant_messages[0]
            content_parts = [
                part.text.value for part in latest_message.content
                if hasattr(part, "text") and hasattr(part.text, "value")
            ]
            texto = "\n".join(content_parts)

            # Guardar la salida
            self._save_output(texto, f"{iteration_id}-verificacion")

            # Intentar extraer el JSON de la respuesta
            try:
                # Buscar el JSON en la respuesta (puede estar en un bloque de código)
                json_match = re.search(r'```json\n(.*?)\n```|```(.*?)```|({.*})', texto, re.DOTALL)

                if json_match:
                    json_str = json_match.group(1) or json_match.group(2) or json_match.group(3)
                    data = json.loads(json_str)

                    # Actualizar el estado de los requerimientos
                    if "requirements_status" in data:
                        for req_status in data["requirements_status"]:
                            req_id = req_status.get("id")
                            status = req_status.get("status", "").upper()

                            # Mapear los estados al formato de Pydantic
                            status_map = {
                                "CUMPLIDO": "Completo",
                                "PARCIAL": "Parcial",
                                "PENDIENTE": "Pendiente"
                            }

                            # Actualizar el estado en la lista de requerimientos
                            for req in reqs_list:
                                if req.id == req_id:
                                    req.status = status_map.get(status, "Pendiente")

                    # Crear un resumen detallado para guardar
                    resumen_detallado = ["# Verificación de Requerimientos", ""]
                    resumen_detallado.append(f"## Resumen")
                    resumen_detallado.append(data.get("summary", "No disponible"))
                    resumen_detallado.append("")
                    resumen_detallado.append(f"## Estado de los Requerimientos")

                    for req_status in data.get("requirements_status", []):
                        req_id = req_status.get("id", "Sin ID")
                        status = req_status.get("status", "Desconocido")
                        evidence = req_status.get("evidence", "No proporcionada")
                        missing = req_status.get("missing", "Nada")

                        resumen_detallado.append(f"### {req_id}: {status}")
                        resumen_detallado.append(f"**Evidencia:** {evidence}")
                        if status.upper() != "CUMPLIDO" and missing:
                            resumen_detallado.append(f"**Pendiente:** {missing}")
                        resumen_detallado.append("")

                    # Guardar el resumen detallado
                    resumen_path = Path(self.config.output_dir) / f"verificacion-{iteration_id}.md"
                    with open(resumen_path, "w", encoding="utf-8") as f:
                        f.write("\n".join(resumen_detallado))

                    print(f"[{self.config.name}] ✅ Verificación detallada guardada en: {resumen_path}")

                    # Verificar si todos los requerimientos están completos
                    todos_completos = data.get("all_complete", False)
                    return todos_completos, data.get("requirements_status", {})

                # Si no se pudo extraer el JSON, recurrir al método anterior
                return self._confirmar_requerimientos_resueltos(requerimientos_funcionales, texto), {}

            except Exception as e:
                print(f"[{self.config.name}] ⚠️ Error al procesar JSON: {str(e)}. Usando método alternativo.")

                # Si falla el procesamiento JSON, recurrir al método anterior
                return self._confirmar_requerimientos_resueltos(requerimientos_funcionales, texto), {}

        return False, {}

    def inicializar_mensajeria(self):
        """Configura el sistema de mensajería para este agente."""
        # Registrar handlers para tipos específicos de mensajes
        self.registrar_callback("consulta", self.manejar_consulta)
        self.registrar_callback("aclarar_requerimiento", self.aclarar_requerimiento)
        self.registrar_callback("verificar_implementacion", self.verificar_implementacion)

        if self.config.verbose:
            print(f"[{self.config.name}] Sistema de mensajería inicializado")

    def manejar_consulta(self, mensaje):
        """Maneja consultas generales de otros agentes."""
        if self.config.verbose:
            print(f"[{self.config.name}] Recibida consulta de {mensaje.emisor}: {mensaje.contenido[:50]}...")

        # Determinar el tipo de consulta
        contenido = mensaje.contenido.lower()

        if "requerimiento" in contenido or "requisito" in contenido:
            return self.aclarar_requerimiento(mensaje)
        elif "verifica" in contenido or "implementación" in contenido or "código" in contenido:
            return self.verificar_implementacion(mensaje)
        else:
            # Consulta general, pasarla al sistema
            return self.run(mensaje.contenido)

    def aclarar_requerimiento(self, mensaje):
        """Proporciona aclaraciones sobre requerimientos específicos."""
        contenido = mensaje.contenido

        # Intentar identificar qué requerimiento se solicita
        req_match = re.search(r'REQ-\d+', contenido)
        req_id = req_match.group(0) if req_match else None

        prompt = f"""
        Se solicita una aclaración sobre {'el requerimiento ' + req_id if req_id else 'los requerimientos'}.

        Consulta: {contenido}

        Proporciona una explicación detallada {'de este requerimiento' if req_id else 'de los requerimientos relevantes'}, 
        incluyendo:
        1. Qué funcionalidad debe implementarse exactamente
        2. Criterios de aceptación
        3. Consideraciones técnicas importantes
        4. Posibles desafíos de implementación

        Responde de manera clara y concisa, pero completa.
        """

        respuesta = self.run(prompt)

        # Registrar esta interacción con metadatos
        if self._sistema_mensajeria:
            self._sistema_mensajeria.publicar(
                Mensaje(
                    emisor=self.config.name,
                    tipo="registro_aclaracion",
                    contenido=f"Aclaración sobre {req_id if req_id else 'requerimientos generales'}",
                    metadata={
                        "req_id": req_id,
                        "consulta": contenido,
                        "respuesta": respuesta
                    }
                )
            )

        return respuesta

    def verificar_implementacion(self, mensaje):
        """Verifica si una implementación cumple con los requerimientos."""
        contenido = mensaje.contenido

        # Extraer código o referencia a archivos si está presente
        codigo_bloque = re.search(r'```[\w]*\n(.*?)```', contenido, re.DOTALL)
        codigo = codigo_bloque.group(1) if codigo_bloque else ""

        # Extraer requerimientos mencionados
        reqs_match = re.findall(r'REQ-\d+', contenido)
        reqs_mencionados = list(set(reqs_match))  # Eliminar duplicados

        prompt = f"""
        Se solicita verificar la implementación de código proporcionada.

        {'Requerimientos mencionados: ' + ', '.join(reqs_mencionados) if reqs_mencionados else 'No se especificaron requerimientos particulares.'}

        {'Código a verificar:' if codigo else 'No se proporcionó código explícito, analiza la consulta:'}
        {codigo if codigo else contenido}

        Evalúa si la implementación cumple con los requerimientos. Incluye:
        1. Análisis de qué requisitos se cumplen y cuáles no
        2. Problemas o deficiencias en la implementación
        3. Sugerencias para mejorar o completar la implementación

        Sé específico y detallado en tu análisis.
        """

        return self.run(prompt)

    def solicitar_diseno(self, requerimiento, arquitecto_nombre):
        """
        Solicita al arquitecto un diseño para un requerimiento específico.

        Args:
            requerimiento: El requerimiento (ID o descripción completa)
            arquitecto_nombre: Nombre del agente arquitecto

        Returns:
            El diseño proporcionado por el arquitecto
        """
        contenido = f"""
        Necesito un diseño técnico para el siguiente requerimiento:

        {requerimiento}

        Por favor, proporciona:
        1. Componentes necesarios
        2. Interacciones entre componentes
        3. Tecnologías recomendadas
        4. Consideraciones de diseño importantes
        """

        return self.consultar_agente(arquitecto_nombre, contenido)

    def verificar_codigo_requerimientos(self, codigo, requerimientos, developer_nombre=None):
        """
        Verifica si el código cumple con los requerimientos y opcionalmente solicita mejoras al desarrollador.

        Args:
            codigo: Código a verificar
            requerimientos: Lista de requerimientos a verificar
            developer_nombre: Nombre del agente desarrollador (opcional)

        Returns:
            Resultado de la verificación y, si se solicitó, respuesta del desarrollador
        """
        # Verificar el código
        verificacion = self.verificar_implementacion(
            Mensaje(
                emisor="interno",
                tipo="verificar_implementacion",
                contenido=f"""
                Verifica si este código cumple con los siguientes requerimientos:

                REQUERIMIENTOS:
                {requerimientos}

                CÓDIGO:
                ```
                {codigo}
                ```
                """
            )
        )

        # Si hay un desarrollador especificado y se detectaron problemas, solicitar mejoras
        if developer_nombre and "no cumple" in verificacion.lower():
            respuesta_dev = self.enviar_mensaje(
                destinatario=developer_nombre,
                tipo="solicitud_mejora",
                contenido=f"""
                El código no cumple completamente con los requerimientos.

                ANÁLISIS:
                {verificacion}

                Por favor, realiza las mejoras necesarias para cumplir con todos los requerimientos.
                """,
                esperar_respuesta=True,
                timeout=120.0
            )

            if respuesta_dev:
                return {
                    "verificacion": verificacion,
                    "mejoras_solicitadas": True,
                    "respuesta_developer": respuesta_dev.contenido
                }

        return {
            "verificacion": verificacion,
            "mejoras_solicitadas": False
        }