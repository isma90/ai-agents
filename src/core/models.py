# src/core/models.py
from typing import List, Optional
from pydantic import BaseModel, Field, validator
import re


class FunctionalRequirement(BaseModel):
    """Modelo para un requerimiento funcional estandarizado."""
    id: str = Field(..., description="Identificador único del requerimiento (ej: REQ-01)")
    description: str = Field(..., description="Descripción detallada del requerimiento")
    priority: Optional[str] = Field("Media", description="Prioridad del requerimiento: Alta, Media, Baja")
    status: Optional[str] = Field("Pendiente", description="Estado del requerimiento: Pendiente, Parcial, Completo")

    @validator('id')
    def validate_id_format(cls, v):
        """Valida que el ID tenga el formato correcto."""
        if not re.match(r'^REQ-\d{2,}$', v):
            raise ValueError('El ID debe tener el formato REQ-XX donde XX son números (ej: REQ-01)')
        return v

    @validator('priority')
    def validate_priority(cls, v):
        """Valida que la prioridad tenga un valor permitido."""
        valid_priorities = ["Alta", "Media", "Baja"]
        if v and v not in valid_priorities:
            raise ValueError(f'La prioridad debe ser una de: {", ".join(valid_priorities)}')
        return v

    @validator('status')
    def validate_status(cls, v):
        """Valida que el estado tenga un valor permitido."""
        valid_statuses = ["Pendiente", "Parcial", "Completo"]
        if v and v not in valid_statuses:
            raise ValueError(f'El estado debe ser uno de: {", ".join(valid_statuses)}')
        return v

    def __str__(self):
        return f"{self.id}: {self.description}"

    @classmethod
    def from_string(cls, req_string: str):
        """
        Crea un objeto FunctionalRequirement a partir de una cadena de texto.
        Ejemplo: "REQ-01: Implementar autenticación de usuarios"
        """
        try:
            # Intenta extraer el ID y la descripción
            parts = req_string.split(':', 1)
            if len(parts) != 2:
                # Si no tiene el formato esperado, asigna un ID automático
                return cls(id=f"REQ-{hash(req_string) % 100:02d}", description=req_string.strip())

            req_id = parts[0].strip()
            description = parts[1].strip()

            # Valida el formato del ID o lo corrige si es necesario
            if not re.match(r'^REQ-\d{2,}$', req_id):
                if re.match(r'^REQ-\d+$', req_id):
                    # Corregir el formato si tiene menos de 2 dígitos
                    digits = re.search(r'\d+', req_id).group()
                    req_id = f"REQ-{int(digits):02d}"
                else:
                    # Si no tiene el formato correcto, asigna un ID automático
                    req_id = f"REQ-{hash(req_string) % 100:02d}"

            return cls(id=req_id, description=description)
        except Exception as e:
            # Si hay algún error, crea un requerimiento con un ID genérico
            return cls(id=f"REQ-{hash(req_string) % 100:02d}", description=req_string.strip())


class RequirementsList(BaseModel):
    """Modelo para una lista de requerimientos funcionales."""
    requirements: List[FunctionalRequirement] = Field(default_factory=list)

    def add_requirement(self, requirement: FunctionalRequirement):
        self.requirements.append(requirement)

    def get_pending_requirements(self) -> List[FunctionalRequirement]:
        """Retorna los requerimientos pendientes o parciales."""
        return [req for req in self.requirements if req.status != "Completo"]

    def update_requirement_status(self, req_id: str, new_status: str):
        """Actualiza el estado de un requerimiento específico."""
        for req in self.requirements:
            if req.id == req_id:
                req.status = new_status
                break

    def __iter__(self):
        return iter(self.requirements)

    def __len__(self):
        return len(self.requirements)

    def __getitem__(self, idx):
        return self.requirements[idx]

    @classmethod
    def from_strings(cls, requirements_strings: List[str]):
        """
        Crea un objeto RequirementsList a partir de una lista de cadenas de texto.
        """
        requirements_list = cls()
        for req_string in requirements_strings:
            if req_string.strip():  # Solo procesa líneas no vacías
                req = FunctionalRequirement.from_string(req_string)
                requirements_list.add_requirement(req)
        return requirements_list