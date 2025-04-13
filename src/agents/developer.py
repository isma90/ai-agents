# src/agents/developer.py
import re
import os
from pathlib import Path
from typing import List
from core.agent import Agent
from core.config import AgentConfig

class Developer(Agent):
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.assistant = None
        if self.client and self.config.provider == "openai":
            self.assistant = self._create_or_get_assistant()
    
    def _create_or_get_assistant(self):
        """
        Crea o recupera un asistente de OpenAI.
        Solo se utiliza cuando el proveedor es "openai".
        """
        if self.config.provider != "openai":
            return None
            
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
                description="Desarrollador de código",
                model=self.config.model,
                instructions=instructions
            )
    
    def run(self, requerimientos_funcionales: List[str], diseno_tecnico: List[str]) -> List[str]:
        """
        Ejecuta el agente Developer, procesando los requerimientos funcionales y el diseño técnico.
        
        Args:
            requerimientos_funcionales: Lista de requerimientos funcionales a implementar.
            diseno_tecnico: Lista de líneas del diseño técnico a seguir.
            
        Returns:
            List[str]: Lista de líneas del código implementado.
        """
        iteration_id = self._generate_iteration_id()
        
        # Preparar el prompt para la implementación
        prompt = self._format_prompt(
            requerimientos="\n".join(requerimientos_funcionales),
            diseno="\n".join(diseno_tecnico)
        )
        
        # Ejecutar según el proveedor
        if self.config.provider == "openai":
            return self._run_with_openai(prompt, iteration_id)
        elif self.config.provider == "anthropic":
            return self._run_with_anthropic(prompt, iteration_id)
        else:
            raise ValueError(f"Proveedor no soportado: {self.config.provider}")
    
    def _run_with_openai(self, prompt: str, iteration_id: str) -> List[str]:
        """
        Ejecuta el agente Developer utilizando la API de OpenAI.
        """
        # Añadir instrucciones específicas para la generación de código
        instructions = """
        IMPORTANTE: Debes generar código completo y funcional para la solución.
        
        Para cada archivo que debas crear, usa el siguiente formato:
        
        ```filepath:ruta/al/archivo.ext
        // Contenido del archivo
        ```
        
        Organiza el código en una estructura de carpetas clara, separando frontend y backend.
        Asegúrate de incluir todos los archivos necesarios para que la aplicación funcione correctamente.
        """
        
        # Crear un nuevo thread para esta conversación
        thread = self.client.beta.threads.create()
        
        # Agregar mensaje al thread
        self.client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=f"{instructions}\n\n{prompt}"
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
            
            # Guardar la salida en el archivo de log
            self._save_output(texto, iteration_id)
            
            # Generar los archivos de código
            self._generate_source_code_files(texto)
            
            return [r.strip() for r in texto.split("\n") if r.strip()]
        
        return []
    
    def _run_with_anthropic(self, prompt: str, iteration_id: str) -> List[str]:
        """
        Ejecuta el agente Developer utilizando la API de Anthropic.
        """
        # Añadir instrucciones específicas para la generación de código
        system_prompt = f"""
        Eres un desarrollador experto. {self.prompt_template.split('{')[0]}
        
        IMPORTANTE: Debes generar código completo y funcional para la solución.
        
        Para cada archivo que debas crear, usa el siguiente formato:
        
        ```filepath:ruta/al/archivo.ext
        // Contenido del archivo
        ```
        
        Organiza el código en una estructura de carpetas clara, separando frontend y backend.
        Asegúrate de incluir todos los archivos necesarios para que la aplicación funcione correctamente.
        """
        
        # Crear un mensaje con Anthropic
        message = self.client.messages.create(
            model=self.config.model,
            max_tokens=4000,
            temperature=0.5,
            system=system_prompt,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # Extraer el contenido de la respuesta
        texto = message.content[0].text
        
        # Guardar la salida en el archivo de log
        self._save_output(texto, iteration_id)
        
        # Generar los archivos de código
        self._generate_source_code_files(texto)
        
        return [r.strip() for r in texto.split("\n") if r.strip()]
    
    def _generate_source_code_files(self, texto: str) -> None:
        """
        Analiza el texto generado y crea los archivos de código correspondientes.
        
        Args:
            texto: Texto generado por el modelo que contiene el código.
        """
        
        # Crear el directorio base si no existe
        base_dir = Path("src/outputs/source_code")
        base_dir.mkdir(parents=True, exist_ok=True)
        
        # Patrón para encontrar bloques de código con rutas de archivo
        pattern = r"```filepath:(.*?)\n(.*?)```"
        matches = re.finditer(pattern, texto, re.DOTALL)
        
        files_created = []
        
        for match in matches:
            filepath = match.group(1).strip()
            content = match.group(2)
            
            # Construir la ruta completa
            full_path = base_dir / filepath
            
            # Crear el directorio padre si no existe
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Escribir el contenido al archivo
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            files_created.append(str(full_path))
        
        if self.config.verbose:
            print(f"\n[{self.config.name}] ✅ Archivos generados:")
            for file in files_created:
                print(f"  - {file}")
    
    def __str__(self):
        return f"{self.config.name}: Desarrollador"
