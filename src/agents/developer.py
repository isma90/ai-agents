# src/agents/developer.py
from typing import List
from core.agent import Agent
from core.config import AgentConfig

class Developer(Agent):
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
                description="Desarrollador de código",
                model=self.config.model,
                instructions=instructions
            )
    
    def run(self, descripcion_general: str) -> List[str]:
        iteration_id = self._generate_iteration_id()
        
        # Crear un nuevo thread para esta conversación
        thread = self.client.beta.threads.create()
        
        # Agregar mensaje al thread
        self.client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=descripcion_general
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
            
            return [r.strip() for r in texto.split("\n") if r.strip()]
        
        return []
    
    def __str__(self):
        return f"{self.config.name}: Desarrollador"