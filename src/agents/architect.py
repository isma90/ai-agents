# src/agents/architect.py
import re
import base64
import requests
from pathlib import Path
from typing import List
from src.core.agent import OpenAIAssistantAgent
from src.core.config import AgentConfig
from src.core.messaging import Mensaje


class Architect(OpenAIAssistantAgent):
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.assistant = None
        if self.client:
            self.assistant = self._create_or_get_assistant()
    
    def _create_or_get_assistant(self):
        # Crea un nuevo asistente con las instrucciones del prompt
        with open(self.config.prompt_path, "r", encoding="utf-8") as f:
            instructions = f.read()
        
        # Lista los asistentes existentes
        assistants = self.client.beta.assistants.list()
        existing_assistant = next((a for a in assistants.data if a.name == self.config.name), None)
        
        if existing_assistant:
            return existing_assistant
        else:
            return self.client.beta.assistants.create(
                name=self.config.name,
                description="Diseñador de soluciones técnicas",
                model=self.config.model,
                instructions=instructions
            )

    def run(self, requerimientos_funcionales: List[str]) -> List[str]:
        """
        Ejecuta el agente Architect, procesando los requerimientos funcionales.

        Args:
            requerimientos_funcionales: Lista de requerimientos funcionales a procesar.

        Returns:
            List[str]: Lista de líneas del diseño técnico generado.
        """
        iteration_id = self._generate_iteration_id()

        # Verificar que los requerimientos no estén vacíos
        if not requerimientos_funcionales:
            error_msg = "No se proporcionaron requerimientos funcionales."
            print(f"[{self.config.name}] ⚠️ {error_msg}")
            self._save_output(error_msg, iteration_id)
            return [error_msg]

        # Formatear los requerimientos como texto
        requerimientos_texto = "\n".join([f"- {req}" for req in requerimientos_funcionales])

        # Añadir instrucciones específicas para la generación de diagramas
        instrucciones_adicionales = """
        IMPORTANTE: 
        1. Genera un diseño técnico detallado basado en los requerimientos.
        2. Incluye diagramas de arquitectura utilizando la sintaxis de Mermaid.
        3. Para cada diagrama, usa el siguiente formato:

        ```mermaid
        // Código del diagrama aquí
        ```

        4. Asegúrate de incluir al menos un diagrama de arquitectura de alto nivel.
        5. Proporciona una explicación detallada de cada componente y su interacción.
        """

        # Preparar el prompt para el diseño
        prompt = self._format_prompt(requerimientos=requerimientos_texto) + "\n\n" + instrucciones_adicionales

        # Notificar inicio de diseño si el sistema de mensajería está disponible
        if self._sistema_mensajeria:
            self._sistema_mensajeria.publicar(
                Mensaje(
                    emisor=self.config.name,
                    tipo="generando_diseno",
                    contenido=f"Generando diseño para {len(requerimientos_funcionales)} requerimientos",
                    metadata={
                        "requerimientos_count": len(requerimientos_funcionales)
                    }
                )
            )

        # Usar el método run_with_thread
        texto = self.run_with_thread(prompt)

        # Extraer y guardar los diagramas como imágenes
        diagramas = self._extract_and_save_diagrams(texto, iteration_id)

        # Guardar la salida de texto
        self._save_output(texto, iteration_id)

        # Notificar diseño completo si el sistema de mensajería está disponible
        if self._sistema_mensajeria:
            self._sistema_mensajeria.publicar(
                Mensaje(
                    emisor=self.config.name,
                    tipo="diseno_completado",
                    contenido=f"Diseño completado con {len(diagramas)} diagramas",
                    metadata={
                        "diagramas_count": len(diagramas),
                        "diseno_length": len(texto)
                    }
                )
            )

        return [r.strip() for r in texto.split("\n") if r.strip()]

    def _extract_and_save_diagrams(self, texto: str, iteration_id: str) -> List[str]:
        """
        Extrae los diagramas de Mermaid del texto y los guarda como imágenes.

        Args:
            texto: Texto que contiene los diagramas de Mermaid.
            iteration_id: ID de la iteración actual.

        Returns:
            List[str]: Lista de rutas a los diagramas generados.
        """
        # Patrón para encontrar bloques de código Mermaid
        pattern = r"```mermaid\n(.*?)```"
        matches = re.finditer(pattern, texto, re.DOTALL)

        diagrams_created = []  # Lista para almacenar las rutas de los diagramas creados

        for i, match in enumerate(matches, 1):
            mermaid_code = match.group(1).strip()

            try:
                # Crear el directorio de salida si no existe
                output_dir = Path(self.config.output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)

                # Nombre del archivo de imagen
                image_filename = f"{self.config.name.lower()}-diagram-{i}-{iteration_id}.png"
                image_path = output_dir / image_filename

                # Guardar el código Mermaid en un archivo de texto
                mermaid_filename = f"{self.config.name.lower()}-diagram-{i}-{iteration_id}.mmd"
                mermaid_path = output_dir / mermaid_filename

                with open(mermaid_path, "w", encoding="utf-8") as f:
                    f.write(mermaid_code)

                # Intentar convertir el diagrama a imagen usando la API de Mermaid
                try:
                    # Codificar el código Mermaid en base64
                    mermaid_base64 = base64.b64encode(mermaid_code.encode("utf-8")).decode("utf-8")

                    # URL para la API de Mermaid
                    url = f"https://mermaid.ink/img/{mermaid_base64}"

                    # Descargar la imagen
                    response = requests.get(url, timeout=10)

                    if response.status_code == 200:
                        with open(image_path, "wb") as f:
                            f.write(response.content)

                        diagrams_created.append(str(image_path))

                        if self.config.verbose:
                            print(f"[{self.config.name}] ✅ Diagrama guardado en: {image_path}")
                    else:
                        print(f"[{self.config.name}] ⚠️ Error al generar el diagrama {i}: {response.status_code}")
                        # Aún así, agregamos la ruta del archivo .mmd a la lista de diagramas creados
                        diagrams_created.append(str(mermaid_path))

                except Exception as e:
                    print(f"[{self.config.name}] ⚠️ Error al generar el diagrama {i}: {str(e)}")
                    # Aún si falla la conversión a imagen, guardamos el archivo .mmd
                    diagrams_created.append(str(mermaid_path))

            except Exception as e:
                print(f"[{self.config.name}] ⚠️ Error al procesar el diagrama {i}: {str(e)}")

        if not diagrams_created and self.config.verbose:
            print(f"[{self.config.name}] ℹ️ No se encontraron diagramas para guardar.")

        # Devolvemos la lista de rutas a los diagramas creados
        return diagrams_created

    def __str__(self):
        return f"{self.config.name}: Diseñador de soluciones técnicas"

    def inicializar_mensajeria(self):
        """Configura el sistema de mensajería para este agente."""
        # Registrar handlers para tipos específicos de mensajes
        self.registrar_callback("consulta", self.manejar_consulta)
        self.registrar_callback("diseño_tecnologico", self.crear_diseno_tecnologico)
        self.registrar_callback("validar_diseno", self.validar_diseno)
        self.registrar_callback("aclarar_arquitectura", self.aclarar_arquitectura)

        if self.config.verbose:
            print(f"[{self.config.name}] Sistema de mensajería inicializado")

    def manejar_consulta(self, mensaje):
        """Maneja consultas generales de otros agentes."""
        if self.config.verbose:
            print(f"[{self.config.name}] Recibida consulta de {mensaje.emisor}: {mensaje.contenido[:50]}...")

        # Determinar el tipo de consulta
        contenido = mensaje.contenido.lower()

        if "diseño" in contenido or "arquitectura" in contenido:
            return self.crear_diseno_tecnologico(mensaje)
        elif "validar" in contenido or "revisar" in contenido:
            return self.validar_diseno(mensaje)
        elif "aclarar" in contenido or "explicar" in contenido:
            return self.aclarar_arquitectura(mensaje)
        else:
            # Consulta general, pasarla al sistema
            respuesta = self.run(mensaje.contenido)
            return respuesta

    def crear_diseno_tecnologico(self, mensaje):
        """
        Crea un diseño tecnológico basado en los requerimientos proporcionados.

        Args:
            mensaje: Mensaje con la solicitud de diseño

        Returns:
            Diseño tecnológico como texto
        """
        contenido = mensaje.contenido

        # Extraer requerimientos si están presentes
        reqs_block = re.search(r'REQUERIMIENTOS:?\s*(.*?)(?=\n\n|$)', contenido, re.DOTALL)
        reqs = reqs_block.group(1).strip() if reqs_block else contenido

        # Verificar si hay restricciones mencionadas
        restricciones_block = re.search(r'RESTRICCIONES:?\s*(.*?)(?=\n\n|$)', contenido, re.DOTALL)
        restricciones = restricciones_block.group(1).strip() if restricciones_block else ""

        # Verificar si hay preferencias tecnológicas
        tech_block = re.search(r'TECNOLOGÍAS:?\s*(.*?)(?=\n\n|$)', contenido, re.DOTALL)
        tecnologias = tech_block.group(1).strip() if tech_block else ""

        prompt = f"""
        Crea un diseño tecnológico detallado basado en los siguientes requerimientos:

        REQUERIMIENTOS:
        {reqs}

        {f'RESTRICCIONES:\n{restricciones}\n' if restricciones else ''}
        {f'TECNOLOGÍAS PREFERIDAS:\n{tecnologias}\n' if tecnologias else ''}

        El diseño debe incluir:
        1. Arquitectura general del sistema
        2. Componentes principales y sus responsabilidades
        3. Diagramas usando sintaxis Mermaid para:
           - Arquitectura de alto nivel
           - Flujo de datos
           - Modelo de datos (si aplica)
        4. Tecnologías recomendadas para cada componente
        5. Consideraciones de seguridad, escalabilidad y mantenibilidad

        Proporciona un diseño detallado y completo que sirva como guía para la implementación.
        """

        respuesta = self.run_with_thread(prompt)

        # Registrar esta interacción con metadatos
        if self._sistema_mensajeria:
            self._sistema_mensajeria.publicar(
                Mensaje(
                    emisor=self.config.name,
                    tipo="registro_diseno",
                    contenido=f"Diseño tecnológico creado para {mensaje.emisor}",
                    metadata={
                        "solicitante": mensaje.emisor,
                        "requerimientos": reqs,
                        "restricciones": restricciones,
                        "tecnologias": tecnologias,
                        "respuesta_length": len(respuesta)
                    }
                )
            )

        return respuesta

    def validar_diseno(self, mensaje):
        """
        Valida un diseño tecnológico existente.

        Args:
            mensaje: Mensaje con la solicitud de validación

        Returns:
            Resultado de la validación como texto
        """
        contenido = mensaje.contenido

        # Extraer el diseño a validar si está presente
        import re
        diseno_block = re.search(r'DISEÑO:?\s*(.*?)(?=\n\n|$)', contenido, re.DOTALL)
        diseno = diseno_block.group(1).strip() if diseno_block else ""

        # Extraer los requerimientos si están presentes
        reqs_block = re.search(r'REQUERIMIENTOS:?\s*(.*?)(?=\n\n|$)', contenido, re.DOTALL)
        reqs = reqs_block.group(1).strip() if reqs_block else ""

        prompt = f"""
        Valida el siguiente diseño tecnológico:

        {diseno if diseno else "No se proporcionó un diseño específico para validar."}

        {f'CONTRA ESTOS REQUERIMIENTOS:\n{reqs}' if reqs else ''}

        Proporciona una evaluación detallada que incluya:
        1. ¿El diseño cumple con todos los requerimientos?
        2. ¿La arquitectura es adecuada y sigue buenas prácticas?
        3. ¿Hay problemas potenciales o áreas que mejorar?
        4. ¿Hay consideraciones importantes que faltan?
        5. Recomendaciones específicas para mejorar el diseño

        Sé objetivo y detallado en tu análisis.
        """

        return self.run_with_thread(prompt)

    def aclarar_arquitectura(self, mensaje):
        """
        Proporciona aclaraciones sobre aspectos específicos de la arquitectura o diseño.

        Args:
            mensaje: Mensaje con la solicitud de aclaración

        Returns:
            List[str]: Aclaración como lista de líneas de texto
        """
        contenido = mensaje.contenido

        prompt = f"""
        Se solicita una aclaración sobre arquitectura o diseño:

        {contenido}

        Proporciona una explicación detallada y clara que responda a la consulta.
        Incluye ejemplos, diagramas o código si es necesario para ilustrar mejor la respuesta.
        """

        # El método run devuelve una lista de strings, así que lo usamos directamente
        return self.run_with_thread(prompt)

    def consultar_requerimientos(self, sme_nombre, id_requerimiento=None):
        """
        Consulta al SME sobre detalles de requerimientos para el diseño.

        Args:
            sme_nombre: Nombre del agente SME
            id_requerimiento: ID específico del requerimiento (opcional)

        Returns:
            Aclaración de los requerimientos
        """
        if id_requerimiento:
            consulta = f"Necesito más detalles sobre el requerimiento {id_requerimiento} para crear un diseño adecuado. ¿Puedes proporcionar criterios específicos, restricciones o consideraciones importantes?"
        else:
            consulta = "Estoy diseñando la arquitectura del sistema. ¿Puedes proporcionar más detalles sobre los requerimientos no funcionales como escalabilidad, seguridad, rendimiento o mantenibilidad que debo considerar?"

        return self.consultar_agente(sme_nombre, consulta)

    def revisar_implementacion(self, codigo, diseno, developer_nombre=None):
        """
        Revisa si una implementación sigue el diseño arquitectónico.

        Args:
            codigo: Código a revisar
            diseno: Diseño contra el que se compara
            developer_nombre: Nombre del agente desarrollador (opcional)

        Returns:
            Resultado de la revisión y, si se solicitó, respuesta del desarrollador
        """
        # Analizar la implementación
        analisis = self.validar_diseno(
            Mensaje(
                emisor="interno",
                tipo="validar_diseno",
                contenido=f"""
                Verifica si esta implementación sigue el diseño arquitectónico establecido:

                DISEÑO:
                {diseno}

                IMPLEMENTACIÓN:
                ```
                {codigo}
                ```

                Evalúa si la implementación:
                1. Sigue la arquitectura propuesta
                2. Implementa correctamente los componentes descritos
                3. Respeta los patrones y principios de diseño
                4. Se desvía del diseño (y si estas desviaciones son justificadas)
                """
            )
        )

        # Si hay un desarrollador especificado y se detectaron problemas, solicitar mejoras
        if developer_nombre and ("no sigue" in analisis.lower() or "desviación" in analisis.lower()):
            respuesta_dev = self.enviar_mensaje(
                destinatario=developer_nombre,
                tipo="revision_arquitectura",
                contenido=f"""
                La implementación no sigue completamente el diseño arquitectónico establecido.

                ANÁLISIS:
                {analisis}

                Por favor, ajusta la implementación para alinearla con el diseño arquitectónico.
                """,
                esperar_respuesta=True,
                timeout=120.0
            )

            if respuesta_dev:
                return {
                    "analisis": analisis,
                    "mejoras_solicitadas": True,
                    "respuesta_developer": respuesta_dev.contenido
                }

        return {
            "analisis": analisis,
            "mejoras_solicitadas": False
        }