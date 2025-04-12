# src/agents/sme.py

import openai
import os
from datetime import datetime
from typing import List
from dataclasses import dataclass

@dataclass
class SMEConfig:
    model: str = "text-davinci-003"
    verbose: bool = True
    prompt_path: str = "src/prompts/sme.txt"
    output_dir: str = "src/outputs"

class SME:
    def __init__(self, nombre="SME", api_key=None, config: SMEConfig = SMEConfig()):
        self.nombre = nombre
        self.api_key = api_key
        self.config = config
        openai.api_key = self.api_key
        os.makedirs(self.config.output_dir, exist_ok=True)

    def __str__(self):
        return f"{self.nombre}: Generador de requerimientos funcionales"

    def _cargar_prompt(self, descripcion_general: str) -> str:
        with open(self.config.prompt_path, "r", encoding="utf-8") as f:
            template = f.read()
        return template.replace("{{descripcion}}", descripcion_general)

    def _guardar_resultado(self, requerimientos: List[str]) -> str:
        # Obtener el próximo ID de archivo
        existing_files = os.listdir(self.config.output_dir)
        ids = [
            int(f.replace("sme-id-", "").replace(".txt", ""))
            for f in existing_files
            if f.startswith("sme-id-") and f.endswith(".txt") and f.replace("sme-id-", "").replace(".txt", "").isdigit()
        ]
        next_id = max(ids) + 1 if ids else 1

        filename = f"sme-id-{next_id}.txt"
        filepath = os.path.join(self.config.output_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            for r in requerimientos:
                f.write(f"- {r}\n")
        
        if self.config.verbose:
            print(f"[{self.nombre}] 📝 Requerimientos guardados en {filepath}")
        
        return filepath


    def analizar_necesidad(self, descripcion_general: str) -> List[str]:
        if self.config.verbose:
            print(f"[{self.nombre}] Analizando: '{descripcion_general}'")

        prompt = self._cargar_prompt(descripcion_general)

        try:
            response = openai.Completion.create(
                model=self.config.model,
                prompt=prompt,
                max_tokens=300,
                n=1,
                stop=None,
                temperature=0.5
            )
        except Exception as e:
            print(f"[{self.nombre}] ❌ Error al comunicarse con OpenAI: {e}")
            return []

        texto = response.choices[0].text.strip()
        requerimientos = [line.strip("-• ") for line in texto.split("\n") if line.strip()]

        if self.config.verbose:
            print(f"[{self.nombre}] ✅ Requerimientos generados:")
            for r in requerimientos:
                print(f"  - {r}")

        self._guardar_resultado(requerimientos)
        return requerimientos
