import openai
import os
from datetime import datetime

class DeveloperConfig:
    def __init__(self, model="text-davinci-003", verbose=True):
        self.model = model
        self.verbose = verbose


class Developer:
    def __init__(self, api_key: str, config: DeveloperConfig = DeveloperConfig()):
        """
        Inicializa el agente Developer con una clave API y la configuración para el modelo de OpenAI.
        El agente se encarga de generar las actividades de desarrollo y generar el código base para el backend y frontend.
        """
        self.api_key = api_key
        self.config = config
        openai.api_key = self.api_key
        self.nombre = "Developer"
        self.descripcion_rol = (
            "Eres un desarrollador experto que transforma las soluciones técnicas en código funcional "
            "y estructurado utilizando tecnologías modernas como TypeScript, NestJS, ReactJS, MaterialUI y TypeORM."
        )

    def __str__(self):
        """
        Devuelve una breve descripción del rol y el nombre del agente.
        """
        return f"{self.nombre}: {self.descripcion_rol}"

    def cargar_prompt(self, archivo_prompt: str) -> str:
        """
        Carga el contenido del prompt desde un archivo de texto.
        """
        with open(archivo_prompt, "r") as file:
            prompt = file.read()
        return prompt

    def definir_tareas(self, solucion_tecnica: str, archivo_prompt: str) -> list[str]:
        """
        Analiza la solución técnica y genera una lista detallada de tareas de desarrollo usando el prompt desde un archivo.
        """
        prompt = self.cargar_prompt(archivo_prompt)
        prompt = prompt.replace("{{solucion_tecnica}}", solucion_tecnica)
        
        response = openai.Completion.create(
            model=self.config.model,
            prompt=prompt,
            max_tokens=500,
            n=1,
            stop=None,
            temperature=0.5
        )
        
        tareas_texto = response.choices[0].text.strip()
        tareas = tareas_texto.split("\n")
        tareas = [tarea.strip() for tarea in tareas if tarea.strip()]
        
        return tareas

    def generar_codigo(self, tareas: list[str], archivo_prompt: str) -> str:
        """
        A partir de las tareas, genera el código base para el proyecto backend y frontend usando el prompt desde un archivo.
        """
        prompt = self.cargar_prompt(archivo_prompt)
        prompt = prompt.replace("{{tareas}}", "\n".join(tareas))
        
        response = openai.Completion.create(
            model=self.config.model,
            prompt=prompt,
            max_tokens=1000,
            n=1,
            stop=None,
            temperature=0.5
        )
        
        return response.choices[0].text.strip()

    def guardar_resultados(self, tareas: list[str], codigo: str) -> str:
        """
        Guarda las tareas de desarrollo y el código generado en un archivo con nombre versionado.
        """
        timestamp = datetime.now().strftime("%d%m%Y-%H%M%S")
        filename = f"developer-iteracion-{timestamp}.txt"
        
        with open(filename, "w") as f:
            f.write("Tareas de Desarrollo:\n")
            for tarea in tareas:
                f.write(f"- {tarea}\n")
            
            f.write("\nCódigo Generado:\n")
            f.write(codigo)
        
        return filename

    def procesar_solucion(self, solucion_tecnica: str, archivo_prompt: str) -> str:
        """
        Procesa la solución técnica, generando tareas y el código base para el proyecto.
        """
        tareas = self.definir_tareas(solucion_tecnica, archivo_prompt)
        codigo = self.generar_codigo(tareas, archivo_prompt)
        filename = self.guardar_resultados(tareas, codigo)
        
        return filename
