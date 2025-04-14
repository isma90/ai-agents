# src/agents/sme.py
from typing import List, Union, Dict, Any
import json
import re
from src.core.agent import OpenAIAssistantAgent
from src.core.config import AgentConfig
from src.core.models import FunctionalRequirement, RequirementsList


class SME(OpenAIAssistantAgent):
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.requirements_list = RequirementsList()

    def run(self, descripcion_general: str) -> RequirementsList:
        """
        Ejecuta el agente SME, procesando la descripción general del proyecto.

        Args:
            descripcion_general: Descripción general del proyecto.

        Returns:
            RequirementsList: Lista estructurada de requerimientos funcionales generados.
        """
        iteration_id = self._generate_iteration_id()

        # Modificamos el prompt para solicitar una respuesta estructurada
        prompt_actualizado = f"""
        {descripcion_general}

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

        # Crear un nuevo thread para esta conversación
        thread = self.client.beta.threads.create()

        # Agregar mensaje al thread
        self.client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=prompt_actualizado
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
            except Exception as e:
                # Si falla el procesamiento JSON, recurrir al método anterior
                lines = texto.split("\n")
                self.requirements_list = RequirementsList.from_strings(lines)

                if self.config.verbose:
                    print(f"[{self.config.name}] ⚠️ Error al procesar JSON: {str(e)}. Se procesó como texto plano.")

            # Convertir a lista para mantener compatibilidad con el resto del código
            return self.requirements_list

        # Si no hay respuesta, devolver una lista vacía
        return RequirementsList()

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