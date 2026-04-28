# Ataque De Fuerza Bruta Para Archivos .RAR

Este script está diseñado para llevar a cabo un ataque de fuerza bruta en un archivo RAR protegido con contraseña, utilizando un diccionario de contraseñas. Este script podría beneficiar a las personas en situaciones donde necesitan recuperar el acceso a un archivo RAR protegido del cual han olvidado la contraseña. También podría ser útil en pruebas de penetración ética para probar la seguridad de archivos RAR protegidos con contraseñas débiles. Sin embargo, es importante destacar que el uso de fuerza bruta para acceder a archivos sin permiso puede ser ilegal y debe realizarse con permiso explícito o en situaciones legales y éticas.


<img align="center" height="400" width="1000" alt="GIF" src="https://github.com/Yextep/BruteRAR/assets/114537444/760b59c4-62a9-4dc2-902f-b7e25a3ce560"/>

# Hilos

El script utiliza múltiples hilos para realizar un ataque de fuerza bruta en un archivo RAR. Divide el diccionario en secciones y asigna cada sección a un hilo para acelerar el proceso. Si encuentra la contraseña, muestra un mensaje indicando que la contraseña fue encontrada y termina la ejecución. Si ninguna contraseña es encontrada, muestra un mensaje indicando que la contraseña no fue encontrada.

# Instalación

Clonamos el repositorio
```bash
git clone https://github.com/Yextep/BruteRAR
```
Accedemos a la carpeta
```bash
cd BruteRAR
```
Instalamos requerimientos
```bash
pip install -r requeriments.txt
```
Ejecutamos el Script
```bash
python3 brute-rar.py
```

# Brute RAR V2

Esta version esta pensada para laboratorios, CTFs y recuperacion legitima: detecta el sistema, busca 7-Zip/UnRAR, intenta instalar un motor compatible si falta y ejecuta pruebas en paralelo con parada temprana.

## Caracteristicas
- Funciona en Linux, Windows, macOS y Termux cuando hay 7-Zip o UnRAR disponible.                                        - Instalacion automatica del motor externo cuando es posible (`apt`, `dnf`, `pacman`, `zypper`, `brew`, `pkg`, `winget` o `choco`).
- Lectura del diccionario por streaming para no cargar archivos grandes completos en memoria.
- Workers paralelos configurados automaticamente segun la CPU.
- Prueba con `test` del archivo, sin extraerlo en cada intento.
- Parada temprana cuando encuentra la contraseña.
- Progreso con intentos, porcentaje, velocidad media, timeouts y errores.
- Opciones avanzadas por CLI sin romper el modo simple interactivo.

## Requisitos

- Python 3.8 o superior.
- 7-Zip o UnRAR. Si no estan instalados, el script intentara instalarlos automaticamente.
- Un archivo RAR y un diccionario de contraseñas en texto plano.       
Las dependencias Python de terceros no son necesarias. El archivo `requirements.txt` se incluye para que `pip install -r requirements.txt` sea valido en flujos de GitHub.

## Uso Rapido

Modo interactivo:

```bash
python brute-rar-v2.py
```

El script pedira solo:

1. Ruta del archivo RAR.
2. Ruta del diccionario `.txt`.

Modo directo:

```bash
python brute-rar-v2.py -a secreto.rar -w rockyou.txt
```

En Windows:

```powershell
py .\brute-rar-v2.py -a C:\Users\me\Desktop\secreto.rar -w C:\Users\me\Desktop\diccionario.txt
```

## Opciones Utiles

```bash
python brute-rar-v2.py -a secreto.rar -w rockyou.txt -j 12
python brute-rar-v2.py -a secreto.rar -w rockyou.txt --engine 7z
python brute-rar-v2.py -a secreto.rar -w rockyou.txt --dedupe
python brute-rar-v2.py -a secreto.rar -w rockyou.txt --extract-to salida
python brute-rar-v2.py -a secreto.rar -w rockyou.txt --no-install
```

- `-j, --workers`: numero de intentos paralelos. Por defecto usa el numero de CPUs, con maximo 32.
- `--engine`: fuerza `7z`, `unrar` o deteccion automatica.
- `--timeout`: segundos maximos por intento. Sube este valor si el RAR es muy grande.
- `--batch-size`: tamaño de lote interno. El valor por defecto suele ser estable.
- `--encoding`: codificacion del diccionario. Por defecto `utf-8`.
- `--dedupe`: evita probar contraseñas repetidas, usando mas memoria.
- `--extract-to`: extrae el archivo automaticamente si encuentra la contraseña.
- `--no-install`: no intenta instalar herramientas automaticamente.
- `--quiet`: reduce la salida.

## Notas De Rendimiento

La velocidad real depende de la CPU, el tamaño del RAR, el tipo de cifrado, el motor externo y la calidad del diccionario. RAR5 con cifrado fuerte puede ser lento por diseño. El script optimiza el flujo evitando extracciones repetidas, leyendo el diccionario por streaming y ejecutando varias pruebas en paralelo, pero no puede garantizar encontrar una contraseña que no este en el diccionario.

Para mejorar resultados:

- Usa un diccionario relevante al objetivo autorizado.
- Ajusta `--workers` si el sistema se satura.
- Usa `--dedupe` si el diccionario tiene muchas repeticiones y tienes memoria suficiente.
- Evita probar sobre discos lentos o rutas de red.
