# src/main.py
import os
from agents.sme import SME, SMEConfig
from agents.architect import Architect
from agents.developer import Developer, DeveloperConfig
from dotenv import load_dotenv


load_dotenv()
# Clave API de OpenAI
API_KEY = os.getenv("OPENAI_API_KEY")


if not API_KEY:
    raise ValueError("No se encontró la clave API de OpenAI en las variables de entorno.")
        

# Crear el agente SME
sme = SME(api_key=API_KEY, config=SMEConfig(model="text-davinci-003", verbose=True))

# Analizar una necesidad general
descripcion_general = "Necesitamos un sistema de gestión de usuarios para una aplicación web."
requerimientos = sme.analizar_necesidad(descripcion_general)

# Mostrar los requerimientos generados
print("\nRequerimientos Funcionales Generados:")
for req in requerimientos:
    print(f"- {req}")

# Crear el agente Arquitecto
arquitecto = Architect(api_key=API_KEY)

# Diseñar la solución técnica
solucion = arquitecto.diseñar_solucion(requerimientos)

# Mostrar resultado
print("\nSolución Técnica Generada:")
print(solucion)


# Crear el agente Developer
developer = Developer(api_key=API_KEY, config=DeveloperConfig(model="text-davinci-003", verbose=True))

# Generar el plan de desarrollo
plan = developer.generar_plan_de_desarrollo(solucion)

# Mostrar el plan de desarrollo generado
print("\nPlan de Desarrollo Generado:")
print(plan)