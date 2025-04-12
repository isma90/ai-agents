# src/main.py
import os
import time
from dotenv import load_dotenv
from core.config import AgentConfig
from agents.sme import SME
from agents.architect import Architect
from agents.developer import Developer

def main():
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
        "output_dir": "outputs"
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

    print("\nInicializando Agente Developer...")
    developer = Developer(config=AgentConfig(
        name="Developer",
        prompt_path="src/prompts/developer.txt",
        **common_config
    ))

    # Definir el problema inicial
    descripcion_general = "Necesitamos crear un sitio web que sea una calculadora cientifica y que cada operación sea almacenada en la base de datos"
    
    # Ciclo de iteraciones
    ITERACIONES_TOTALES = 4
    iteracion_actual = 1
    
    # Variable para almacenar la última versión del código
    codigo_final = []
    
    print(f"\n{'='*20} INICIANDO CICLO DE DESARROLLO COLABORATIVO {'='*20}")
    print(f"\nDescripción inicial del proyecto: {descripcion_general}")
    
    while iteracion_actual <= ITERACIONES_TOTALES:
        print(f"\n{'='*20} ITERACIÓN {iteracion_actual}/{ITERACIONES_TOTALES} {'='*20}")
        
        # === Fase 1: SME genera requerimientos ===
        print(f"\n[Iteración {iteracion_actual}] SME analizando proyecto y generando requerimientos...")
        if iteracion_actual == 1:
            # Primera iteración usa la descripción inicial
            requerimientos = sme.run(descripcion_general)
        else:
            # Iteraciones posteriores usan el feedback del SME sobre la iteración anterior
            prompt_sme = f"""
            Estamos en la iteración {iteracion_actual} de {ITERACIONES_TOTALES} del proyecto.
            
            Descripción original: {descripcion_general}
            
            Código actual desarrollado:
            {'\n'.join(codigo_final)}
            
            Basado en la revisión del código actual, genera requerimientos funcionales refinados
            para la siguiente iteración. Enfócate en mejorar la solución existente y añadir cualquier
            requerimiento faltante.
            """
            requerimientos = sme.run(prompt_sme)
        
        # === Fase 2: Architect genera diseño ===
        print(f"\n[Iteración {iteracion_actual}] Architect diseñando solución técnica basada en requerimientos...")
        prompt_architect = f"""
        Estamos en la iteración {iteracion_actual} de {ITERACIONES_TOTALES} del proyecto.
        
        Requerimientos funcionales:
        {'\n'.join(requerimientos)}
        
        {'A continuación está el código de la iteración anterior que debes mejorar:' if iteracion_actual > 1 else ''}
        {'\n'.join(codigo_final) if iteracion_actual > 1 else ''}
        
        Diseña una solución técnica detallada que cumpla con estos requerimientos.
        """
        diseno = arquitecto.run(prompt_architect)
        
        # === Fase 3: Developer implementa la solución ===
        print(f"\n[Iteración {iteracion_actual}] Developer implementando la solución basada en diseño técnico...")
        prompt_developer = f"""
        Estamos en la iteración {iteracion_actual} de {ITERACIONES_TOTALES} del proyecto.
        
        Requerimientos funcionales:
        {'\n'.join(requerimientos)}
        
        Diseño técnico:
        {'\n'.join(diseno)}
        
        {'A continuación está el código de la iteración anterior que debes mejorar:' if iteracion_actual > 1 else ''}
        {'\n'.join(codigo_final) if iteracion_actual > 1 else ''}
        
        Implementa una solución completa y funcional que cumpla con los requerimientos y siga el diseño técnico.
        """
        codigo_final = developer.run(prompt_developer)
        
        # === Fase 4: SME evalúa la solución (feedback para la próxima iteración) ===
        if iteracion_actual < ITERACIONES_TOTALES:
            print(f"\n[Iteración {iteracion_actual}] SME evaluando la implementación para generar feedback...")
            prompt_evaluacion = f"""
            Evalúa la siguiente implementación y proporciona feedback detallado:
            
            Requerimientos originales:
            {'\n'.join(requerimientos)}
            
            Diseño técnico:
            {'\n'.join(diseno)}
            
            Implementación:
            {'\n'.join(codigo_final)}
            
            Por favor evalúa si la implementación cumple con los requerimientos y sigue el diseño técnico.
            Identifica problemas, áreas de mejora y sugerencias para la próxima iteración.
            """
            feedback = sme.run(prompt_evaluacion)
            print(f"\n[Iteración {iteracion_actual}] Feedback del SME: {feedback}")
        
        iteracion_actual += 1
        
        # Pequeña pausa para evitar límites de tasa de la API
        if iteracion_actual <= ITERACIONES_TOTALES:
            print("\nPreparando siguiente iteración...")
            time.sleep(2)
    
    print(f"\n{'='*20} DESARROLLO COMPLETADO {'='*20}")
    print("\nImplementación final:")
    for linea in codigo_final:
        print(linea)
    
    print("\nEl proceso de desarrollo colaborativo ha finalizado exitosamente.")
    print(f"La solución final ha pasado por {ITERACIONES_TOTALES} iteraciones de refinamiento.")

if __name__ == "__main__":
    main()