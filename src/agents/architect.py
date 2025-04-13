# src/agents/architect.py
import re
import os
import base64
import requests
from pathlib import Path
from typing import List
from core.agent import Agent
from core.config import AgentConfig

class Architect(Agent):
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
        
        # Crear un nuevo thread para esta conversación
        thread = self.client.beta.threads.create()
        
        # Preparar el prompt para el diseño
        prompt = self._format_prompt(requerimientos=requerimientos_texto) + "\n\n" + instrucciones_adicionales
        
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
            
            # Extraer y guardar los diagramas como imágenes
            self._extract_and_save_diagrams(texto, iteration_id)
            
            # Guardar la salida de texto
            self._save_output(texto, iteration_id)
            
            return [r.strip() for r in texto.split("\n") if r.strip()]
        
        return []
    
    def _extract_and_save_diagrams(self, texto: str, iteration_id: str) -> None:
        """
        Extrae los diagramas de Mermaid del texto y los guarda como imágenes.
        
        Args:
            texto: Texto que contiene los diagramas de Mermaid.
            iteration_id: ID de la iteración actual.
        """
        
        # Patrón para encontrar bloques de código Mermaid
        pattern = r"```mermaid\n(.*?)```"
        matches = re.finditer(pattern, texto, re.DOTALL)
        
        diagrams_created = []
        
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
                
                except Exception as e:
                    print(f"[{self.config.name}] ⚠️ Error al generar el diagrama {i}: {str(e)}")
            
            except Exception as e:
                print(f"[{self.config.name}] ⚠️ Error al procesar el diagrama {i}: {str(e)}")
        
        if not diagrams_created and self.config.verbose:
            print(f"[{self.config.name}] ℹ️ No se encontraron diagramas para guardar.")
    
    def __str__(self):
        return f"{self.config.name}: Diseñador de soluciones técnicas"
