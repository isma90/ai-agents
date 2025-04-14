# src/agents/developer.py
from typing import List
from src.core.agent import AnthropicAgent


class Developer(AnthropicAgent):
    def run(self, requerimientos_funcionales: List[str], diseno_tecnico: List[str]) -> List[str]:
        """
        Ejecuta el agente Developer, implementando código basado en los requerimientos y el diseño.

        Args:
            requerimientos_funcionales: Lista de requerimientos funcionales a implementar.
            diseno_tecnico: Lista de líneas del diseño técnico.

        Returns:
            List[str]: Lista de líneas de código implementado.
        """
        iteration_id = self._generate_iteration_id()

        # Verificar que los requerimientos y el diseño no estén vacíos
        if not requerimientos_funcionales:
            error_msg = "No se proporcionaron requerimientos funcionales."
            print(f"[{self.config.name}] ⚠️ {error_msg}")
            self._save_output(error_msg, iteration_id)
            return [error_msg]

        if not diseno_tecnico:
            error_msg = "No se proporcionó un diseño técnico."
            print(f"[{self.config.name}] ⚠️ {error_msg}")
            self._save_output(error_msg, iteration_id)
            return [error_msg]

        # Formatear los requerimientos y el diseño como texto
        requerimientos_texto = "\n".join([f"- {req}" for req in requerimientos_funcionales])
        diseno_texto = "\n".join(diseno_tecnico)

        if self.config.verbose:
            print(
                f"[{self.config.name}] Generando implementación para {len(requerimientos_funcionales)} requerimientos...")

        # Construimos el mensaje para el usuario con los requisitos y el diseño
        user_message = f"""
        Necesito implementar código que cumpla con los siguientes requerimientos funcionales:

        {requerimientos_texto}

        El diseño técnico propuesto es el siguiente:

        {diseno_texto}

        Por favor, proporciona una implementación completa y funcional que cumpla con estos requerimientos.
        Devuelve únicamente el código implementado, organizado en archivos según sea necesario.
        """

        # Configuramos max_tokens para respuestas largas
        max_tokens = 8000

        # Utilizamos AnthropicAgent que ya establece el prompt_template como system
        # y enviamos el mensaje del usuario con los requerimientos y diseño
        response = super().run(message=user_message, max_tokens=max_tokens)

        # Guardar la salida
        self._save_output(response, iteration_id)

        # Convertir la respuesta en una lista de líneas
        return [r.strip() for r in response.split("\n") if r.strip()]

    def __str__(self):
        return f"{self.config.name}: Desarrollador de implementaciones"