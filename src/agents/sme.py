# src/agents/sme.py
from typing import List
from core.agent import Agent
from core.config import AgentConfig

class SME(Agent):
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
                description="Generador de requerimientos funcionales",
                model=self.config.model,
                instructions=instructions
            )
    
    def run(self, descripcion_general: str) -> List[str]:
        """
        Ejecuta el agente SME, procesando la descripción general del proyecto.
        
        Args:
            descripcion_general: Descripción general del proyecto.
            
        Returns:
            List[str]: Lista de requerimientos funcionales generados.
        """
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
    
    def verificar_requerimientos(self, requerimientos_funcionales: List[str], codigo_actual: List[str]) -> bool:
        """
        Verifica si todos los requerimientos funcionales están implementados en el código actual.
        
        Args:
            requerimientos_funcionales: Lista de requerimientos funcionales a verificar.
            codigo_actual: Código actual implementado.
            
        Returns:
            bool: True si todos los requerimientos están implementados, False en caso contrario.
        """
        iteration_id = self._generate_iteration_id()
        
        # Crear un nuevo thread para esta conversación
        thread = self.client.beta.threads.create()
        
        # Preparar el prompt para la verificación
        prompt = f"""
        Evalúa el código desarrollado y determina qué requerimientos se han cumplido y cuáles faltan.
        
        Requerimientos originales:
        {requerimientos_funcionales}
        
        Código actual:
        {codigo_actual}
        
        Para cada requerimiento, indica claramente si:
        1. CUMPLIDO: El requerimiento está completamente implementado
        2. PARCIAL: El requerimiento está parcialmente implementado (explica qué falta)
        3. PENDIENTE: El requerimiento no ha sido implementado
        
        Responde con un análisis línea por línea de cada requerimiento.
        Al final, indica si TODOS LOS REQUERIMIENTOS ESTÁN COMPLETOS o no.
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
            
            # Verificar si todos los requerimientos están completos
            return self._confirmar_requerimientos_resueltos(requerimientos_funcionales, texto)
        
        return False
    
    def _confirmar_requerimientos_resueltos(self, requerimientos_funcionales: list[str], respuesta: str) -> bool:
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
        # Esto puede ser personalizado según el formato de respuesta esperado
        if "TODOS LOS REQUERIMIENTOS ESTÁN COMPLETOS" in respuesta.upper():
            return True
            
        # Contar cuántos requerimientos están marcados como completos
        requerimientos_completos = 0
        for req in requerimientos_funcionales:
            req_id = req.split(":")[0].strip()
            if f"{req_id}: COMPLETO" in respuesta or f"{req_id} - COMPLETO" in respuesta:
                requerimientos_completos += 1
                
        # Si todos los requerimientos están completos, retornar True
        return requerimientos_completos == len(requerimientos_funcionales)
    
    def __str__(self):
        return f"{self.config.name}: Generador de requerimientos funcionales"
