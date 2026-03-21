from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class TranscriptEntry:
    text: str
    timestamp: str = ""


class TranscriptStore:
    """Almacena el historial reciente de transcripciones de la sesion actual.

    Responsabilidades:
    - Acumular entradas individuales de transcripcion.
    - Construir un texto unificado para mostrar en la UI.
    - Exportar el historial completo a un archivo .txt.
    - Limpiar el historial de la sesion.
    """

    def __init__(self):
        self._entries: list[TranscriptEntry] = []

    @property
    def entries(self) -> list[TranscriptEntry]:
        return list(self._entries)

    @property
    def count(self) -> int:
        return len(self._entries)

    @property
    def full_text(self) -> str:
        """Devuelve todo el historial concatenado con saltos de linea."""
        return "\n".join(entry.text for entry in self._entries if entry.text).strip()

    @property
    def can_export(self) -> bool:
        return bool(self.full_text)

    @property
    def last_text(self) -> str:
        """Devuelve solo el texto de la ultima transcripcion."""
        if not self._entries:
            return ""
        return self._entries[-1].text

    def append(self, text, timestamp=""):
        """Agrega una nueva transcripcion al historial."""
        stripped = text.strip() if isinstance(text, str) else ""
        if not stripped:
            return

        self._entries.append(TranscriptEntry(text=stripped, timestamp=timestamp))

    def clear(self):
        """Limpia todo el historial de la sesion."""
        self._entries.clear()

    def export_to_file(self, path):
        """Exporta el historial completo a un archivo de texto.

        Retorna la ruta del archivo escrito o lanza OSError si falla.
        """
        target_path = Path(path)
        content = self.full_text
        if not content:
            raise ValueError("No hay transcripciones para exportar.")

        target_path.write_text(content, encoding="utf-8")
        return target_path
