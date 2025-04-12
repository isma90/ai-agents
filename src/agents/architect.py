# src/agents/architect.py

import openai
import os
from datetime import datetime
from typing import List
from dataclasses import dataclass

@dataclass
class ArchitectConfig:
    model: str = "text-davinci-003"
    verbose: bool = True
    prompt_path: str = "src/prompts/architect.txt"
    output_dir: str = "src/outputs"

class Architect:
    def __init__(self, nombre="Arquitecto", api_key=None, config: ArchitectConfig = ArchitectConfig()):
        self.nombre = nombre
        self.api_key = api_key
        self.config = config
        openai.api_key = self.api_key
        os.makedirs(self.config.output_dir, exist_ok=True)

    def __str__(self):
        return f"{self.nombre}: Diseñador de soluciones técnicas"

    def _cargar_prompt(self, requerimientos: List[str]) -> str:
        with open(self.config.prompt_path, "r", encoding="utf-8") as f:
            template = f.read()
        lista = "\n".join(f"- {r}" for r in requerimientos)
        return template.replace("{{requerimientos}}", lista)

    def _guardar_resultado(self, resultado: str) -> str:
        archivos = os.listdir(self.config.output_dir)
        ids = [
            int(f.replace("architect-id-", "").replace(".txt", ""))
            for f in archivos
            if f.startswith("architect-id-") and f.endswith(".txt") and f.replace("architect-id-", "").replace(".txt", "").isdigit()
        ]
        next_id = max(ids) + 1 if ids else 1

        filename = f"architect-id-{next_id}.txt"
        filepath = os.path.join(self.config.output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(resultado)

        if self.config.verbose:
            print(f"[{self.nombre}] 📝 Solución técnica guardada en {filepath}")
        
        return filepath

    def diseñar_solucion(self, requerimientos: List[str]) -> str:
        if self.config.verbose:
            print(f"[{self.nombre}] Diseñando solución técnica...")

        prompt = self._cargar_prompt(requerimientos)

        try:
            response = openai.Completion.create(
                model=self.config.model,
                prompt=prompt,
                max_tokens=800,
                n=1,
                stop=None,
                temperature=0.5
            )
        except Exception as e:
            print(f"[{self.nombre}] ❌ Error al comunicarse con OpenAI: {e}")
            return ""

        resultado = response.choices[0].text.strip()

        print(f"[{self.nombre}] ✅ Solución generada.")
        self._guardar_resultado(resultado)
        return resultado
