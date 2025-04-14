# src/core/agent.py (actualizado)
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
import os
from src.core.config import AgentConfig
from openai import OpenAI

try:
    from anthropic import Anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class Agent(ABC):
    def __init__(self, config: AgentConfig):
        self.config = config
        self.prompt_template = self._load_prompt(self.config.prompt_path)
        self.client = None

        # Inicializar cliente según el proveedor
        if config.provider == "openai":
            self.client = OpenAI(api_key=config.api_key)
        elif config.provider == "anthropic":
            if not ANTHROPIC_AVAILABLE:
                raise ImportError(
                    "El paquete 'anthropic' no está instalado. "
                    "Instálalo con 'pip install anthropic' para usar el proveedor Anthropic."
                )
            self.client = Anthropic(api_key=config.api_key)

    def _load_prompt(self, path: str) -> str:
        if not Path(path).exists():
            raise FileNotFoundError(f"Prompt file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def _save_output(self, content: str, iteration_id: str) -> str:
        Path(self.config.output_dir).mkdir(parents=True, exist_ok=True)
        filename = f"{self.config.name.lower()}-{iteration_id}.txt"
        full_path = os.path.join(self.config.output_dir, filename)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        if self.config.verbose:
            print(f"[{self.config.name}] Resultado guardado en: {full_path}")
        return full_path

    def _generate_iteration_id(self) -> str:
        return datetime.now().strftime("id-%d%m%Y-%H%M%S")

    def _format_prompt(self, **kwargs) -> str:
        return self.prompt_template.format(**kwargs)

    @abstractmethod
    def run(self, **kwargs) -> str:
        pass


class OpenAIDirectAgent(Agent):
    """
    Agente que utiliza directamente la API de chat de OpenAI (no la API de asistentes).
    Utiliza el contenido del prompt como mensaje con role: system.
    """

    def run(self, **kwargs) -> str:
        # Formateamos el prompt con los argumentos proporcionados
        formatted_prompt = self._format_prompt(**kwargs)

        # Creamos el ID de iteración
        iteration_id = self._generate_iteration_id()

        if self.config.verbose:
            print(f"[{self.config.name}] Ejecutando con {self.config.model}...")

        # Utilizamos el prompt como instrucción del sistema (system role)
        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=[
                {"role": "system", "content": self.prompt_template},
                {"role": "user", "content": formatted_prompt}
            ]
        )

        # Extraemos el contenido de la respuesta
        content = response.choices[0].message.content

        # Guardamos la salida si está configurado para hacerlo
        self._save_output(content, iteration_id)

        return content


class AnthropicAgent(Agent):
    """
    Agente que utiliza la API de Anthropic.
    Utiliza el contenido del prompt como parámetro system.
    """

    def run(self, **kwargs) -> str:
        # Formateamos el prompt con los argumentos proporcionados
        formatted_prompt = self._format_prompt(**kwargs)

        # Creamos el ID de iteración
        iteration_id = self._generate_iteration_id()

        if self.config.verbose:
            print(f"[{self.config.name}] Ejecutando con {self.config.model}...")

        # Para Anthropic, utilizamos el parámetro system para establecer el prompt como instrucción del sistema
        # Agregamos el parámetro max_tokens requerido (por defecto 4000)
        max_tokens = kwargs.get("max_tokens", 4000)

        # Obtener el mensaje de usuario, ya sea de kwargs['message'] o usando el formatted_prompt
        user_message = kwargs.get("message", formatted_prompt)

        response = self.client.messages.create(
            model=self.config.model,
            system=self.prompt_template,
            max_tokens=max_tokens,  # Añadimos el parámetro max_tokens
            messages=[
                {"role": "user", "content": user_message}
            ]
        )

        # Extraemos el contenido de la respuesta
        content = response.content[0].text

        # Guardamos la salida si está configurado para hacerlo
        self._save_output(content, iteration_id)

        return content


class OpenAIAssistantAgent(Agent):
    """
    Agente que utiliza la API de asistentes de OpenAI (beta).
    Este tipo se usa para mantener compatibilidad con las clases existentes SME y Architect.
    """

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.assistant = None
        if self.client:
            self.assistant = self._create_or_get_assistant()

    def _create_or_get_assistant(self):
        # Crea un nuevo asistente con las instrucciones del prompt
        instructions = self.prompt_template

        # Lista los asistentes existentes
        assistants = self.client.beta.assistants.list()
        existing_assistant = next((a for a in assistants.data if a.name == self.config.name), None)

        if existing_assistant:
            return existing_assistant
        else:
            return self.client.beta.assistants.create(
                name=self.config.name,
                description=f"Asistente {self.config.name}",
                model=self.config.model,
                instructions=instructions
            )

    @abstractmethod
    def run(self, **kwargs) -> str:
        pass


# Función de fábrica para crear la instancia adecuada del agente según el proveedor y tipo
def create_agent(config: AgentConfig, agent_type="direct") -> Agent:
    """
    Crea una instancia del agente basada en la configuración y el tipo especificado.

    Args:
        config: Configuración del agente
        agent_type: Tipo de agente a crear ("direct" o "assistant")

    Returns:
        Una instancia del agente apropiado
    """
    # Los agentes actuales SME y Architect son de tipo assistant
    if agent_type == "assistant":
        # Este es solo un placeholder, ya que las subclases reales serán SME y Architect
        return OpenAIAssistantAgent(config)
    else:
        if config.provider == "openai":
            return OpenAIDirectAgent(config)
        elif config.provider == "anthropic":
            return AnthropicAgent(config)
        else:
            raise ValueError(f"Proveedor no soportado: {config.provider}")