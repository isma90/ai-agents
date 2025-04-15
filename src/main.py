# src/main.py (actualizado con sistema de mensajería)
import os
import time
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from src.core.config import AgentConfig
from src.core.models import RequirementsList
from src.core.messaging import SistemaMensajeria, Mensaje
from src.core.agent import Agent
from src.agents.sme import SME
from src.agents.architect import Architect
from src.agents.developer import Developer


def registrar_interaccion(mensaje):
    """Callback para registrar todas las interacciones entre agentes."""
    print(f"📩 Mensaje: {mensaje}")


def main():
    try:
        load_dotenv()
        API_KEY = os.getenv("OPENAI_API_KEY")
        ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

        if not API_KEY:
            raise ValueError("No se encontró la clave API de OpenAI en las variables de entorno.")

        if not ANTHROPIC_API_KEY:
            raise ValueError("No se encontró la clave API de Anthropic en las variables de entorno.")

        # Configurar el sistema de mensajería
        print("\nInicializando sistema de mensajería entre agentes...")
        mensajeria = SistemaMensajeria(ruta_almacenamiento="src/outputs/mensajes")

        # Configurar el sistema de mensajería para todos los agentes
        Agent.configurar_mensajeria(mensajeria)

        # Suscribirse a todos los mensajes para logging (opcional)
        if os.getenv("DEBUG_MENSAJES", "false").lower() == "true":
            mensajeria.suscribir("*", registrar_interaccion)

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
            api_key=ANTHROPIC_API_KEY,
            model="claude-3-7-sonnet-20250219",
            verbose=True,
            output_dir="src/outputs"
        ))

        # Inicializar los sistemas de mensajería de cada agente
        print("\nConfigurando capacidades de comunicación entre agentes...")
        sme.inicializar_mensajeria()
        arquitecto.inicializar_mensajeria()
        developer.inicializar_mensajeria()

        # Publicar mensaje de inicio del sistema
        mensajeria.publicar(
            Mensaje(
                emisor="Sistema",
                tipo="inicio",
                contenido="Sistema de desarrollo colaborativo iniciado",
                metadata={
                    "timestamp": datetime.now().isoformat(),
                    "version": "1.0.0"
                }
            )
        )

        # Definir el problema inicial
        descripcion_general = input(
            "\nDescribe el proyecto que deseas desarrollar (o presiona Enter para usar el ejemplo predeterminado): ")
        if not descripcion_general.strip():
            descripcion_general = "Necesito un sitio web que sea una calculadora científica y que cada operación sea almacenada en la base de datos"

        # Notificar a todos los agentes sobre el proyecto
        mensajeria.publicar(
            Mensaje(
                emisor="Sistema",
                tipo="nuevo_proyecto",
                contenido=f"Nuevo proyecto: {descripcion_general}",
                metadata={
                    "descripcion": descripcion_general
                }
            )
        )

        # Ciclo de iteraciones (infinito hasta que el SME confirme que todos los requisitos están completos)
        iteracion_actual = 1
        max_iteraciones = 10  # Límite de seguridad para evitar bucles infinitos

        # Estructuras para llevar seguimiento de la evolución
        todos_los_requerimientos = RequirementsList()
        diseno_actual = []
        codigo_actual = []

        print(f"\n{'=' * 20} INICIANDO CICLO DE DESARROLLO COLABORATIVO {'=' * 20}")
        print(f"\nDescripción inicial del proyecto: {descripcion_general}")

        while True:
            print(f"\n{'=' * 20} ITERACIÓN {iteracion_actual} {'=' * 20}")

            # Notificar inicio de iteración
            mensajeria.publicar(
                Mensaje(
                    emisor="Sistema",
                    tipo="inicio_iteracion",
                    contenido=f"Iniciando iteración {iteracion_actual}",
                    metadata={
                        "iteracion": iteracion_actual
                    }
                )
            )

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

                # Notificar requerimientos generados
                reqs_dict = [{"id": req.id, "descripcion": req.description, "prioridad": req.priority}
                             for req in todos_los_requerimientos]
                mensajeria.publicar(
                    Mensaje(
                        emisor="SME",
                        tipo="requerimientos_generados",
                        contenido=f"Generados {len(todos_los_requerimientos)} requerimientos",
                        metadata={
                            "requerimientos": reqs_dict
                        }
                    )
                )

                print("\nRequerimientos identificados:")
                if len(todos_los_requerimientos) > 0:
                    for req in todos_los_requerimientos:
                        print(f"- {req.id}: {req.description} (Prioridad: {req.priority})")
                else:
                    print("No se identificaron requerimientos.")

                # Requerimientos pendientes para la primera iteración son todos
                requerimientos_pendientes = todos_los_requerimientos

            else:
                # Iteraciones posteriores: SME evalúa el código revisando directamente el proyecto
                print("\nVerificando estado de los requerimientos...")

                # Verificar el proyecto directamente
                if developer.project_path and developer.project_path.exists():
                    print(f"[SME] Analizando código del proyecto en {developer.project_path}...")

                    # Notificar verificación
                    mensajeria.publicar(
                        Mensaje(
                            emisor="Sistema",
                            destinatario="SME",
                            tipo="solicitud_verificacion",
                            contenido=f"Verificar estado del proyecto en {developer.project_path}"
                        )
                    )

                    # Usar el nuevo método que verifica directamente el proyecto
                    todos_completos, estados_reqs = sme.verificar_requerimientos_proyecto(
                        todos_los_requerimientos,
                        developer.project_path
                    )

                    # Notificar resultados de verificación
                    mensajeria.publicar(
                        Mensaje(
                            emisor="SME",
                            tipo="resultado_verificacion",
                            contenido=f"Verificación completada: {len(estados_reqs)} requerimientos revisados",
                            metadata={
                                "todos_completos": todos_completos,
                                "estados": estados_reqs
                            }
                        )
                    )

                    # Mostrar el estado de cada requerimiento
                    if estados_reqs:
                        print("\nEstado detallado de los requerimientos:")
                        for estado in estados_reqs:
                            req_id = estado.get("id", "")
                            status = estado.get("status", "")
                            missing = estado.get("missing", "")

                            if status.upper() == "CUMPLIDO":
                                print(f"✅ {req_id}: {status}")
                            elif status.upper() == "PARCIAL":
                                print(f"⚠️ {req_id}: {status} - Falta: {missing[:50]}...")
                            else:
                                print(f"❌ {req_id}: {status}")
                else:
                    print("[SME] No se encontró un proyecto para verificar.")
                    # Usar el método antiguo si no hay proyecto
                    todos_completos = sme.verificar_requerimientos(todos_los_requerimientos, codigo_actual)

                if todos_completos:
                    print("¡Todos los requerimientos han sido implementados correctamente!")

                    # Notificar completitud
                    mensajeria.publicar(
                        Mensaje(
                            emisor="SME",
                            tipo="proyecto_completado",
                            contenido="Todos los requerimientos han sido implementados correctamente"
                        )
                    )

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

            # Notificar solicitud de diseño
            reqs_pendientes_dict = [{"id": req.id, "descripcion": req.description}
                                    for req in requerimientos_pendientes]
            mensajeria.publicar(
                Mensaje(
                    emisor="Sistema",
                    destinatario="Architect",
                    tipo="solicitud_diseno",
                    contenido=f"Diseñar solución para {len(requerimientos_pendientes)} requerimientos pendientes",
                    metadata={
                        "requerimientos": reqs_pendientes_dict
                    }
                )
            )

            # Convertir los requerimientos pendientes a strings para mantener compatibilidad con Architect
            reqs_strings = [f"{req.id}: {req.description}" for req in requerimientos_pendientes]

            # Pasar los requerimientos al arquitecto
            diseno_actual = arquitecto.run(reqs_strings)

            # Notificar diseño completado
            mensajeria.publicar(
                Mensaje(
                    emisor="Architect",
                    tipo="diseno_completado",
                    contenido=f"Diseño creado para {len(requerimientos_pendientes)} requerimientos pendientes",
                    metadata={
                        "diseno_length": len("\n".join(diseno_actual)) if isinstance(diseno_actual, list) else len(
                            diseno_actual)
                    }
                )
            )

            # === Fase 3: Developer implementa de forma incremental ===
            print(f"\n[Iteración {iteracion_actual}] Developer implementando solución de forma incremental...")

            # Notificar solicitud de implementación
            mensajeria.publicar(
                Mensaje(
                    emisor="Sistema",
                    destinatario="Developer",
                    tipo="solicitud_implementacion",
                    contenido=f"Implementar solución según diseño para {len(requerimientos_pendientes)} requerimientos",
                    metadata={
                        "requerimientos": reqs_pendientes_dict,
                        "diseno_disponible": True
                    }
                )
            )

            # Pasar los requerimientos y el diseño al desarrollador
            # Ahora devuelve un resumen de lo actualizado
            resumen_implementacion = developer.run(reqs_strings, diseno_actual)

            # Notificar implementación completada
            mensajeria.publicar(
                Mensaje(
                    emisor="Developer",
                    tipo="implementacion_completada",
                    contenido=f"Implementación completada para iteración {iteracion_actual}",
                    metadata={
                        "proyecto_path": str(developer.project_path) if developer.project_path else "No disponible"
                    }
                )
            )

            # Guardar este resumen para el registro
            codigo_actual = resumen_implementacion

            # Incrementar el contador de iteraciones
            iteracion_actual += 1

            # Verificar si se ha alcanzado el límite de iteraciones
            if iteracion_actual >= max_iteraciones:
                print(f"\n⚠️ Se ha alcanzado el límite máximo de {max_iteraciones} iteraciones.")
                print("El proceso se detendrá para evitar un bucle infinito.")

                # Notificar finalización por límite
                mensajeria.publicar(
                    Mensaje(
                        emisor="Sistema",
                        tipo="limite_iteraciones",
                        contenido=f"Se alcanzó el límite de {max_iteraciones} iteraciones",
                        metadata={
                            "razon": "limite_seguridad"
                        }
                    )
                )

                break

            # Pequeña pausa para evitar límites de tasa de la API
            print("\nPreparando siguiente iteración...")
            time.sleep(2)

        # Al finalizar, guardar toda la información del proyecto en un archivo JSON
        print(f"\n{'=' * 20} DESARROLLO COMPLETADO {'=' * 20}")

        # Crear un resumen detallado del proyecto final
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        resumen_final_path = Path(f"src/outputs/RESUMEN-FINAL-{timestamp}.md")

        with open(resumen_final_path, "w", encoding="utf-8") as f:
            f.write(f"# Resumen Final del Proyecto\n\n")
            f.write(f"## Descripción\n{descripcion_general}\n\n")

            f.write(f"## Requerimientos\n")
            for req in todos_los_requerimientos:
                emoji = "✅" if req.status == "Completo" else "⚠️" if req.status == "Parcial" else "❌"
                f.write(f"{emoji} **{req.id}** ({req.status}): {req.description}\n")

            f.write(f"\n## Estadísticas\n")
            total_reqs = len(todos_los_requerimientos)
            completos = sum(1 for req in todos_los_requerimientos if req.status == "Completo")
            parciales = sum(1 for req in todos_los_requerimientos if req.status == "Parcial")
            pendientes = sum(1 for req in todos_los_requerimientos if req.status == "Pendiente")

            f.write(f"- **Total de requerimientos:** {total_reqs}\n")
            f.write(f"- **Completados:** {completos} ({completos / total_reqs * 100:.1f}%)\n")
            f.write(f"- **Parciales:** {parciales} ({parciales / total_reqs * 100:.1f}%)\n")
            f.write(f"- **Pendientes:** {pendientes} ({pendientes / total_reqs * 100:.1f}%)\n")
            f.write(f"- **Iteraciones realizadas:** {iteracion_actual - 1}\n")

            f.write(f"\n## Ubicación del proyecto\n")
            f.write(f"El código completo se encuentra en: `{developer.project_path}`\n")

            f.write(f"\n## Estadísticas de comunicación\n")
            total_mensajes = len(mensajeria.mensajes)
            mensajes_por_tipo = {}
            for m in mensajeria.mensajes:
                if m.tipo not in mensajes_por_tipo:
                    mensajes_por_tipo[m.tipo] = 0
                mensajes_por_tipo[m.tipo] += 1

            f.write(f"- **Total de mensajes intercambiados:** {total_mensajes}\n")
            f.write(f"- **Desglose por tipo:**\n")
            for tipo, count in mensajes_por_tipo.items():
                f.write(f"  - {tipo}: {count}\n")

            f.write(f"\n## Fecha de finalización\n")
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # Guardar también el resumen en formato JSON
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
            "estadisticas": {
                "total": total_reqs,
                "completados": completos,
                "parciales": parciales,
                "pendientes": pendientes,
                "porcentaje_completado": round(completos / total_reqs * 100, 1)
            },
            "comunicacion": {
                "total_mensajes": total_mensajes,
                "por_tipo": mensajes_por_tipo
            },
            "iteraciones_completadas": iteracion_actual - 1,
            "todos_requerimientos_completados": all(req.status == "Completo" for req in todos_los_requerimientos),
            "ubicacion_proyecto": str(developer.project_path) if developer.project_path else "No disponible"
        }

        # Guardar el resumen en un archivo JSON
        resumen_json_path = os.path.join("src/outputs", f"resumen-proyecto-{timestamp}.json")
        with open(resumen_json_path, "w", encoding="utf-8") as f:
            json.dump(proyecto_info, f, indent=2, ensure_ascii=False)

        # Notificar finalización del proyecto
        mensajeria.publicar(
            Mensaje(
                emisor="Sistema",
                tipo="proyecto_finalizado",
                contenido=f"Proyecto finalizado con {completos}/{total_reqs} requerimientos completos",
                metadata={
                    "resumen_path": str(resumen_final_path),
                    "json_path": resumen_json_path,
                    "porcentaje_completado": round(completos / total_reqs * 100, 1)
                }
            )
        )

        print(f"\nResumen del proyecto guardado en: {resumen_final_path}")
        print(f"Datos JSON guardados en: {resumen_json_path}")

        # Mostrar el resumen de la implementación
        print("\nResumen de la implementación:")
        for linea in resumen_implementacion:
            print(linea)

        # Mostrar información sobre donde encontrar los archivos
        if developer.project_path:
            print(f"\n📁 El proyecto completo se encuentra en: {developer.project_path}")

            # Verificar si existe el README.md
            readme_path = developer.project_path / "README.md"
            if readme_path.exists():
                print("   Revisa el archivo README.md para instrucciones de instalación y ejecución.")

            # Verificar si existe el HISTORIAL.md
            historial_path = developer.project_path / "HISTORIAL.md"
            if historial_path.exists():
                print("   Revisa el archivo HISTORIAL.md para ver el progreso de todas las iteraciones.")

        print("\nEl proceso de desarrollo colaborativo ha finalizado exitosamente.")
        print(
            f"La solución final ha cumplido con {completos} de {total_reqs} requerimientos ({completos / total_reqs * 100:.1f}%).")
        print(f"Se intercambiaron {total_mensajes} mensajes entre los agentes durante el proceso.")

    except Exception as e:
        print(f"\nError durante la ejecución: {e}")

        # Notificar error
        if 'mensajeria' in locals():
            mensajeria.publicar(
                Mensaje(
                    emisor="Sistema",
                    tipo="error",
                    contenido=f"Error durante la ejecución: {str(e)}",
                    metadata={
                        "error": str(e),
                        "traceback": __import__("traceback").format_exc()
                    }
                )
            )

        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()