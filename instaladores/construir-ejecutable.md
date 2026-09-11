# Construir ejecutable del agente con PyInstaller

Permite instalar el agente **sin Python** en cada cliente. Hay que compilar en
cada sistema operativo (no se puede generar un `.exe` en Linux para Windows).

Requisito: Python 3.10+ y PyInstaller solo en la máquina de compilación
(`pip install pyinstaller` — no va en los clientes del laboratorio).

## Windows (en un PC con Python)

Desde la raíz del proyecto:

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name ciber-agente `
  --paths . `
  --hidden-import=tkinter `
  agente/__main__.py
```

El ejecutable queda en `dist\ciber-agente.exe`. Ajusta el acceso directo de
Inicio para usar `ciber-agente.exe` en lugar de `pythonw.exe`.

## Linux (Ubuntu/Debian)

```bash
pip install pyinstaller
pyinstaller --onefile --name ciber-agente \
  --paths . \
  --hidden-import=tkinter \
  agente/__main__.py
```

Copia `dist/ciber-agente` a `/opt/ciber-mensajeria/` y actualiza
`ciber-agente.desktop` para invocar ese binario.

## macOS

Igual que Linux; compila en una Mac con el Python de python.org (Tk actualizado).

```bash
pip3 install pyinstaller
pyinstaller --onefile --windowed --name ciber-agente \
  --paths . \
  --hidden-import=tkinter \
  agente/__main__.py
```

## Notas

- El ejecutable incluye la biblioteca estándar; sigue leyendo `config.json` del
  SO (`C:\ProgramData\...`, `/etc/ciber-mensajeria/`, etc.).
- Tras cambiar el código del agente, hay que volver a compilar en cada
  plataforma.
- Para el servidor no suele hacer falta ejecutable: en DC01 ya hay Python
  instalado con el instalador del servidor.
