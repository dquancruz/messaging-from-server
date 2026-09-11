# Ciber Mensajería

Sistema de avisos estilo cibercafé para el laboratorio `lab.lan`: desde el
servidor (Windows Server 2022, DC01) se ven los equipos conectados, se les
mandan avisos que aparecen encima de todo en su pantalla, y se controlan
sesiones con tiempo ("te quedan 5 minutos", "tu tiempo terminó"). Funciona en
clientes Windows, Linux y macOS.

Proyecto universitario (cursos de Sistemas Operativos y de Servidores y Redes).

## Documentación

- [`CLAUDE.md`](CLAUDE.md) — reglas del proyecto, entorno real del laboratorio,
  comandos.
- [`PLAN.md`](PLAN.md) — el plan completo, por fases. Es la fuente de verdad
  del estado del proyecto.
- [`docs/protocolo.md`](docs/protocolo.md) — mensajes agente ↔ servidor.
- [`docs/checklist-pruebas.md`](docs/checklist-pruebas.md) — pruebas en la red
  real del laboratorio (Fase 6).
- [`docs/guion-demo.md`](docs/guion-demo.md) — guion de 5 minutos para la
  presentación (Fase 6).
- `docs/guia-instalacion.md` — guía de instaladores (Fase 5).

## Estructura

```
comun/          # protocolo compartido entre agente y servidor
servidor/       # asyncio: acepta agentes, guarda estado, panel web
agente/         # tkinter: ventanas emergentes, contador, bloqueo (Fase 2+)
instaladores/   # scripts de instalación por sistema operativo (Fase 5)
herramientas/   # simular_agentes.py y otras utilidades de desarrollo
tests/          # pruebas unitarias (python -m unittest)
legacy/         # script anterior (msg.exe + SSH); no se modifica
```

## Requisitos

Solo biblioteca estándar de Python 3.10+ (el mínimo por Ubuntu 22.04) tanto en
el servidor como en el agente. La interfaz del agente es tkinter; la del
servidor, un panel web servido por el propio servidor. Sin dependencias
externas ni `pip install` en los clientes.

## Comandos

```bash
# Pruebas
python -m unittest discover -s tests -v

# Servidor en local (desarrollo)
python -m servidor --config servidor/config.json

# Agente en local (desarrollo)
python -m agente --config agente/config.json

# Simular equipos falsos (sin las máquinas reales)
python herramientas/simular_agentes.py --n 4
```

En DC01, tras instalar con `instaladores/windows/instalar-servidor.ps1`:

```powershell
# Iniciar el servidor manualmente (consola visible)
C:\CiberMensajeria\iniciar-servidor.ps1
```

El token compartido del laboratorio está en `servidor/config.json` y
`agente/config.json` (`lab-lan-ciber-mensajeria`). Los instaladores de agente
lo usan por defecto; no hace falta pasarlo a mano.
