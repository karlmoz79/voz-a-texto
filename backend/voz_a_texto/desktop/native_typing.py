import os
import shutil
import subprocess
import sys


DEFAULT_NATIVE_TYPE_CMD = "xdotool"


class NativeTypingError(RuntimeError):
    def __init__(self, message, *, disable_feature=False):
        super().__init__(message)
        self.disable_feature = disable_feature


class NativeTypingService:
    def __init__(
        self,
        command=None,
        env=None,
        platform_name=None,
        runner=None,
        which=None,
        timeout_sec=5,
    ):
        self.command = (
            command or os.environ.get("NATIVE_TYPE_CMD") or DEFAULT_NATIVE_TYPE_CMD
        )
        self._env = os.environ if env is None else env
        self._platform_name = platform_name or sys.platform
        self._runner = runner or subprocess.run
        self._which = which or shutil.which
        self._timeout_sec = timeout_sec

    def get_environment_error(self):
        try:
            self._ensure_supported_environment()
        except NativeTypingError as exc:
            return str(exc)
        return None

    def type_text(self, text, append_space=True, backspaces=0, delay_ms=1):
        normalized_text = self._normalize_text(text)
        normalized_backspaces = self._normalize_backspaces(backspaces)
        normalized_delay_ms = self._normalize_delay_ms(delay_ms)

        if not normalized_text and normalized_backspaces == 0:
            return

        self._ensure_supported_environment()
        self._ensure_focused_window()

        if normalized_backspaces > 0:
            self._run_command(
                [
                    "key",
                    "--clearmodifiers",
                    "--repeat",
                    str(normalized_backspaces),
                    "BackSpace",
                ],
                default_message="No se pudo enviar retrocesos a la ventana activa.",
            )

        if normalized_text:
            final_text = f"{normalized_text} " if append_space else normalized_text
            self._run_command(
                [
                    "type",
                    "--clearmodifiers",
                    "--delay",
                    str(normalized_delay_ms),
                    "--",
                    final_text,
                ],
                default_message="No se pudo escribir el texto en la ventana activa.",
            )

    def _ensure_supported_environment(self):
        if not self._platform_name.startswith("linux"):
            raise NativeTypingError(
                "El dictado nativo solo esta soportado en Linux.",
                disable_feature=True,
            )

        display = self._read_env("DISPLAY")
        session_type_raw = self._read_env("XDG_SESSION_TYPE")
        session_type = session_type_raw.lower() if session_type_raw else None

        if not display:
            if session_type == "wayland":
                raise NativeTypingError(
                    "El dictado nativo requiere una sesion X11 compatible. Wayland puro no esta soportado.",
                    disable_feature=True,
                )

            raise NativeTypingError(
                "No se detecto una sesion grafica X11 compatible para dictado nativo.",
                disable_feature=True,
            )

        if not self._which(self.command):
            raise NativeTypingError(
                f"No se encontro `{self.command}` en PATH. Instala xdotool para usar dictado nativo.",
                disable_feature=True,
            )

    def _ensure_focused_window(self):
        result = self._run_command(
            ["getwindowfocus"],
            default_message="No hay una ventana enfocada compatible para dictado nativo.",
        )
        if not result.stdout.strip():
            raise NativeTypingError(
                "No hay una ventana enfocada compatible para dictado nativo."
            )

    def _run_command(self, args, default_message):
        try:
            result = self._runner(
                [self.command, *args],
                capture_output=True,
                text=True,
                timeout=self._timeout_sec,
                env=dict(self._env),
            )
        except FileNotFoundError:
            raise NativeTypingError(
                f"No se encontro `{self.command}` en PATH. Instala xdotool para usar dictado nativo.",
                disable_feature=True,
            ) from None
        except subprocess.TimeoutExpired:
            raise NativeTypingError(
                "El comando de dictado nativo no respondio a tiempo."
            ) from None
        except OSError as exc:
            raise NativeTypingError(
                f"No se pudo ejecutar `{self.command}`: {exc}"
            ) from exc

        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            if detail:
                raise NativeTypingError(f"{default_message} {detail}")
            raise NativeTypingError(default_message)

        return result

    def _normalize_text(self, text):
        if text is None:
            return ""
        if not isinstance(text, str):
            raise NativeTypingError("Texto invalido para dictado nativo.")
        return text.strip()

    def _normalize_backspaces(self, backspaces):
        try:
            parsed = int(backspaces)
        except (TypeError, ValueError):
            return 0
        return max(0, min(2000, parsed))

    def _normalize_delay_ms(self, delay_ms):
        try:
            parsed = int(delay_ms)
        except (TypeError, ValueError):
            return 1
        return max(0, min(25, parsed))

    def _read_env(self, key):
        value = self._env.get(key)
        return value.strip() if isinstance(value, str) else ""
