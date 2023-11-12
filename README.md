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
