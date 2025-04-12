class AgentConfig:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", verbose: bool = True, role_file: str = None):
        self.api_key = api_key
        self.model = model
        self.verbose = verbose
        self.role_file = role_file

        # Cargar la descripción del rol desde el archivo
        self.descripcion_rol = self.cargar_descripcion_rol(role_file)

    def cargar_descripcion_rol(self, role_file: str) -> str:
        """
        Carga la descripción del rol desde un archivo de texto.
        """
        if role_file:
            try:
                with open(role_file, 'r') as file:
                    return file.read().strip()
            except FileNotFoundError:
                raise FileNotFoundError(f"El archivo de rol '{role_file}' no se encuentra.")
        else:
            return "Descripción de rol no especificada."
