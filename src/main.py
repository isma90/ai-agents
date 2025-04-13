# src/main.py (actualizado)
import os
import time
import json
from dotenv import load_dotenv
from core.config import AgentConfig
from agents.sme import SME
from agents.architect import Architect
from agents.developer import Developer

def main():
    try:
        load_dotenv()
        API_KEY = os.getenv("OPENAI_API_KEY")
        if not API_KEY:
            raise ValueError("No se encontró la clave API de OpenAI en las variables de entorno.")

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
            prompt_path="src/prompts/developer.txt",
            provider="anthropic",
            api_key=os.getenv("ANTHROPIC_API_KEY"),  # Usar ANTHROPIC_API_KEY
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
        todos_los_requerimientos = []
        diseno_actual = []
        codigo_actual = []
        
        print(f"\n{'='*20} INICIANDO CICLO DE DESARROLLO COLABORATIVO {'='*20}")
        print(f"\nDescripción inicial del proyecto: {descripcion_general}")
        
        while True:
            print(f"\n{'='*20} ITERACIÓN {iteracion_actual} {'='*20}")
            
            # === Fase 1: SME genera requerimientos ===
            print(f"\n[Iteración {iteracion_actual}] SME analizando proyecto y generando requerimientos...")
            
            if iteracion_actual == 1:
                # Primera iteración usa la descripción inicial
                prompt_sme = f"""
                Analiza detalladamente la siguiente descripción de proyecto:
                
                "{descripcion_general}"
                
                Genera una lista completa de requerimientos funcionales, cada uno en una línea 
                con formato 'REQ-XX: [Descripción del requerimiento]'
                """
                requerimientos_respuesta = sme.run(prompt_sme)
                
                # Filtrar para obtener solo líneas que parecen requerimientos
                todos_los_requerimientos = [req for req in requerimientos_respuesta if req.startswith("REQ-")]
                
                # Si no se encontraron requerimientos con el formato REQ-XX, usar todas las líneas no vacías
                if not todos_los_requerimientos:
                    todos_los_requerimientos = [req for req in requerimientos_respuesta if req.strip()]
                
                requerimientos_faltantes = todos_los_requerimientos.copy()
                
                print("\nRequerimientos identificados:")
                if todos_los_requerimientos:
                    for req in todos_los_requerimientos:
                        print(f"- {req}")
                else:
                    print("No se identificaron requerimientos. Revisando el archivo de salida...")
                    # Leer el archivo de salida del SME para mostrar su contenido
                    output_files = [f for f in os.listdir("src/outputs") if f.startswith("sme-id-")]
                    if output_files:
                        latest_file = sorted(output_files)[-1]
                        with open(os.path.join("src/outputs", latest_file), "r", encoding="utf-8") as f:
                            content = f.read()
                            print("\nContenido del archivo de salida del SME:")
                            print(content)
                            # Extraer posibles requerimientos del contenido
                            lines = content.split("\n")
                            todos_los_requerimientos = [line.strip() for line in lines if line.strip()]
                            requerimientos_faltantes = todos_los_requerimientos.copy()
                
            else:
                # Iteraciones posteriores: SME evalúa el código y verifica si todos los requerimientos están completos
                print("\nVerificando si todos los requerimientos están completos...")
                todos_completos = sme.verificar_requerimientos(todos_los_requerimientos, codigo_actual)
                
                if todos_completos:
                    print("¡Todos los requerimientos han sido implementados correctamente!")
                    break
                    
                # Si no están todos completos, obtener los requerimientos faltantes
                requerimientos_faltantes = []
                for req in todos_los_requerimientos:
                    if not sme._confirmar_requerimientos_resueltos([req], codigo_actual):
                        requerimientos_faltantes.append(req)
                
                print("\nRequerimientos pendientes/parciales:")
                for req in requerimientos_faltantes:
                    print(f"- {req}")
            
            # === Fase 2: Architect revisa diseño y lo adapta si es necesario ===
            print(f"\n[Iteración {iteracion_actual}] Architect revisando diseño para los requerimientos pendientes...")
            
            # Pasar directamente los requerimientos al arquitecto
            diseno_actual = arquitecto.run(requerimientos_faltantes)
            
            # === Fase 3: Developer implementa de forma incremental ===
            print(f"\n[Iteración {iteracion_actual}] Developer implementando solución de forma incremental...")
            
            # Pasar los requerimientos y el diseño al desarrollador
            codigo_actual = developer.run(requerimientos_faltantes, diseno_actual)
            
            iteracion_actual += 1
            
            # Verificar si se ha alcanzado el límite de iteraciones
            if iteracion_actual >= MAX_ITERACIONES:
                print(f"\n⚠️ Se ha alcanzado el límite máximo de {MAX_ITERACIONES} iteraciones.")
                print("El proceso se detendrá para evitar un bucle infinito.")
                break
                
            # Pequeña pausa para evitar límites de tasa de la API
            print("\nPreparando siguiente iteración...")
            time.sleep(2)
        
        print(f"\n{'='*20} DESARROLLO COMPLETADO {'='*20}")
        print("\nCódigo final implementado:")
        for linea in codigo_actual:
            print(linea)
        
        print("\nEl proceso de desarrollo colaborativo ha finalizado exitosamente.")
        print(f"La solución final ha cumplido con todos los requerimientos especificados.")

    except Exception as e:
        print(f"\nError durante la ejecución: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
