# Ciber Mensajería — lab.lan

Proyecto universitario (cursos de SO y Servidores + Redes). Es un sistema de avisos estilo
cibercafé: desde el servidor Windows se mandan mensajes emergentes y se controlan sesiones
con tiempo ("te quedan 5 minutos", "tu tiempo terminó") en equipos cliente Windows, Linux y macOS.

El plan completo, por fases, está en `PLAN.md`. Síguelo en orden.

## Entorno real del laboratorio

| Equipo | Sistema | Dirección | Notas |
|---|---|---|---|
| DC01 | Windows Server 2022 (VM en Proxmox) | 192.168.1.10 / `dc01.lab.lan` | AD DS, DNS y DHCP del dominio `lab.lan`. Aquí corre el servidor. |
| Proxmox | Proxmox VE 9 | 192.168.1.5 | Host físico. No se toca. |
| Ubuntu | Ubuntu Desktop LTS | 192.168.1.20 / `daniel-cruz-hp.lab.lan` | Unido al dominio con SSSD. Usuario de prueba: `dquan`. |
| Debian | Debian 12+ | DHCP | Unido al dominio. Puede no tener escritorio gráfico. |
| Win10 / Win11 | Windows 10/11 Pro | DHCP | Se unen al dominio más adelante. |
| Mac | macOS | DHCP | Puntos extra. Puede no estar en el dominio. |

Gateway: 192.168.1.1. Todo es red local; no hay acceso desde internet.

## Reglas del proyecto

- **Solo biblioteca estándar de Python 3.10+** en servidor y agente. Nada de `pip install` en
  los clientes. Python 3.10 es el mínimo porque es el de Ubuntu 22.04. No uses `tomllib` ni
  otras cosas de 3.11+; la configuración va en JSON.
- La interfaz del agente es **tkinter**. La del servidor es un **panel web** servido por el
  propio servidor.
- Todo el texto que ve el usuario va **en español**, con acentos correctos.
- Archivos en **UTF-8**. Los `.ps1` van en **UTF-8 con BOM y CRLF**, porque el PowerShell 5.1
  de Windows Server 2022 lee mal los acentos sin BOM. Los `.sh` van con **LF**. Déjalo fijado
  en `.gitattributes`.
- Rutas con `pathlib`. Nada de rutas de Windows o Unix escritas a mano fuera de los instaladores.
- **El agente nunca se instala como servicio de Windows.** Los servicios corren en la sesión 0
  y no pueden mostrar ventanas. El agente arranca al iniciar sesión cada usuario.
- Los clientes **no abren puertos**: el agente se conecta al servidor, nunca al revés.
- No ejecutes instaladores, no cambies el firewall ni la red de la máquina donde estás
  trabajando sin preguntarme antes.
- La carpeta `legacy/` contiene un script anterior que ya funciona. No lo modifiques.

## Cómo trabajar conmigo

- Avanza **una fase a la vez**. Al terminar cada fase: corre las pruebas, dime qué hiciste,
  cómo lo pruebo a mano y **detente** hasta que te dé el OK.
- Marca la casilla de la fase en `PLAN.md` cuando esté terminada.
- Si algo del plan no se puede hacer o hay una mejor opción, dímelo antes de cambiar la
  arquitectura.
- Explica las decisiones de forma sencilla: esto se presenta ante un ingeniero y tengo que
  poder defenderlo.

## Comandos

- Pruebas: `python -m unittest discover -s tests -v`
- Servidor en local: `python -m servidor --config servidor/config.json`
- Agente en local: `python -m agente --config agente/config.json`
- Simular equipos falsos: `python herramientas/simular_agentes.py --n 4`