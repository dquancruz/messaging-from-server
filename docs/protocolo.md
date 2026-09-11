# Protocolo agente ↔ servidor

Implementado en `comun/protocolo.py`.

## Transporte

- TCP, puerto **5050** (`servidor.puerto_agentes` en `config.json`).
- Cada mensaje es un objeto JSON en UTF-8, en una sola línea terminada en
  `\n`. No hay framing adicional: se lee con `readline()`.
- Todo mensaje lleva `"tipo"`. Los que requieren respuesta llevan `"id"`
  (uuid4), por ejemplo `mensaje` → el agente contesta `visto` con ese mismo
  `id`.
- Un mensaje (la línea completa, con el `\n`) de más de **64 KB** se
  rechaza (`TAMANO_MAXIMO_MENSAJE`). El servidor crea el socket con
  `limit=TAMANO_MAXIMO_MENSAJE`, así que una línea sin salto que supere ese
  tamaño hace que `readline()` levante `asyncio.LimitOverrunError` en vez de
  seguir acumulando memoria indefinidamente.
- Latido: el agente manda `ping` cada **15 s** (`INTERVALO_PING`). El
  servidor marca el equipo como desconectado si pasan **45 s**
  (`TIMEOUT_DESCONEXION`) sin recibir nada de él — se implementa con un
  `readline()` con ese timeout; si expira, se cierra la conexión.
- Reconexión del agente con espera creciente: 1, 2, 4, 8, 16, 30 s (tope
  30), en `ESPERAS_RECONEXION`.
- Un mismo equipo puede tener varias conexiones activas (una por usuario
  con sesión abierta). Los mensajes a un equipo se mandan a todas sus
  conexiones.

## Agente → servidor

| tipo | campos | notas |
|---|---|---|
| `hola` | `token`, `equipo`, `so` (`windows`/`linux`/`macos`), `version_so`, `usuario`, `version_agente` | Primer mensaje obligatorio de toda conexión. `equipo` es el hostname; el servidor lo normaliza a minúsculas. |
| `visto` | `id` | El usuario cerró un `mensaje` con "Entendido". |
| `ping` | — | Latido, cada 15 s. |

## Servidor → agente

| tipo | campos | notas |
|---|---|---|
| `bienvenido` | `sesion` (segundos restantes o `null`), `bloqueado` (bool) | Respuesta a un `hola` aceptado. En la Fase 1, siempre `sesion: null, bloqueado: false` (las sesiones llegan en la Fase 4). |
| `rechazado` | `motivo` | Token incorrecto, o el primer mensaje no fue `hola`. El servidor cierra la conexión después de mandarlo. |
| `mensaje` | `id`, `titulo`, `texto`, `nivel` (`info`/`aviso`/`critico`), `pedir_visto` (bool) | Se implementa a partir de la Fase 2/3 (panel + ventana emergente). |
| `sesion` | `restante` (segundos) o `null` | Fase 4. |
| `bloquear` | `texto` | Fase 4. |
| `desbloquear` | — | Fase 4. |
| `pong` | — | Respuesta a `ping`. |

## Errores de protocolo

`comun.protocolo.ErrorProtocolo` se levanta para: JSON inválido, línea que
no es un objeto, `tipo` ausente o desconocido, campos requeridos faltantes,
o mensaje que supera `TAMANO_MAXIMO_MENSAJE`. El servidor nunca deja que un
mensaje mal formado tumbe la conexión completa por una excepción no
controlada: lo registra en el log y sigue (o cierra esa conexión en
particular, si el problema fue en el saludo).
