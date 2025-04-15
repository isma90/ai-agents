# src/agents/developer.py
import os
import re
from typing import List, Dict, Tuple
from pathlib import Path
from datetime import datetime

from core.messaging import Mensaje
from src.core.agent import AnthropicAgent


class Developer(AnthropicAgent):
    def __init__(self, *args, **kwargs):
        """
        Inicializa el agente Developer.

        Extiende la inicialización de AnthropicAgent y agrega atributos específicos para el Developer.
        """
        super().__init__(*args, **kwargs)

        # Inicializar atributos específicos del Developer
        self.project_path = Path(self.config.output_dir) / "proyecto"
        self.iteration_count = 0

        if self.config.verbose:
            print(f"[{self.config.name}] Inicializado. Ruta del proyecto: {self.project_path}")

    def run(self, requerimientos_funcionales: List[str], diseno_tecnico: List[str]) -> List[str]:
        """
        Ejecuta el agente Developer, implementando código basado en los requerimientos y el diseño.

        Args:
            requerimientos_funcionales: Lista de requerimientos funcionales a implementar.
            diseno_tecnico: Lista de líneas del diseño técnico.

        Returns:
            List[str]: Lista de líneas de resumen de la implementación.
        """
        # Verificar que los atributos importantes estén inicializados
        if not hasattr(self, 'project_path') or self.project_path is None:
            self.project_path = Path(self.config.output_dir) / "proyecto"
            if self.config.verbose:
                print(f"[{self.config.name}] Inicializando ruta del proyecto: {self.project_path}")

        if not hasattr(self, 'iteration_count'):
            self.iteration_count = 0

        # Generar ID de iteración
        iteration_id = self._generate_iteration_id()

        # Incrementar el contador de iteraciones
        self.iteration_count += 1

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

        if self.config.verbose:
            print(
                f"[{self.config.name}] Generando implementación (Iteración {self.iteration_count}) para {len(requerimientos_funcionales)} requerimientos...")

        # Obtenemos el estado actual del proyecto si existe
        estado_actual = self._obtener_estado_actual_proyecto()

        # Construimos el mensaje para el modelo
        user_message = self._construir_mensaje_implementacion(
            requerimientos_funcionales,
            diseno_tecnico,
            estado_actual
        )

        # Configuramos max_tokens para respuestas largas
        max_tokens = 12000

        try:
            # Utilizamos AnthropicAgent que ya establece el prompt_template como system
            # y enviamos el mensaje del usuario con los requerimientos y diseño
            response = super().run(message=user_message, max_tokens=max_tokens)

            # Procesar la respuesta para extraer los archivos y la documentación
            documentacion, instrucciones, estructura, cambios, archivos = self._procesar_respuesta(response)

            # Actualizar la estructura del proyecto
            resumen = self._actualizar_proyecto(documentacion, instrucciones, estructura, cambios, archivos,
                                                iteration_id)

            # Guardar también la respuesta original completa para referencia
            self._save_output(response, f"{iteration_id}-respuesta-completa")

            # Si el sistema de mensajería está disponible, notificar éxito
            if hasattr(self, '_sistema_mensajeria') and self._sistema_mensajeria:
                archivos_info = [{"ruta": a["ruta"], "es_nuevo": not (self.project_path / a["ruta"]).exists()} for a in
                                 archivos]
                self._sistema_mensajeria.publicar(
                    Mensaje(
                        emisor=self.config.name,
                        tipo="implementacion_exitosa",
                        contenido=f"Implementación exitosa en iteración {self.iteration_count}",
                        metadata={
                            "archivos_procesados": len(archivos),
                            "archivos_info": archivos_info,
                            "proyecto_path": str(self.project_path) if self.project_path else None
                        }
                    )
                )

            return resumen

        except Exception as e:
            error_msg = f"Error durante la implementación: {str(e)}"
            print(f"[{self.config.name}] ⚠️ {error_msg}")

            # Si el sistema de mensajería está disponible, notificar error
            if hasattr(self, '_sistema_mensajeria') and self._sistema_mensajeria:
                self._sistema_mensajeria.publicar(
                    Mensaje(
                        emisor=self.config.name,
                        tipo="error_implementacion",
                        contenido=error_msg,
                        metadata={
                            "error": str(e),
                            "iteracion": self.iteration_count
                        }
                    )
                )

            # Crear un mensaje de error como resumen
            self._save_output(f"Error: {error_msg}\n\nDetalles del error: {str(e)}", f"{iteration_id}-error")
            return [error_msg]

    def _obtener_estado_actual_proyecto(self) -> str:
        """
        Obtiene el estado actual del proyecto listando archivos y su contenido.

        Returns:
            str: Descripción del estado actual del proyecto
        """
        if not self.project_path or not self.project_path.exists():
            return ""

        resultado = ["\nEstructura de archivos existente:"]

        # Listar archivos encontrados
        archivos_encontrados = []
        for ruta in self.project_path.glob("**/*"):
            if ruta.is_file():
                # Ruta relativa al directorio del proyecto
                ruta_relativa = ruta.relative_to(self.project_path)
                archivos_encontrados.append(str(ruta_relativa))

        # Ordenar para mejor presentación
        archivos_encontrados.sort()

        # Agregar al resultado
        for archivo in archivos_encontrados:
            resultado.append(f"- {archivo}")

        # Incluir contenido de algunos archivos importantes
        resultado.append("\nContenido de archivos clave:")
        archivos_clave = [
            "README.md",
            "frontend/package.json",
            "backend/package.json",
            "frontend/src/App.js",
            "frontend/src/index.js",
            "frontend/src/App.jsx",
            "frontend/src/index.jsx",
            "backend/app.py",
            "backend/server.js",
            "backend/index.js"
        ]

        # Limitamos la cantidad de archivos para no exceder el contexto
        archivos_a_incluir = []
        for archivo_clave in archivos_clave:
            ruta_completa = self.project_path / archivo_clave
            if ruta_completa.exists() and ruta_completa.is_file():
                archivos_a_incluir.append(archivo_clave)

        # Incluir otros archivos importantes que puedan existir pero no estén en la lista anterior
        for archivo in archivos_encontrados:
            if len(archivos_a_incluir) >= 10:  # Limitar a 10 archivos
                break

            # Incluir archivos principales como index.html, etc.
            if archivo not in archivos_a_incluir and any(
                    nombre in archivo.lower() for nombre in ["index", "main", "app", "config"]):
                archivos_a_incluir.append(archivo)

        # Leer y agregar el contenido de los archivos seleccionados
        for archivo in archivos_a_incluir:
            ruta_completa = self.project_path / archivo
            try:
                with open(ruta_completa, "r", encoding="utf-8") as f:
                    contenido = f.read()

                extension = ruta_completa.suffix.lstrip('.')
                if not extension:
                    extension = ""

                resultado.append(f"\n### {archivo}")
                resultado.append(f"```{extension}")
                resultado.append(contenido)
                resultado.append("```")
            except Exception as e:
                resultado.append(f"\n### {archivo}")
                resultado.append(f"Error al leer el archivo: {str(e)}")

        return "\n".join(resultado)

    def _procesar_respuesta(self, response: str) -> Tuple[str, str, str, str, List[Dict]]:
        """
        Procesa la respuesta del modelo para extraer las secciones y los archivos.

        Args:
            response: Respuesta completa del modelo.

        Returns:
            Tuple con: documentación, instrucciones, estructura, cambios, y lista de archivos.
        """
        # Extraer las secciones principales
        documentacion = ""
        instrucciones = ""
        estructura = ""
        cambios = ""
        archivos = []

        # Buscar la sección de DOCUMENTACIÓN
        doc_match = re.search(r'#+\s*DOCUMENTACIÓN\s*\n(.*?)(?=#+\s*INSTRUCCIONES|\Z)', response, re.DOTALL)
        if doc_match:
            documentacion = doc_match.group(1).strip()

        # Buscar la sección de INSTRUCCIONES
        inst_match = re.search(r'#+\s*INSTRUCCIONES\s*\n(.*?)(?=#+\s*ESTRUCTURA|\Z)', response, re.DOTALL)
        if inst_match:
            instrucciones = inst_match.group(1).strip()

        # Buscar la sección de ESTRUCTURA
        estruct_match = re.search(r'#+\s*ESTRUCTURA\s*\n(.*?)(?=#+\s*CAMBIOS|\Z)', response, re.DOTALL)
        if estruct_match:
            estructura = estruct_match.group(1).strip()

        # Buscar la sección de CAMBIOS REALIZADOS
        cambios_match = re.search(r'#+\s*CAMBIOS REALIZADOS[^#]*\n(.*?)(?=#+\s*ARCHIVOS|\Z)', response, re.DOTALL)
        if cambios_match:
            cambios = cambios_match.group(1).strip()

        # Extraer los archivos
        # Patrón para buscar definiciones de archivos: ### path/to/file.ext seguido de un bloque de código
        archivo_pattern = r'###\s+([\w/.-]+)\s*\n```(?:(\w*))?\n(.*?)```'
        for match in re.finditer(archivo_pattern, response, re.DOTALL):
            ruta_archivo = match.group(1).strip()
            lenguaje = match.group(2) or ""
            contenido = match.group(3)

            archivos.append({
                "ruta": ruta_archivo,
                "contenido": contenido,
                "lenguaje": lenguaje
            })

        # Si no se encontraron archivos con el formato esperado, intentar otros patrones alternativos
        if not archivos:
            # Buscar patrones alternativos
            alt_patterns = [
                # Comentario HTML encima del bloque de código
                r'<!--\s*([\w/.-]+)\s*-->\s*```(?:\w*)\n(.*?)```',
                # Comentario con // encima del bloque de código
                r'//\s*([\w/.-]+)\s*\n```(?:\w*)\n(.*?)```',
                # Texto plano indicando archivo
                r'Archivo:\s*([\w/.-]+)\s*\n```(?:\w*)\n(.*?)```',
                # Buscar código de cualquier bloque y tratar de inferir el nombre del archivo
                r'```(\w+)\n(.*?)```'
            ]

            for pattern in alt_patterns:
                for match in re.finditer(pattern, response, re.DOTALL):
                    if len(match.groups()) >= 2:
                        # Caso normal: nombre de archivo + contenido
                        ruta_archivo = match.group(1).strip()
                        contenido = match.group(2)
                        lenguaje = ""
                    else:
                        # Caso de inferencia: solo tenemos lenguaje + contenido
                        lenguaje = match.group(1)
                        contenido = match.group(2)
                        # Inferir nombre de archivo basado en lenguaje o contenido
                        if lenguaje == "js" or lenguaje == "javascript":
                            ruta_archivo = "script.js"
                        elif lenguaje == "py" or lenguaje == "python":
                            ruta_archivo = "app.py"
                        elif lenguaje == "html":
                            ruta_archivo = "index.html"
                        elif lenguaje == "css":
                            ruta_archivo = "styles.css"
                        else:
                            ruta_archivo = f"file.{lenguaje}"

                    archivos.append({
                        "ruta": ruta_archivo,
                        "contenido": contenido,
                        "lenguaje": lenguaje
                    })

                # Si encontramos archivos con este patrón, dejamos de buscar
                if archivos:
                    break

        return documentacion, instrucciones, estructura, cambios, archivos

    def _actualizar_proyecto(self, documentacion: str, instrucciones: str, estructura: str,
                             cambios: str, archivos: List[Dict], iteration_id: str) -> List[str]:
        """
        Actualiza los archivos del proyecto con la nueva implementación.

        Args:
            documentacion: Documentación del proyecto
            instrucciones: Instrucciones de instalación y ejecución
            estructura: Descripción de la estructura de archivos
            cambios: Descripción de los cambios realizados en esta iteración
            archivos: Lista de diccionarios con ruta y contenido de cada archivo
            iteration_id: ID de la iteración

        Returns:
            List[str]: Resumen de lo actualizado
        """
        # Verificar si project_path está inicializado, si no, inicializarlo
        if not hasattr(self, 'project_path') or self.project_path is None:
            from pathlib import Path
            self.project_path = Path(self.config.output_dir) / "proyecto"
            if self.config.verbose:
                print(f"[{self.config.name}] Inicializando proyecto en: {self.project_path}")

        # Asegurarse de que el directorio base del proyecto exista
        self.project_path.mkdir(parents=True, exist_ok=True)

        resumen = []
        resumen.append(f"Iteración #{getattr(self, 'iteration_count', 1)} - Actualización del proyecto")
        resumen.append(f"Proyecto: {self.project_path}")

        # Crear o actualizar README.md con la documentación
        if documentacion:
            readme_content = f"""# Proyecto

            ## Documentación
            {documentacion}
        
            ## Instrucciones de Instalación y Ejecución
            {instrucciones}
        
            ## Estructura del Proyecto
            {estructura}
        
            ---
            Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            Generado por {self.config.name}
            """

            readme_path = self.project_path / "README.md"
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(readme_content)

            resumen.append(f"✅ Documentación actualizada en README.md")

        # Guardar los cambios de esta iteración
        if cambios:
            cambios_path = self.project_path / f"CAMBIOS-{iteration_id}.md"
            with open(cambios_path, "w", encoding="utf-8") as f:
                f.write(f"# Cambios realizados en la iteración {getattr(self, 'iteration_count', 1)}\n\n")
                f.write(cambios)

            resumen.append(f"✅ Registro de cambios guardado en {cambios_path.name}")

        # Contadores para estadísticas
        archivos_creados = 0
        archivos_actualizados = 0

        # Guardar cada archivo en su ubicación
        for archivo in archivos:
            ruta = archivo["ruta"].strip().lstrip("/")  # Eliminar "/" inicial si existe

            # Determinar si es frontend o backend basado en la ruta o extensión
            if not (ruta.startswith(("frontend/", "backend/", "client/", "server/", "api/", "public/", "src/"))):
                extension = ruta.split(".")[-1] if "." in ruta else ""

                # Si no tiene un directorio específico, determinar automáticamente
                if extension in ["html", "css", "js", "jsx", "ts", "tsx", "vue", "svelte"]:
                    ruta = f"frontend/{ruta}"
                elif extension in ["py", "java", "php", "rb", "go"]:
                    ruta = f"backend/{ruta}"

            # Crear directorios si no existen
            file_path = self.project_path / ruta
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Verificar si es una creación o actualización
            es_nuevo = not file_path.exists()

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(archivo["contenido"])

            if es_nuevo:
                archivos_creados += 1
            else:
                archivos_actualizados += 1

        resumen.append(f"✅ Procesados {len(archivos)} archivos:")
        resumen.append(f"   - {archivos_creados} archivos nuevos creados")
        resumen.append(f"   - {archivos_actualizados} archivos existentes actualizados")

        # Guardar un registro de esta iteración
        iteracion_path = self.project_path / "HISTORIAL.md"

        # Leer contenido existente si lo hay
        historial_previo = ""
        if iteracion_path.exists():
            with open(iteracion_path, "r", encoding="utf-8") as f:
                historial_previo = f.read()

        # Actualizar el historial
        with open(iteracion_path, "w", encoding="utf-8") as f:
            f.write(f"# Historial de Iteraciones\n\n")

            # Agregar nueva entrada
            f.write(
                f"## Iteración {getattr(self, 'iteration_count', 1)} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"\n### Cambios realizados\n")
            f.write(f"{cambios}\n\n")
            f.write(f"### Estadísticas\n")
            f.write(f"- Archivos procesados: {len(archivos)}\n")
            f.write(f"- Archivos nuevos: {archivos_creados}\n")
            f.write(f"- Archivos actualizados: {archivos_actualizados}\n\n")
            f.write(f"---\n\n")

            # Agregar historial previo sin el encabezado
            if historial_previo:
                # Eliminar el encabezado "# Historial de Iteraciones" del historial previo
                historial_sin_titulo = re.sub(r'^# Historial de Iteraciones\s*\n+', '', historial_previo)
                f.write(historial_sin_titulo)

        resumen.append(f"\nHistorial de iteraciones actualizado en HISTORIAL.md")
        resumen.append(f"\nEl proyecto se encuentra en: {self.project_path}")

        # También guardar el resumen en la carpeta de outputs
        self._save_output("\n".join(resumen), f"{iteration_id}-resumen")

        return resumen

    def _save_output(self, content: str, iteration_id: str) -> str:
        """
        Guarda la salida en un archivo de texto.
        Sobrescribe el método de la clase base para usar formato Markdown.

        Args:
            content: Contenido a guardar
            iteration_id: ID de la iteración

        Returns:
            str: Ruta al archivo guardado
        """
        Path(self.config.output_dir).mkdir(parents=True, exist_ok=True)
        filename = f"{self.config.name.lower()}-{iteration_id}.md"
        full_path = os.path.join(self.config.output_dir, filename)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        if self.config.verbose:
            print(f"[{self.config.name}] Resultado guardado en: {full_path}")
        return full_path

    def __str__(self):
        return f"{self.config.name}: Desarrollador de implementaciones"

    def inicializar_mensajeria(self):
        """Configura el sistema de mensajería para este agente."""
        # Registrar handlers para tipos específicos de mensajes
        self.registrar_callback("consulta", self.manejar_consulta)
        self.registrar_callback("implementar_codigo", self.implementar_codigo)
        self.registrar_callback("corregir_codigo", self.corregir_codigo)
        self.registrar_callback("solicitud_mejora", self.mejorar_implementacion)
        self.registrar_callback("revision_arquitectura", self.ajustar_arquitectura)

        if self.config.verbose:
            print(f"[{self.config.name}] Sistema de mensajería inicializado")

    def manejar_consulta(self, mensaje):
        """Maneja consultas generales de otros agentes."""
        if self.config.verbose:
            print(f"[{self.config.name}] Recibida consulta de {mensaje.emisor}: {mensaje.contenido[:50]}...")

        # Determinar el tipo de consulta
        contenido = mensaje.contenido.lower()

        if "implementa" in contenido or "desarrolla" in contenido or "crea código" in contenido:
            return self.implementar_codigo(mensaje)
        elif "corrige" in contenido or "arregla" in contenido or "soluciona error" in contenido:
            return self.corregir_codigo(mensaje)
        elif "mejora" in contenido or "optimiza" in contenido:
            return self.mejorar_implementacion(mensaje)
        else:
            # Consulta general sobre desarrollo
            respuesta = self.run([mensaje.contenido], ["Consulta general de desarrollo"])
            return respuesta[0] if isinstance(respuesta, list) else respuesta

    def implementar_codigo(self, mensaje):
        """
        Implementa código basado en requerimientos y/o diseño.

        Args:
            mensaje: Mensaje con la solicitud de implementación

        Returns:
            Código implementado como texto
        """
        contenido = mensaje.contenido

        # Extraer requerimientos si están presentes
        reqs_block = re.search(r'REQUERIMIENTOS:?\s*(.*?)(?=\n\n|$)', contenido, re.DOTALL)
        reqs = reqs_block.group(1).strip() if reqs_block else ""

        # Extraer diseño si está presente
        diseno_block = re.search(r'DISEÑO:?\s*(.*?)(?=\n\n|$)', contenido, re.DOTALL)
        diseno = diseno_block.group(1).strip() if diseno_block else ""

        # Si no hay requerimientos ni diseño, usar todo el contenido como solicitud general
        if not reqs and not diseno:
            solicitud = contenido
        else:
            solicitud = f"""
            Implementar código basado en:

            {f'REQUERIMIENTOS:\n{reqs}\n\n' if reqs else ''}
            {f'DISEÑO:\n{diseno}\n\n' if diseno else ''}
            """

        # Usar el método run adaptado para el formato de lista
        reqs_lista = [r.strip() for r in reqs.split('\n') if r.strip()]
        diseno_lista = [d.strip() for d in diseno.split('\n') if d.strip()]

        # Si no hay listas, usar el contenido completo
        if not reqs_lista and not diseno_lista:
            reqs_lista = [solicitud]
            diseno_lista = []

        respuesta = self.run(reqs_lista, diseno_lista)

        # Convertir a string si es una lista
        if isinstance(respuesta, list):
            respuesta = "\n".join(respuesta)

        # Registrar esta interacción con metadatos
        if self._sistema_mensajeria:
            self._sistema_mensajeria.publicar(
                Mensaje(
                    emisor=self.config.name,
                    tipo="registro_implementacion",
                    contenido=f"Código implementado para {mensaje.emisor}",
                    metadata={
                        "solicitante": mensaje.emisor,
                        "requerimientos_count": len(reqs_lista) if reqs_lista else 0,
                        "diseno_length": len(diseno) if diseno else 0,
                        "respuesta_length": len(respuesta)
                    }
                )
            )

        return respuesta

    def corregir_codigo(self, mensaje):
        """
        Corrige errores en código existente.

        Args:
            mensaje: Mensaje con la solicitud de corrección

        Returns:
            Código corregido como texto
        """
        contenido = mensaje.contenido

        # Extraer el código a corregir
        codigo_block = re.search(r'```[\w]*\n(.*?)```', contenido, re.DOTALL)
        codigo = codigo_block.group(1) if codigo_block else ""

        # Extraer la descripción del error si está presente
        error_block = re.search(r'ERROR:?\s*(.*?)(?=\n\n|$)', contenido, re.DOTALL)
        error = error_block.group(1).strip() if error_block else ""

        # Si no hay código explícito, buscar la descripción del código
        if not codigo:
            codigo_desc_block = re.search(r'CÓDIGO:?\s*(.*?)(?=\n\n|$)', contenido, re.DOTALL)
            if codigo_desc_block:
                codigo = codigo_desc_block.group(1).strip()

        # Preparar el mensaje para el modelo
        prompt = f"""
        Corregir los errores en el siguiente código:

        {'```\n' + codigo + '\n```' if codigo else 'No se proporcionó código específico a corregir.'}

        {f'ERROR REPORTADO:\n{error}' if error else 'No se especificó un error concreto.'}

        Por favor, proporciona el código corregido y una explicación de los cambios realizados.
        """

        # Enviar al modelo a través del método run adaptado
        respuesta = self.run([prompt], ["Solicitud de corrección de código"])

        # Convertir a string si es una lista
        if isinstance(respuesta, list):
            respuesta = "\n".join(respuesta)

        return respuesta

    def mejorar_implementacion(self, mensaje):
        """
        Mejora una implementación existente según los comentarios recibidos.

        Args:
            mensaje: Mensaje con la solicitud de mejora

        Returns:
            Código mejorado como texto
        """
        contenido = mensaje.contenido

        # Extraer análisis o feedback si está presente
        analisis_block = re.search(r'ANÁLISIS:?\s*(.*?)(?=\n\n|$)', contenido, re.DOTALL)
        analisis = analisis_block.group(1).strip() if analisis_block else ""

        # Extraer el código a mejorar si está presente
        codigo_block = re.search(r'```[\w]*\n(.*?)```', contenido, re.DOTALL)
        codigo = codigo_block.group(1) if codigo_block else ""

        # Si el código no está explícito, buscarlo en el contexto actual del proyecto
        if not codigo and self.project_path:
            # Usar descripción del código para buscar en los archivos del proyecto
            codigo_desc = re.search(r'código\s+(?:en|de)\s+([^\.]+)', contenido, re.IGNORECASE)
            if codigo_desc:
                archivo_desc = codigo_desc.group(1).strip()
                try:
                    for archivo in self.project_path.glob(f"**/*{archivo_desc}*"):
                        if archivo.is_file():
                            with open(archivo, "r", encoding="utf-8") as f:
                                codigo = f.read()
                            break
                except Exception as e:
                    print(f"Error buscando archivo: {str(e)}")

        # Preparar el mensaje para el modelo
        prompt = f"""
        Mejorar la siguiente implementación según el análisis proporcionado:

        {'```\n' + codigo + '\n```' if codigo else 'No se proporcionó código específico a mejorar.'}

        {f'ANÁLISIS/FEEDBACK:\n{analisis}' if analisis else 'No se proporcionó análisis específico.'}

        Por favor, proporciona el código mejorado y una explicación de las mejoras realizadas.
        """

        # Enviar al modelo
        respuesta = self.run([prompt], ["Solicitud de mejora de implementación"])

        # Convertir a string si es una lista
        if isinstance(respuesta, list):
            respuesta = "\n".join(respuesta)

        # Aplicar los cambios al proyecto si es posible
        self._intentar_aplicar_cambios(respuesta)

        return respuesta

    def ajustar_arquitectura(self, mensaje):
        """
        Ajusta la implementación para alinearla con la arquitectura de diseño.

        Args:
            mensaje: Mensaje con la solicitud de ajuste

        Returns:
            Código ajustado como texto
        """
        contenido = mensaje.contenido

        # Extraer análisis de desviación de arquitectura
        analisis_block = re.search(r'ANÁLISIS:?\s*(.*?)(?=\n\n|$)', contenido, re.DOTALL)
        analisis = analisis_block.group(1).strip() if analisis_block else ""

        # Preparar el mensaje para el modelo
        prompt = f"""
        Se requiere ajustar la implementación del proyecto para alinearla mejor con el diseño arquitectónico.

        ANÁLISIS DEL ARQUITECTO:
        {analisis if analisis else "No se proporcionó un análisis específico."}

        Por favor:
        1. Identifica los archivos que necesitan ser modificados
        2. Realiza los cambios necesarios para alinear el código con la arquitectura prevista
        3. Explica las modificaciones realizadas

        Asegúrate de mantener la funcionalidad existente mientras alineas el código con la arquitectura.
        """

        # Enviar al modelo
        respuesta = self.run([prompt], ["Solicitud de ajuste arquitectónico"])

        # Convertir a string si es una lista
        if isinstance(respuesta, list):
            respuesta = "\n".join(respuesta)

        # Aplicar los cambios al proyecto si es posible
        self._intentar_aplicar_cambios(respuesta)

        return respuesta

    def _intentar_aplicar_cambios(self, respuesta):
        """
        Intenta aplicar los cambios de código identificados en la respuesta al proyecto.

        Args:
            respuesta: Respuesta del modelo con los cambios propuestos
        """
        if not self.project_path or not self.project_path.exists():
            return

        try:
            # Extraer bloques de código con nombres de archivo
            archivo_bloques = re.finditer(r'###\s+([\w/.-]+)\s*\n```(?:\w*)\n(.*?)```', respuesta, re.DOTALL)

            cambios_aplicados = []

            for match in archivo_bloques:
                ruta_archivo = match.group(1).strip()
                nuevo_contenido = match.group(2)

                # Ruta completa del archivo
                file_path = self.project_path / ruta_archivo

                # Verificar si el directorio padre existe, si no, crearlo
                file_path.parent.mkdir(parents=True, exist_ok=True)

                # Verificar si el archivo existe para registrar si es creación o modificación
                es_nuevo = not file_path.exists()

                # Guardar el nuevo contenido
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(nuevo_contenido)

                cambios_aplicados.append({
                    "archivo": str(ruta_archivo),
                    "accion": "creado" if es_nuevo else "modificado"
                })

            # Registrar los cambios realizados
            if cambios_aplicados and self._sistema_mensajeria:
                self._sistema_mensajeria.publicar(
                    Mensaje(
                        emisor=self.config.name,
                        tipo="cambios_aplicados",
                        contenido=f"Se aplicaron {len(cambios_aplicados)} cambios al proyecto",
                        metadata={
                            "cambios": cambios_aplicados,
                            "proyecto": str(self.project_path)
                        }
                    )
                )
        except Exception as e:
            print(f"[{self.config.name}] ⚠️ Error al aplicar cambios: {str(e)}")

    def solicitar_aclaracion_requerimiento(self, sme_nombre, requerimiento):
        """
        Solicita al SME una aclaración sobre un requerimiento específico.

        Args:
            sme_nombre: Nombre del agente SME
            requerimiento: ID o descripción del requerimiento

        Returns:
            Aclaración del requerimiento
        """
        consulta = f"""
        Necesito una aclaración sobre este requerimiento para implementarlo correctamente:

        {requerimiento}

        Específicamente, necesito entender:
        1. Detalles funcionales exactos que se esperan
        2. Comportamiento esperado en casos límite
        3. Criterios de aceptación específicos
        4. Cualquier restricción o consideración técnica importante
        """

        return self.consultar_agente(sme_nombre, consulta)

    def solicitar_diseno_tecnico(self, architect_nombre, requerimiento):
        """
        Solicita al arquitecto detalles de diseño para implementar un requerimiento.

        Args:
            architect_nombre: Nombre del agente arquitecto
            requerimiento: ID o descripción del requerimiento

        Returns:
            Diseño técnico para el requerimiento
        """
        consulta = f"""
        Necesito orientación de diseño para implementar este requerimiento:

        {requerimiento}

        Por favor, proporciona:
        1. Componentes específicos que debo crear o modificar
        2. Estructura de datos recomendada
        3. Patrones de diseño aplicables
        4. Consideraciones técnicas importantes para la implementación
        """

        return self.consultar_agente(architect_nombre, consulta)

    def _construir_mensaje_implementacion(self, requerimientos_funcionales, diseno_tecnico, estado_actual):
        """
        Construye el mensaje de solicitud de implementación para el modelo.

        Args:
            requerimientos_funcionales: Lista de requerimientos a implementar
            diseno_tecnico: Lista de líneas del diseño técnico
            estado_actual: Estado actual del proyecto si existe

        Returns:
            Mensaje formateado para el modelo
        """
        # Formatear los requerimientos y el diseño como texto
        requerimientos_texto = "\n".join([f"- {req}" for req in requerimientos_funcionales])
        diseno_texto = "\n".join(diseno_tecnico)

        return f"""
        Necesito {'mejorar' if estado_actual else 'implementar'} código que cumpla con los siguientes requerimientos funcionales:

        {requerimientos_texto}

        El diseño técnico propuesto es el siguiente:

        {diseno_texto}

        {'ESTADO ACTUAL DEL PROYECTO:' if estado_actual else 'Este es un nuevo proyecto, aún no hay código implementado.'}
        {estado_actual}

        IMPORTANTE: 
        1. {'Mejora el código existente' if estado_actual else 'Implementa un nuevo proyecto'} que cumpla con todos los requerimientos funcionales.
        2. Estructura tu respuesta con las siguientes secciones claramente delimitadas:

        ## DOCUMENTACIÓN
        [Actualiza o crea la documentación detallada del proyecto]

        ## INSTRUCCIONES
        [Instrucciones paso a paso para instalar dependencias y ejecutar el proyecto]

        ## ESTRUCTURA
        [Describe brevemente la estructura de archivos y carpetas del proyecto]

        ## CAMBIOS REALIZADOS EN ESTA ITERACIÓN
        [Lista de cambios específicos realizados en esta iteración]

        ## ARCHIVOS
        [Para cada archivo nuevo o modificado, usa el siguiente formato:]

        ### path/to/file.ext
        ```lenguaje
        contenido completo del archivo
        ```

        3. Separa claramente el frontend y el backend en carpetas diferentes.
        4. Incluye todos los archivos necesarios para que el proyecto funcione, incluyendo package.json, configuraciones, etc.
        5. Asegúrate de que la implementación sea completamente funcional.
        6. Es muy importante que incluyas el código COMPLETO de cada archivo, no uses '...' o 'código existente aquí'.
        """