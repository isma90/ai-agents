# Actualización de src/core/agent.py para incluir mensajería
from abc import ABC, abstractmethod
import time
from datetime import datetime
from pathlib import Path
import os
from typing import Optional, Dict, Any, List, Union
from src.core.config import AgentConfig
from src.core.messaging import SistemaMensajeria, Mensaje
from openai import OpenAI

try:
    from anthropic import Anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class Agent(ABC):
    # Sistema de mensajería compartido entre todos los agentes
    _sistema_mensajeria: Optional[SistemaMensajeria] = None

    @classmethod
    def configurar_mensajeria(cls, sistema_mensajeria: SistemaMensajeria) -> None:
        """
        Configura el sistema de mensajería compartido para todos los agentes.

        Args:
            sistema_mensajeria: Sistema de mensajería a utilizar
        """
        cls._sistema_mensajeria = sistema_mensajeria

    def __init__(self, config: AgentConfig):
        self.config = config
        self.prompt_template = self._load_prompt(self.config.prompt_path)
        self.client = None
        self.callbacks = {}  # Para almacenar callbacks de respuesta

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

        # Registrar el agente para recibir mensajes dirigidos a él
        if self._sistema_mensajeria:
            self._registrar_para_mensajes()

    def _registrar_para_mensajes(self) -> None:
        """Registra el agente para recibir mensajes dirigidos a él."""
        if self._sistema_mensajeria:
            self._sistema_mensajeria.suscribir("*", self._procesar_mensaje_entrante)

    def _procesar_mensaje_entrante(self, mensaje: Mensaje) -> None:
        """
        Procesa un mensaje entrante y ejecuta la acción apropiada.

        Args:
            mensaje: El mensaje recibido
        """
        # Solo procesar mensajes dirigidos a este agente
        if mensaje.destinatario != self.config.name:
            return

        if self.config.verbose:
            print(f"[{self.config.name}] Recibido: {mensaje}")

        # Verificar si hay un callback registrado para este tipo de mensaje
        if mensaje.tipo in self.callbacks:
            try:
                respuesta = self.callbacks[mensaje.tipo](mensaje)

                # Enviar respuesta automática si el callback devuelve algo
                if respuesta:
                    self.enviar_mensaje(
                        destinatario=mensaje.emisor,
                        tipo=f"respuesta_{mensaje.tipo}",
                        contenido=respuesta,
                        id_respuesta=mensaje.id,
                        metadata={"automatico": True}
                    )
            except Exception as e:
                error_msg = f"Error procesando mensaje {mensaje.tipo}: {str(e)}"
                print(f"[{self.config.name}] ⚠️ {error_msg}")

                # Notificar error al emisor
                self.enviar_mensaje(
                    destinatario=mensaje.emisor,
                    tipo="error",
                    contenido=error_msg,
                    id_respuesta=mensaje.id,
                    metadata={"error": True}
                )

    def registrar_callback(self, tipo_mensaje: str, callback: callable) -> None:
        """
        Registra una función para manejar un tipo específico de mensaje.

        Args:
            tipo_mensaje: Tipo de mensaje a manejar
            callback: Función que procesará el mensaje
        """
        self.callbacks[tipo_mensaje] = callback

    def enviar_mensaje(
            self,
            destinatario: str,
            tipo: str,
            contenido: str,
            id_respuesta: Optional[str] = None,
            metadata: Optional[Dict[str, Any]] = None,
            esperar_respuesta: bool = False,
            timeout: Optional[float] = None
    ) -> Union[str, Optional[Mensaje]]:
        """
        Envía un mensaje a otro agente.

        Args:
            destinatario: Nombre del agente destinatario
            tipo: Tipo de mensaje
            contenido: Contenido del mensaje
            id_respuesta: ID del mensaje al que responde (si es una respuesta)
            metadata: Metadatos adicionales
            esperar_respuesta: Si True, espera y retorna la primera respuesta
            timeout: Tiempo máximo de espera para la respuesta en segundos

        Returns:
            ID del mensaje enviado, o la respuesta si esperar_respuesta=True
        """
        if not self._sistema_mensajeria:
            raise RuntimeError("Sistema de mensajería no configurado")

        # Crear y enviar el mensaje
        mensaje = Mensaje(
            emisor=self.config.name,
            destinatario=destinatario,
            tipo=tipo,
            contenido=contenido,
            id_respuesta=id_respuesta,
            metadata=metadata or {}
        )

        mensaje_id = self._sistema_mensajeria.publicar(mensaje)

        # Si no se debe esperar respuesta, solo retornar el ID
        if not esperar_respuesta:
            return mensaje_id

        # Esperar respuesta con timeout
        start_time = time.time()
        while timeout is None or (time.time() - start_time) < timeout:
            respuestas = self._sistema_mensajeria.obtener_respuestas(mensaje_id)
            if respuestas:
                return respuestas[0]
            time.sleep(0.1)  # Pequeña pausa para no consumir CPU

        return None  # Timeout sin respuesta

    def consultar_agente(
            self,
            agente_nombre: str,
            consulta: str,
            esperar_respuesta: bool = True,
            timeout: Optional[float] = 60.0,
            metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Consulta a otro agente y opcionalmente espera su respuesta.

        Args:
            agente_nombre: Nombre del agente a consultar
            consulta: Texto de la consulta
            esperar_respuesta: Si debe esperar la respuesta
            timeout: Tiempo máximo de espera en segundos
            metadata: Metadatos adicionales

        Returns:
            Texto de la respuesta o None si no hay respuesta
        """
        resultado = self.enviar_mensaje(
            destinatario=agente_nombre,
            tipo="consulta",
            contenido=consulta,
            metadata=metadata,
            esperar_respuesta=esperar_respuesta,
            timeout=timeout
        )

        # Si se esperaba respuesta, extraer el contenido
        if esperar_respuesta and resultado:
            return resultado.contenido

        return None

    def responder_consulta(self, mensaje: Mensaje) -> str:
        """
        Responde a una consulta de otro agente.
        Implementación por defecto que puede ser sobrescrita por subclases.

        Args:
            mensaje: El mensaje de consulta recibido

        Returns:
            Texto de la respuesta
        """
        # Por defecto, simplemente ejecuta run con el contenido de la consulta
        return self.run(message=mensaje.contenido)

    def obtener_historial_mensajes(
            self,
            limite: int = 10,
            tipos: Optional[List[str]] = None,
            solo_propios: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Obtiene un historial de mensajes para este agente.

        Args:
            limite: Número máximo de mensajes a retornar
            tipos: Lista de tipos de mensajes a incluir
            solo_propios: Si True, solo incluye mensajes enviados o recibidos por este agente

        Returns:
            Lista de mensajes en formato de diccionario
        """
        if not self._sistema_mensajeria:
            return []

        filtro_emisor = self.config.name if solo_propios else None
        filtro_destinatario = self.config.name if solo_propios else None

        mensajes = self._sistema_mensajeria.obtener_mensajes(
            emisor=filtro_emisor,
            destinatario=filtro_destinatario,
            tipo=tipos[0] if tipos and len(tipos) == 1 else None,
            limite=limite
        )

        # Filtrar por múltiples tipos si se especificaron
        if tipos and len(tipos) > 1:
            mensajes = [m for m in mensajes if m.tipo in tipos]

        # Convertir a diccionarios
        return [m.to_dict() for m in mensajes]

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

        # Si recibimos una lista como primer argumento (comportamiento específico de Developer)
        if isinstance(kwargs.get("requerimientos_funcionales"), list) and isinstance(kwargs.get("diseno_tecnico"),
                                                                                     list):
            reqs = kwargs.get("requerimientos_funcionales", [])
            diseno = kwargs.get("diseno_tecnico", [])

            # Formatear el mensaje para el usuario
            reqs_texto = "\n".join([f"- {req}" for req in reqs])
            diseno_texto = "\n".join(diseno)

            user_message = f"""
            Necesito implementar código que cumpla con los siguientes requerimientos funcionales:

            {reqs_texto}

            El diseño técnico propuesto es el siguiente:

            {diseno_texto}

            Por favor, proporciona una implementación completa y funcional que cumpla con estos requerimientos.
            Devuelve únicamente el código implementado, organizado en archivos según sea necesario.
            """

        try:
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

            # Guardar la salida si está configurado para hacerlo
            self._save_output(content, iteration_id)

            # Notificar al sistema de mensajería si está configurado
            if self._sistema_mensajeria:
                self._sistema_mensajeria.publicar(
                    Mensaje(
                        emisor=self.config.name,
                        tipo="ejecucion_completada",
                        contenido=f"Ejecución del modelo {self.config.model} completada",
                        metadata={
                            "modelo": self.config.model,
                            "tokens_respuesta": len(content.split()),
                            "iteracion_id": iteration_id
                        }
                    )
                )

            return content

        except Exception as e:
            error_msg = f"Error al ejecutar modelo Anthropic: {str(e)}"
            print(f"[{self.config.name}] ⚠️ {error_msg}")

            # Notificar error si el sistema de mensajería está configurado
            if self._sistema_mensajeria:
                self._sistema_mensajeria.publicar(
                    Mensaje(
                        emisor=self.config.name,
                        tipo="error_ejecucion",
                        contenido=error_msg,
                        metadata={
                            "error": str(e),
                            "modelo": self.config.model
                        }
                    )
                )

            # Re-lanzar la excepción para que sea manejada por el código que llamó a este método
            raise

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
        """
        Crea un nuevo asistente con las instrucciones del prompt, o recupera uno existente.

        Returns:
            Objeto asistente de la API de OpenAI
        """
        # Crea un nuevo asistente con las instrucciones del prompt
        instructions = self.prompt_template

        # Lista los asistentes existentes
        assistants = self.client.beta.assistants.list()
        existing_assistant = next((a for a in assistants.data if a.name == self.config.name), None)

        if existing_assistant:
            if self.config.verbose:
                print(f"[{self.config.name}] Utilizando asistente existente: {existing_assistant.id}")

            # Notificar recuperación si el sistema de mensajería está disponible
            if self._sistema_mensajeria:
                self._sistema_mensajeria.publicar(
                    Mensaje(
                        emisor=self.config.name,
                        tipo="asistente_recuperado",
                        contenido=f"Utilizando asistente existente: {existing_assistant.id}",
                        metadata={
                            "assistant_id": existing_assistant.id,
                            "model": self.config.model
                        }
                    )
                )

            return existing_assistant
        else:
            # Crear nuevo asistente
            new_assistant = self.client.beta.assistants.create(
                name=self.config.name,
                description=f"Asistente {self.config.name}",
                model=self.config.model,
                instructions=instructions
            )

            if self.config.verbose:
                print(f"[{self.config.name}] Nuevo asistente creado: {new_assistant.id}")

            # Notificar creación si el sistema de mensajería está disponible
            if self._sistema_mensajeria:
                self._sistema_mensajeria.publicar(
                    Mensaje(
                        emisor=self.config.name,
                        tipo="asistente_creado",
                        contenido=f"Nuevo asistente creado: {new_assistant.id}",
                        metadata={
                            "assistant_id": new_assistant.id,
                            "model": self.config.model
                        }
                    )
                )

            return new_assistant

    def run_with_thread(self, prompt: str) -> str:
        """
        Ejecuta el asistente con un thread nuevo.

        Args:
            prompt: Contenido del mensaje a enviar al asistente

        Returns:
            Respuesta del asistente
        """
        # Crear un nuevo thread para esta conversación
        thread = self.client.beta.threads.create()
        thread_id = thread.id

        if self.config.verbose:
            print(f"[{self.config.name}] Nuevo thread creado: {thread_id}")

        # Notificar creación de thread si el sistema de mensajería está disponible
        if self._sistema_mensajeria:
            self._sistema_mensajeria.publicar(
                Mensaje(
                    emisor=self.config.name,
                    tipo="thread_creado",
                    contenido=f"Nuevo thread creado: {thread_id}",
                    metadata={
                        "thread_id": thread_id
                    }
                )
            )

        # Agregar mensaje al thread
        self.client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=prompt
        )

        # Ejecutar el asistente en este thread
        run = self.client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=self.assistant.id
        )

        # Esperar a que termine la ejecución
        start_time = time.time()
        while run.status in ["queued", "in_progress"]:
            # Notificar estado si el sistema de mensajería está disponible
            if self._sistema_mensajeria and (time.time() - start_time) > 10:
                # Solo notificar cada 10 segundos para no saturar
                start_time = time.time()
                self._sistema_mensajeria.publicar(
                    Mensaje(
                        emisor=self.config.name,
                        tipo="run_en_progreso",
                        contenido=f"Run en progreso: {run.status}",
                        metadata={
                            "thread_id": thread_id,
                            "run_id": run.id,
                            "status": run.status
                        }
                    )
                )

            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )
            time.sleep(1)  # Pequeña pausa para no saturar la API

        # Verificar si la ejecución fue exitosa
        if run.status != "completed":
            error_msg = f"La ejecución del asistente falló con estado: {run.status}"
            print(f"[{self.config.name}] ⚠️ {error_msg}")

            # Notificar error si el sistema de mensajería está disponible
            if self._sistema_mensajeria:
                self._sistema_mensajeria.publicar(
                    Mensaje(
                        emisor=self.config.name,
                        tipo="run_fallido",
                        contenido=error_msg,
                        metadata={
                            "thread_id": thread_id,
                            "run_id": run.id,
                            "status": run.status
                        }
                    )
                )

            return f"Error: {run.status}"

        # Obtener los mensajes resultantes
        messages = self.client.beta.threads.messages.list(
            thread_id=thread_id
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

            # Notificar respuesta si el sistema de mensajería está disponible
            if self._sistema_mensajeria:
                self._sistema_mensajeria.publicar(
                    Mensaje(
                        emisor=self.config.name,
                        tipo="respuesta_recibida",
                        contenido=f"Respuesta recibida ({len(texto)} caracteres)",
                        metadata={
                            "thread_id": thread_id,
                            "respuesta_length": len(texto)
                        }
                    )
                )

            return texto

        # Si no hay respuesta del asistente
        error_msg = "No se recibió respuesta del asistente"
        print(f"[{self.config.name}] ⚠️ {error_msg}")

        # Notificar error si el sistema de mensajería está disponible
        if self._sistema_mensajeria:
            self._sistema_mensajeria.publicar(
                Mensaje(
                    emisor=self.config.name,
                    tipo="sin_respuesta",
                    contenido=error_msg,
                    metadata={
                        "thread_id": thread_id
                    }
                )
            )

        return ""

    @abstractmethod
    def run(self, **kwargs) -> str:
        """
        Implementación abstracta que debe ser sobreescrita por las subclases.
        """
        pass

    def responder_consulta(self, mensaje: 'Mensaje') -> str:
        """
        Responde a una consulta recibida a través del sistema de mensajería.

        Args:
            mensaje: Mensaje recibido

        Returns:
            Respuesta a la consulta
        """
        if self.config.verbose:
            print(f"[{self.config.name}] Respondiendo a consulta de {mensaje.emisor}: {mensaje.contenido[:50]}...")

        # Formatear el mensaje para incluir la fuente
        prompt = f"""
        [Consulta de {mensaje.emisor}]

        {mensaje.contenido}

        Por favor, proporciona una respuesta detallada y útil.
        """

        # Utilizar el método run_with_thread para obtener una respuesta
        respuesta = self.run_with_thread(prompt)

        return respuesta