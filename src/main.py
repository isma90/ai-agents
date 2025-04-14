# src/main.py (actualizado con Pydantic)
import os
import time
import json
from datetime import datetime

from dotenv import load_dotenv
from src.core.config import AgentConfig
from src.core.models import RequirementsList
from src.agents.sme import SME
from src.agents.architect import Architect
from src.agents.developer import Developer


def main():
    try:
        load_dotenv()
        API_KEY = os.getenv("OPENAI_API_KEY")
        ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

        if not API_KEY:
            raise ValueError("No se encontró la clave API de OpenAI en las variables de entorno.")

        if not ANTHROPIC_API_KEY:
            raise ValueError("No se encontró la clave API de Anthropic en las variables de entorno.")

        # === Configuración base común para todos los agentes ===
        common_config = {
            "provider": "openai",
            "api_key": API_KEY,
            "model": "gpt-4o-mini",
            "verbose": True,
            "output_dir": "src/outputs"
        }

        # Inicializar agentes
        print("\nInicializando Agente SME...")
        sme = SME(config=AgentConfig(
            name="SME",
            prompt_path="src/prompts/sme.txt",
            **common_config
        ))

        print("\nInicializando Agente Solution Architect...")
        arquitecto = Architect(config=AgentConfig(
            name="Architect",
            prompt_path="src/prompts/architect.txt",
            **common_config
        ))

        print("\nInicializando Agente Developer (Claude 3 Sonnet)...")
        developer = Developer(config=AgentConfig(
            name="Developer",
            prompt_path="src/prompts/developer.txt",  # Esto ahora se usa como System Message
            provider="anthropic",
            api_key=ANTHROPIC_API_KEY,
            model="claude-3-5-sonnet-20241022",
            verbose=True,
            output_dir="src/outputs"
        ))

        # Definir el problema inicial
        descripcion_general = "Necesito un sitio web que sea una calculadora cientifica y que cada operación sea almacenada en la base de datos"

        # Ciclo de iteraciones (infinito hasta que el SME confirme que todos los requisitos están completos)
        iteracion_actual = 1
        MAX_ITERACIONES = 10  # Límite de seguridad para evitar bucles infinitos

        # Estructuras para llevar seguimiento de la evolución
        todos_los_requerimientos = RequirementsList()
        diseno_actual = []
        codigo_actual = []

        print(f"\n{'=' * 20} INICIANDO CICLO DE DESARROLLO COLABORATIVO {'=' * 20}")
        print(f"\nDescripción inicial del proyecto: {descripcion_general}")

        while True:
            print(f"\n{'=' * 20} ITERACIÓN {iteracion_actual} {'=' * 20}")

            # === Fase 1: SME genera requerimientos ===
            print(f"\n[Iteración {iteracion_actual}] SME analizando proyecto y generando requerimientos...")

            if iteracion_actual == 1:
                # Primera iteración usa la descripción inicial
                prompt_sme = f"""
                Analiza detalladamente la siguiente descripción de proyecto:

                "{descripcion_general}"

                Genera una lista completa de requerimientos funcionales estructurados.
                """

                # La respuesta ahora es un RequirementsList estructurado
                todos_los_requerimientos = sme.run(prompt_sme)

                print("\nRequerimientos identificados:")
                if len(todos_los_requerimientos) > 0:
                    for req in todos_los_requerimientos:
                        print(f"- {req.id}: {req.description} (Prioridad: {req.priority})")
                else:
                    print("No se identificaron requerimientos.")

                # Requerimientos pendientes para la primera iteración son todos
                requerimientos_pendientes = todos_los_requerimientos

            else:
                # Iteraciones posteriores: SME evalúa el código y verifica qué requerimientos están pendientes
                print("\nVerificando estado de los requerimientos...")
                todos_completos = sme.verificar_requerimientos(todos_los_requerimientos, codigo_actual)

                if todos_completos:
                    print("¡Todos los requerimientos han sido implementados correctamente!")
                    break

                # Obtener los requerimientos pendientes
                requerimientos_pendientes = RequirementsList()
                for req in todos_los_requerimientos:
                    if req.status != "Completo":
                        requerimientos_pendientes.add_requirement(req)

                print("\nRequerimientos pendientes/parciales:")
                for req in requerimientos_pendientes:
                    print(f"- {req.id}: {req.description} (Estado: {req.status})")

            # === Fase 2: Architect revisa diseño y lo adapta si es necesario ===
            print(f"\n[Iteración {iteracion_actual}] Architect revisando diseño para los requerimientos pendientes...")

            # Convertir los requerimientos pendientes a strings para mantener compatibilidad con Architect
            reqs_strings = [f"{req.id}: {req.description}" for req in requerimientos_pendientes]

            # Pasar los requerimientos al arquitecto
            diseno_actual = arquitecto.run(reqs_strings)

            # === Fase 3: Developer implementa de forma incremental ===
            print(f"\n[Iteración {iteracion_actual}] Developer implementando solución de forma incremental...")

            # Pasar los requerimientos y el diseño al desarrollador
            codigo_actual = developer.run(reqs_strings, diseno_actual)

            # Incrementar el contador de iteraciones
            iteracion_actual += 1

            # Verificar si se ha alcanzado el límite de iteraciones
            if iteracion_actual >= MAX_ITERACIONES:
                print(f"\n⚠️ Se ha alcanzado el límite máximo de {MAX_ITERACIONES} iteraciones.")
                print("El proceso se detendrá para evitar un bucle infinito.")
                break

            # Pequeña pausa para evitar límites de tasa de la API
            print("\nPreparando siguiente iteración...")
            time.sleep(2)

        # Al finalizar, guardar toda la información del proyecto en un archivo JSON
        print(f"\n{'=' * 20} DESARROLLO COMPLETADO {'=' * 20}")

        # Guardar el resumen del proyecto
        proyecto_info = {
            "descripcion": descripcion_general,
            "requerimientos": [
                {
                    "id": req.id,
                    "descripcion": req.description,
                    "prioridad": req.priority,
                    "estado": req.status
                } for req in todos_los_requerimientos
            ],
            "iteraciones_completadas": iteracion_actual - 1,
            "todos_requerimientos_completados": all(req.status == "Completo" for req in todos_los_requerimientos)
        }

        # Guardar el resumen en un archivo JSON
        resumen_path = os.path.join("src/outputs", f"resumen-proyecto-{datetime.now().strftime('%d%m%Y-%H%M%S')}.json")
        with open(resumen_path, "w", encoding="utf-8") as f:
            json.dump(proyecto_info, f, indent=2, ensure_ascii=False)

        print(f"\nResumen del proyecto guardado en: {resumen_path}")

        # Mostrar el código final
        print("\nCódigo final implementado:")
        for linea in codigo_actual:
            print(linea)

        print("\nEl proceso de desarrollo colaborativo ha finalizado exitosamente.")
        print(
            f"La solución final ha cumplido con {sum(1 for req in todos_los_requerimientos if req.status == 'Completo')} de {len(todos_los_requerimientos)} requerimientos.")

    except Exception as e:
        print(f"\nError durante la ejecución: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()