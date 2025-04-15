# src/core/messaging.py
from datetime import datetime
from typing import List, Dict, Any, Optional, Union, Type
import json
import os
import uuid
from pathlib import Path


class Mensaje:
    """
    Representa un mensaje en el sistema de comunicación entre agentes.
    """

    def __init__(
            self,
            emisor: str,
            tipo: str,
            contenido: str,
            destinatario: Optional[str] = None,
            id_mensaje: Optional[str] = None,
            id_respuesta: Optional[str] = None,
            metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Inicializa un mensaje en el sistema.

        Args:
            emisor: Nombre del agente que envía el mensaje
            tipo: Tipo de mensaje (consulta, respuesta, notificación, etc.)
            contenido: Contenido principal del mensaje
            destinatario: Nombre del agente destinatario (si es específico)
            id_mensaje: Identificador único del mensaje (generado automáticamente si no se proporciona)
            id_respuesta: ID del mensaje al que responde (si es una respuesta)
            metadata: Información adicional sobre el mensaje
        """
        self.id = id_mensaje or str(uuid.uuid4())
        self.timestamp = datetime.now()
        self.emisor = emisor
        self.destinatario = destinatario
        self.tipo = tipo
        self.contenido = contenido
        self.id_respuesta = id_respuesta
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el mensaje a un diccionario para serialización."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "emisor": self.emisor,
            "destinatario": self.destinatario,
            "tipo": self.tipo,
            "contenido": self.contenido,
            "id_respuesta": self.id_respuesta,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Mensaje":
        """Crea un mensaje a partir de un diccionario."""
        # Convertir el timestamp de string a datetime
        if "timestamp" in data and isinstance(data["timestamp"], str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])

        mensaje = cls(
            emisor=data.get("emisor", "unknown"),
            tipo=data.get("tipo", "general"),
            contenido=data.get("contenido", ""),
            destinatario=data.get("destinatario"),
            id_mensaje=data.get("id"),
            id_respuesta=data.get("id_respuesta"),
            metadata=data.get("metadata", {})
        )

        # Si el timestamp estaba en el diccionario, usarlo
        if "timestamp" in data:
            mensaje.timestamp = data["timestamp"]

        return mensaje

    def __str__(self) -> str:
        """Representación en string del mensaje."""
        dest = f" → {self.destinatario}" if self.destinatario else ""
        return f"[{self.timestamp.strftime('%H:%M:%S')}] {self.emisor}{dest} ({self.tipo}): {self.contenido[:50]}{'...' if len(self.contenido) > 50 else ''}"


class SistemaMensajeria:
    """
    Sistema central de mensajería para comunicación entre agentes.
    Implementa un patrón de publicación-suscripción.
    """

    def __init__(self, ruta_almacenamiento: Optional[str] = None):
        """
        Inicializa el sistema de mensajería.

        Args:
            ruta_almacenamiento: Ruta donde se guardarán los registros de mensajes
        """
        self.mensajes: List[Mensaje] = []
        self.suscripciones: Dict[str, List[callable]] = {}
        self.ruta_almacenamiento = ruta_almacenamiento

        # Crear directorio de almacenamiento si no existe
        if self.ruta_almacenamiento:
            os.makedirs(self.ruta_almacenamiento, exist_ok=True)

    def publicar(self, mensaje: Mensaje) -> str:
        """
        Publica un mensaje en el sistema y notifica a los suscriptores.

        Args:
            mensaje: Mensaje a publicar

        Returns:
            ID del mensaje publicado
        """
        # Almacenar el mensaje
        self.mensajes.append(mensaje)

        # Guardar en disco si está configurado
        if self.ruta_almacenamiento:
            self._guardar_mensaje(mensaje)

        # Notificar a los suscriptores del tipo específico
        if mensaje.tipo in self.suscripciones:
            for callback in self.suscripciones[mensaje.tipo]:
                try:
                    callback(mensaje)
                except Exception as e:
                    print(f"Error en callback de suscripción: {e}")

        # Notificar a los suscriptores generales ('*')
        if "*" in self.suscripciones:
            for callback in self.suscripciones["*"]:
                try:
                    callback(mensaje)
                except Exception as e:
                    print(f"Error en callback de suscripción general: {e}")

        return mensaje.id

    def suscribir(self, tipo_mensaje: str, callback: callable) -> None:
        """
        Suscribe una función de callback para recibir notificaciones de cierto tipo de mensaje.

        Args:
            tipo_mensaje: Tipo de mensaje a suscribir ('*' para todos)
            callback: Función a llamar cuando llegue un mensaje de ese tipo
        """
        if tipo_mensaje not in self.suscripciones:
            self.suscripciones[tipo_mensaje] = []

        self.suscripciones[tipo_mensaje].append(callback)

    def cancelar_suscripcion(self, tipo_mensaje: str, callback: callable) -> bool:
        """
        Cancela una suscripción previamente registrada.

        Args:
            tipo_mensaje: Tipo de mensaje de la suscripción
            callback: Función registrada

        Returns:
            True si se encontró y eliminó la suscripción, False en caso contrario
        """
        if tipo_mensaje in self.suscripciones and callback in self.suscripciones[tipo_mensaje]:
            self.suscripciones[tipo_mensaje].remove(callback)
            return True
        return False

    def obtener_mensajes(
            self,
            emisor: Optional[str] = None,
            destinatario: Optional[str] = None,
            tipo: Optional[str] = None,
            desde: Optional[datetime] = None,
            hasta: Optional[datetime] = None,
            id_respuesta: Optional[str] = None,
            limite: Optional[int] = None
    ) -> List[Mensaje]:
        """
        Obtiene mensajes filtrados por varios criterios.

        Args:
            emisor: Filtrar por nombre del emisor
            destinatario: Filtrar por nombre del destinatario
            tipo: Filtrar por tipo de mensaje
            desde: Timestamp de inicio
            hasta: Timestamp de fin
            id_respuesta: Filtrar respuestas a un mensaje específico
            limite: Número máximo de mensajes a retornar

        Returns:
            Lista de mensajes que cumplen los criterios
        """
        resultado = self.mensajes.copy()

        # Aplicar filtros
        if emisor:
            resultado = [m for m in resultado if m.emisor == emisor]
        if destinatario:
            resultado = [m for m in resultado if m.destinatario == destinatario]
        if tipo:
            resultado = [m for m in resultado if m.tipo == tipo]
        if desde:
            resultado = [m for m in resultado if m.timestamp >= desde]
        if hasta:
            resultado = [m for m in resultado if m.timestamp <= hasta]
        if id_respuesta:
            resultado = [m for m in resultado if m.id_respuesta == id_respuesta]

        # Ordenar por timestamp (más reciente primero)
        resultado.sort(key=lambda m: m.timestamp, reverse=True)

        # Aplicar límite si se especificó
        if limite is not None and limite > 0:
            resultado = resultado[:limite]

        return resultado

    def obtener_mensaje(self, id_mensaje: str) -> Optional[Mensaje]:
        """
        Busca un mensaje específico por su ID.

        Args:
            id_mensaje: ID del mensaje a buscar

        Returns:
            El mensaje si se encuentra, None en caso contrario
        """
        for mensaje in self.mensajes:
            if mensaje.id == id_mensaje:
                return mensaje
        return None

    def obtener_respuestas(self, id_mensaje: str) -> List[Mensaje]:
        """
        Obtiene todas las respuestas a un mensaje específico.

        Args:
            id_mensaje: ID del mensaje del que se quieren las respuestas

        Returns:
            Lista de mensajes que son respuestas al mensaje especificado
        """
        return [m for m in self.mensajes if m.id_respuesta == id_mensaje]

    def _guardar_mensaje(self, mensaje: Mensaje) -> None:
        """
        Guarda un mensaje en disco.

        Args:
            mensaje: Mensaje a guardar
        """
        if not self.ruta_almacenamiento:
            return

        try:
            # Determinar la ruta del archivo
            fecha = mensaje.timestamp.strftime("%Y%m%d")
            ruta_archivo = Path(self.ruta_almacenamiento) / f"mensajes_{fecha}.jsonl"

            # Convertir el mensaje a JSON y añadirlo al archivo
            with open(ruta_archivo, "a", encoding="utf-8") as f:
                json_mensaje = json.dumps(mensaje.to_dict())
                f.write(f"{json_mensaje}\n")
        except Exception as e:
            print(f"Error al guardar mensaje en disco: {e}")

    def cargar_mensajes_desde_disco(self) -> int:
        """
        Carga los mensajes guardados en disco.

        Returns:
            Número de mensajes cargados
        """
        if not self.ruta_almacenamiento:
            return 0

        count = 0
        try:
            ruta = Path(self.ruta_almacenamiento)
            for archivo in ruta.glob("mensajes_*.jsonl"):
                with open(archivo, "r", encoding="utf-8") as f:
                    for linea in f:
                        try:
                            data = json.loads(linea.strip())
                            mensaje = Mensaje.from_dict(data)
                            # Evitar duplicados
                            if mensaje.id not in [m.id for m in self.mensajes]:
                                self.mensajes.append(mensaje)
                                count += 1
                        except Exception as e:
                            print(f"Error al cargar mensaje: {e}")

            # Ordenar mensajes por timestamp
            self.mensajes.sort(key=lambda m: m.timestamp)
        except Exception as e:
            print(f"Error al cargar mensajes desde disco: {e}")

        return count