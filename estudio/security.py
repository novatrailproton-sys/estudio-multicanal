from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import re
import threading


def redact(value, secrets=()):
    value = str(value)
    for secret in secrets:
        if secret:
            value = value.replace(secret, "[oculto]")
    return re.sub(r"(?:sk-or-v1-|gsk_|Bearer\s+)[A-Za-z0-9_.-]+", "[oculto]", value)


class Vault:
    """OS protected storage only. Never falls back to a plaintext file."""
    def __init__(self, root):
        self.root = Path(root) / "credentials"
        self.memory = {}
        self.lock = threading.RLock()
        self.namespace = "EstudioMulticanal-" + __import__("hashlib").sha256(str(Path(root).resolve()).encode()).hexdigest()[:16]
        self.backend = "memory"
        if os.name == "nt":
            self.backend = "dpapi"
        else:
            try:
                import keyring
                backend = keyring.get_keyring()
                # Explicitly reject plaintext/third-party fallback backends.
                if type(backend).__module__.startswith(("keyring.backends.SecretService", "keyring.backends.macOS")) and backend.priority > 0:
                    self.backend = "keyring"
                    self.keyring = keyring
            except Exception:
                pass

    @staticmethod
    def validate_name(name):
        if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,150}", name):
            raise ValueError("Nombre de conexión no válido.")

    def set(self, name, value, remember=False):
        self.validate_name(name)
        if not value or len(value) > 16000 or "\r" in value or "\n" in value:
            raise ValueError("Clave vacía o no válida.")
        with self.lock:
            if remember:
                if self.backend == "memory":
                    raise ValueError("Este equipo no ofrece un almacén seguro. Desmarca Recordar; la clave durará esta sesión.")
                if self.backend == "dpapi":
                    self.root.mkdir(exist_ok=True, mode=0o700)
                    temp = self.root / (name + ".tmp")
                    temp.write_bytes(self._dpapi(value.encode(), False))
                    temp.replace(self.root / (name + ".bin"))
                else:
                    self.keyring.set_password(self.namespace, name, value)
            self.memory[name] = value

    def get(self, name):
        self.validate_name(name)
        with self.lock:
            if name in self.memory:
                return self.memory[name]
            env = os.getenv("ESTUDIO_" + name.upper().replace(".", "_").replace("-", "_"), "")
            if env:
                return env
            if self.backend == "dpapi" and (self.root / (name+".bin")).exists():
                value = self._dpapi((self.root / (name+".bin")).read_bytes(), True).decode()
            elif self.backend == "keyring":
                value = self.keyring.get_password(self.namespace, name) or ""
            else:
                return ""
            self.memory[name] = value
            return value

    def delete(self, name):
        self.validate_name(name)
        with self.lock:
            self.memory.pop(name, None)
            if self.backend == "dpapi":
                (self.root / (name+".bin")).unlink(missing_ok=True)
            elif self.backend == "keyring":
                try:
                    self.keyring.delete_password(self.namespace, name)
                except self.keyring.errors.PasswordDeleteError:
                    pass

    def secrets(self):
        return tuple(self.memory.values())

    @staticmethod
    def _dpapi(data, decrypt):
        class Blob(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]
        buffer = ctypes.create_string_buffer(data)
        source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
        result = Blob()
        crypt = ctypes.windll.crypt32
        kernel = ctypes.windll.kernel32
        fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
        # CRYPTPROTECT_UI_FORBIDDEN: no prompts; current Windows user scope.
        if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)):
            raise OSError("Windows no pudo proteger o recuperar la clave.")
        try:
            return ctypes.string_at(result.pbData, result.cbData)
        finally:
            kernel.LocalFree(result.pbData)


class InstanceLock:
    def __init__(self, root):
        self.path = Path(root) / "studio.lock"
        self.file = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open("a+b")
        self.file.seek(0)
        if os.name == "nt":
            import msvcrt
            if self.path.stat().st_size == 0:
                self.file.write(b"0")
                self.file.flush()
            self.file.seek(0)
            try:
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                self.file.close()
                raise RuntimeError("El estudio ya está abierto con estos datos.") from None
        else:
            import fcntl
            try:
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                self.file.close()
                raise RuntimeError("El estudio ya está abierto con estos datos.") from None

    def release(self):
        if self.file and not self.file.closed:
            if os.name == "nt":
                import msvcrt
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            self.file.close()
