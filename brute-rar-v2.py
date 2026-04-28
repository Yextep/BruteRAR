#!/usr/bin/env python3
"""
Brute RAR v2

Auditor de diccionario para archivos RAR protegidos por contraseña.
Usalo solo sobre archivos propios o donde tengas autorizacion explicita.
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from pathlib import Path


VERSION = "2.0.0"
DEFAULT_BATCH_SIZE = 16
DEFAULT_TIMEOUT = 60.0
DEFAULT_STATUS_EVERY = 2.0


@dataclass(frozen=True)
class Engine:
    name: str
    kind: str
    executable: str


@dataclass
class Counters:
    total: int = 0
    submitted: int = 0
    attempted: int = 0
    timeouts: int = 0
    errors: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def add_submitted(self, amount):
        with self.lock:
            self.submitted += amount

    def add_attempt(self, timed_out=False, errored=False):
        with self.lock:
            self.attempted += 1
            if timed_out:
                self.timeouts += 1
            if errored:
                self.errors += 1

    def snapshot(self):
        with self.lock:
            return {
                "total": self.total,
                "submitted": self.submitted,
                "attempted": self.attempted,
                "timeouts": self.timeouts,
                "errors": self.errors,
            }


def clean_path(raw_value):
    if raw_value is None:
        return None
    value = raw_value.strip()
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        value = value[1:-1]
    return Path(value).expanduser()


def prompt_path(current_value, message):
    if current_value:
        return clean_path(current_value)
    try:
        return clean_path(input(message))
    except EOFError:
        return None


def command_exists(name):
    return shutil.which(name) is not None


def windows_known_paths():
    paths = []
    for env_name in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        base = os.environ.get(env_name)
        if not base:
            continue
        paths.extend(
            [
                Path(base) / "7-Zip" / "7z.exe",
                Path(base) / "WinRAR" / "UnRAR.exe",
                Path(base) / "WinRAR" / "unrar.exe",
            ]
        )
    return paths


def find_engine(preference="auto"):
    search_order = ["7z", "unrar"] if preference == "auto" else [preference]

    for wanted in search_order:
        if wanted == "7z":
            for candidate in ("7z", "7zz", "7za", "7z.exe", "7zz.exe", "7za.exe"):
                found = shutil.which(candidate)
                if found:
                    return Engine("7-Zip", "7z", found)
            if platform.system().lower() == "windows":
                for candidate in windows_known_paths():
                    if candidate.name.lower().startswith("7z") and candidate.exists():
                        return Engine("7-Zip", "7z", str(candidate))

        if wanted == "unrar":
            for candidate in ("unrar", "UnRAR.exe", "unrar.exe"):
                found = shutil.which(candidate)
                if found:
                    return Engine("UnRAR", "unrar", found)
            if platform.system().lower() == "windows":
                for candidate in windows_known_paths():
                    if candidate.name.lower() == "unrar.exe" and candidate.exists():
                        return Engine("UnRAR", "unrar", str(candidate))

    return None


def read_os_release_ids():
    ids = set()
    path = Path("/etc/os-release")
    if not path.exists():
        return ids

    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'").lower()
            if key in ("ID", "ID_LIKE"):
                ids.update(value.split())
    except OSError:
        pass
    return ids


def is_termux():
    prefix = os.environ.get("PREFIX", "")
    return "com.termux" in prefix or Path("/data/data/com.termux").exists()


def sudo_prefix():
    if os.name == "nt":
        return []
    geteuid = getattr(os, "geteuid", None)
    if geteuid and geteuid() == 0:
        return []
    if command_exists("sudo"):
        return ["sudo"]
    return []


def installer_commands(preference="auto"):
    system = platform.system().lower()
    target_7z = preference in ("auto", "7z")
    target_unrar = preference == "unrar"

    if is_termux() and command_exists("pkg"):
        if target_unrar:
            return [["pkg", "install", "-y", "unrar"], ["pkg", "install", "-y", "p7zip"]]
        return [["pkg", "install", "-y", "p7zip"]]

    if system == "windows":
        commands = []
        if target_7z and command_exists("winget"):
            commands.append(
                [
                    "winget",
                    "install",
                    "-e",
                    "--id",
                    "7zip.7zip",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                ]
            )
        if target_7z and command_exists("choco"):
            commands.append(["choco", "install", "7zip", "-y"])
        if target_unrar and command_exists("winget"):
            commands.append(
                [
                    "winget",
                    "install",
                    "-e",
                    "--id",
                    "RARLab.WinRAR",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                ]
            )
        return commands

    if system == "darwin":
        if command_exists("brew"):
            return [["brew", "install", "sevenzip", "unrar"]]
        return []

    ids = read_os_release_ids()
    prefix = sudo_prefix()

    if command_exists("apt-get") or {"debian", "ubuntu", "linuxmint"} & ids:
        return [
            prefix + ["apt-get", "update"],
            prefix + ["apt-get", "install", "-y", "p7zip-full", "p7zip-rar", "unrar"],
            prefix + ["apt-get", "install", "-y", "7zip", "unrar"],
            prefix + ["apt-get", "install", "-y", "p7zip-full"],
        ]

    if command_exists("dnf") or {"fedora", "rhel", "centos"} & ids:
        return [prefix + ["dnf", "install", "-y", "p7zip", "p7zip-plugins", "unrar"]]

    if command_exists("pacman") or {"arch", "manjaro"} & ids:
        return [prefix + ["pacman", "-Sy", "--noconfirm", "p7zip", "unrar"]]

    if command_exists("zypper") or {"suse", "opensuse"} & ids:
        return [prefix + ["zypper", "--non-interactive", "install", "p7zip", "unrar"]]

    return []


def try_install_engine(preference="auto", quiet=False):
    commands = installer_commands(preference)
    if not commands:
        return None

    if not quiet:
        print("[*] No se encontro 7-Zip/UnRAR. Intentando instalacion automatica...")

    for command in commands:
        if not command:
            continue
        if not quiet:
            print("[*] Ejecutando:", " ".join(command))
        try:
            completed = subprocess.run(command, check=False)
        except (OSError, KeyboardInterrupt):
            continue
        if completed.returncode == 0:
            engine = find_engine(preference)
            if engine:
                return engine

    return find_engine(preference)


def ensure_engine(preference="auto", auto_install=True, quiet=False):
    engine = find_engine(preference)
    if engine:
        return engine

    if auto_install:
        engine = try_install_engine(preference, quiet=quiet)
        if engine:
            return engine

    raise RuntimeError(
        "No se encontro un motor RAR compatible. Instala 7-Zip o UnRAR, "
        "o ejecuta el script sin --no-install para intentar instalarlo automaticamente."
    )


def build_test_command(engine, archive, password):
    archive_arg = str(archive)
    if engine.kind == "7z":
        return [engine.executable, "t", "-y", "-bd", "-p" + password, archive_arg]
    return [engine.executable, "t", "-y", "-inul", "-p" + password, archive_arg]


def build_no_password_command(engine, archive):
    archive_arg = str(archive)
    if engine.kind == "7z":
        return [engine.executable, "t", "-y", "-bd", "-p", archive_arg]
    return [engine.executable, "t", "-y", "-inul", "-p-", archive_arg]


def build_extract_command(engine, archive, password, output_dir):
    archive_arg = str(archive)
    output_dir = str(output_dir)
    if engine.kind == "7z":
        return [
            engine.executable,
            "x",
            "-y",
            "-bd",
            "-p" + password,
            "-o" + output_dir,
            archive_arg,
        ]
    return [engine.executable, "x", "-y", "-p" + password, archive_arg, output_dir + os.sep]


def run_candidate(engine, archive, password, timeout):
    try:
        completed = subprocess.run(
            build_test_command(engine, archive, password),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
        )
        return completed.returncode == 0, False, False
    except subprocess.TimeoutExpired:
        return False, True, False
    except OSError:
        return False, False, True


def run_no_password_check(engine, archive, timeout):
    try:
        completed = subprocess.run(
            build_no_password_command(engine, archive),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
        )
        return completed.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def count_lines_fast(path):
    total = 0
    last_byte = b""
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            total += chunk.count(b"\n")
            last_byte = chunk[-1:]
    if last_byte and last_byte != b"\n":
        total += 1
    return total


def iter_passwords(path, encoding):
    with path.open("r", encoding=encoding, errors="replace", newline="") as handle:
        for line_number, line in enumerate(handle, start=1):
            password = line.rstrip("\r\n")
            if password == "":
                continue
            yield line_number, password


def attempt_batch(engine, archive, batch, stop_event, timeout, counters):
    for line_number, password in batch:
        if stop_event.is_set():
            return None

        matched, timed_out, errored = run_candidate(engine, archive, password, timeout)
        counters.add_attempt(timed_out=timed_out, errored=errored)

        if matched:
            return line_number, password

    return None


def format_rate(value):
    if value >= 1000:
        return f"{value:,.0f}/s"
    if value >= 100:
        return f"{value:.0f}/s"
    if value >= 10:
        return f"{value:.1f}/s"
    return f"{value:.2f}/s"


def progress_reporter(counters, stop_event, done_event, interval, quiet):
    if quiet or interval <= 0:
        return

    start_time = time.monotonic()
    last_len = 0

    while not done_event.wait(interval):
        snapshot = counters.snapshot()
        elapsed = max(time.monotonic() - start_time, 0.001)
        rate = snapshot["attempted"] / elapsed

        if snapshot["total"]:
            percent = min((snapshot["attempted"] / snapshot["total"]) * 100, 100)
            message = (
                f"[*] Probadas {snapshot['attempted']:,}/{snapshot['total']:,} "
                f"({percent:.1f}%) | {format_rate(rate)}"
            )
        else:
            message = f"[*] Probadas {snapshot['attempted']:,} | {format_rate(rate)}"

        if snapshot["timeouts"]:
            message += f" | timeouts: {snapshot['timeouts']}"
        if snapshot["errors"]:
            message += f" | errores: {snapshot['errors']}"

        sys.stdout.write("\r" + message + " " * max(0, last_len - len(message)))
        sys.stdout.flush()
        last_len = len(message)

        if stop_event.is_set():
            break

    if last_len:
        sys.stdout.write("\r" + " " * last_len + "\r")
        sys.stdout.flush()


def collect_finished(pending):
    done, pending = wait(pending, return_when=FIRST_COMPLETED)
    for future in done:
        result = future.result()
        if result:
            return result, pending
    return None, pending


def crack_archive(engine, archive, wordlist, workers, batch_size, timeout, encoding, dedupe, quiet):
    total = count_lines_fast(wordlist)
    counters = Counters(total=total)
    stop_event = threading.Event()
    done_event = threading.Event()
    reporter = threading.Thread(
        target=progress_reporter,
        args=(counters, stop_event, done_event, DEFAULT_STATUS_EVERY, quiet),
        daemon=True,
    )
    reporter.start()

    found = None
    max_pending = max(workers * 4, workers)
    seen = set() if dedupe else None

    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            pending = set()
            batch = []

            for item in iter_passwords(wordlist, encoding):
                if stop_event.is_set():
                    break

                if seen is not None:
                    password = item[1]
                    if password in seen:
                        continue
                    seen.add(password)

                batch.append(item)
                if len(batch) < batch_size:
                    continue

                counters.add_submitted(len(batch))
                pending.add(
                    executor.submit(
                        attempt_batch,
                        engine,
                        archive,
                        batch,
                        stop_event,
                        timeout,
                        counters,
                    )
                )
                batch = []

                while len(pending) >= max_pending and not stop_event.is_set():
                    found, pending = collect_finished(pending)
                    if found:
                        stop_event.set()
                        break

            if batch and not stop_event.is_set():
                counters.add_submitted(len(batch))
                pending.add(
                    executor.submit(
                        attempt_batch,
                        engine,
                        archive,
                        batch,
                        stop_event,
                        timeout,
                        counters,
                    )
                )

            while pending and not stop_event.is_set():
                found, pending = collect_finished(pending)
                if found:
                    stop_event.set()
                    break

            for future in pending:
                future.cancel()

    finally:
        done_event.set()
        reporter.join()

    return found, counters


def extract_archive(engine, archive, password, output_dir, timeout):
    output_dir.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        build_extract_command(engine, archive, password, output_dir),
        stdin=subprocess.DEVNULL,
        timeout=timeout,
        check=False,
    )
    return completed.returncode == 0


def positive_int(value):
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("debe ser un numero entero")
    if parsed <= 0:
        raise argparse.ArgumentTypeError("debe ser mayor que 0")
    return parsed


def positive_float(value):
    try:
        parsed = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("debe ser un numero")
    if parsed <= 0:
        raise argparse.ArgumentTypeError("debe ser mayor que 0")
    return parsed


def default_workers():
    cpu_count = os.cpu_count() or 2
    return max(1, min(cpu_count, 32))


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Auditor de diccionario para recuperar contrasenas de archivos RAR "
            "propios o autorizados."
        )
    )
    parser.add_argument("-a", "--archive", help="ruta del archivo .rar")
    parser.add_argument("-w", "--wordlist", help="ruta del diccionario .txt")
    parser.add_argument(
        "-j",
        "--workers",
        type=positive_int,
        default=default_workers(),
        help="procesos de prueba en paralelo (por defecto: CPU hasta 32)",
    )
    parser.add_argument(
        "--engine",
        choices=("auto", "7z", "unrar"),
        default="auto",
        help="motor externo a usar (por defecto: auto)",
    )
    parser.add_argument(
        "--timeout",
        type=positive_float,
        default=DEFAULT_TIMEOUT,
        help="segundos maximos por intento antes de descartarlo",
    )
    parser.add_argument(
        "--batch-size",
        type=positive_int,
        default=DEFAULT_BATCH_SIZE,
        help="tamano de lote por tarea interna",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="codificacion del diccionario (por defecto: utf-8)",
    )
    parser.add_argument(
        "--dedupe",
        action="store_true",
        help="evita probar contrasenas repetidas guardandolas en memoria",
    )
    parser.add_argument(
        "--extract-to",
        help="si encuentra la contrasena, extrae el RAR a esta carpeta",
    )
    parser.add_argument(
        "--no-install",
        action="store_true",
        help="no intenta instalar 7-Zip/UnRAR si faltan",
    )
    parser.add_argument("--quiet", action="store_true", help="reduce la salida en pantalla")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser.parse_args()


def validate_paths(archive, wordlist):
    if archive is None:
        raise ValueError("No se recibio la ruta del archivo RAR.")
    if wordlist is None:
        raise ValueError("No se recibio la ruta del diccionario.")

    archive = archive.resolve()
    wordlist = wordlist.resolve()

    if not archive.is_file():
        raise ValueError(f"El archivo RAR no existe o no es un archivo: {archive}")
    if not wordlist.is_file():
        raise ValueError(f"El diccionario no existe o no es un archivo: {wordlist}")
    return archive, wordlist


def main():
    args = parse_args()

    archive = prompt_path(args.archive, "Introduce la ruta del archivo protegido (RAR): ")
    wordlist = prompt_path(args.wordlist, "Introduce la ruta del diccionario .txt: ")

    try:
        archive, wordlist = validate_paths(archive, wordlist)
        engine = ensure_engine(args.engine, auto_install=not args.no_install, quiet=args.quiet)
    except (RuntimeError, ValueError) as exc:
        print(f"[!] {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(f"[*] Sistema: {platform.system()} {platform.release()}")
        print(f"[*] Motor: {engine.name} -> {engine.executable}")
        print(f"[*] Workers: {args.workers} | lote: {args.batch_size} | timeout: {args.timeout:g}s")
        print(f"[*] RAR: {archive}")
        print(f"[*] Diccionario: {wordlist}")

    if run_no_password_check(engine, archive, args.timeout):
        print("[+] Contraseña encontrada: <vacia o archivo sin contraseña>")
        return 0

    started = time.monotonic()
    try:
        found, counters = crack_archive(
            engine=engine,
            archive=archive,
            wordlist=wordlist,
            workers=args.workers,
            batch_size=args.batch_size,
            timeout=args.timeout,
            encoding=args.encoding,
            dedupe=args.dedupe,
            quiet=args.quiet,
        )
    except KeyboardInterrupt:
        print("\n[!] Interrumpido por el usuario.", file=sys.stderr)
        return 130
    except UnicodeError as exc:
        print(f"\n[!] Error leyendo el diccionario: {exc}", file=sys.stderr)
        return 2

    elapsed = max(time.monotonic() - started, 0.001)
    snapshot = counters.snapshot()
    average = snapshot["attempted"] / elapsed

    if found:
        line_number, password = found
        print(f"[+] Contraseña encontrada: {password!r}")
        print(f"[+] Linea del diccionario: {line_number:,}")
        print(f"[+] Intentos reales: {snapshot['attempted']:,} | velocidad media: {format_rate(average)}")

        if args.extract_to:
            output_dir = clean_path(args.extract_to).resolve()
            print(f"[*] Extrayendo en: {output_dir}")
            if extract_archive(engine, archive, password, output_dir, args.timeout * 4):
                print("[+] Extraccion completada.")
            else:
                print("[!] La contraseña es correcta, pero la extraccion fallo.", file=sys.stderr)
                return 3
        return 0

    print("[-] Contraseña no encontrada en el diccionario.")
    print(f"[-] Intentos reales: {snapshot['attempted']:,} | velocidad media: {format_rate(average)}")
    if snapshot["timeouts"]:
        print(f"[-] Intentos descartados por timeout: {snapshot['timeouts']:,}")
    if snapshot["errors"]:
        print(f"[-] Errores al ejecutar el motor externo: {snapshot['errors']:,}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
