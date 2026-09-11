# Guion de demostración (5 minutos)

Presentación del sistema **Ciber Mensajería** en el laboratorio `lab.lan`. Pensado para
mostrarlo en proyector desde el panel en DC01, con al menos un cliente Windows y uno Linux
conectados.

**Requisitos previos (antes de entrar al aula):**

- Servidor corriendo en DC01 (tarea programada o proceso manual).
- Agentes instalados y conectados en 2–3 equipos de prueba.
- Panel abierto en DC01: `http://localhost:8080`
- Para la parte de sesión: tener listo un equipo con sesión de **2 minutos** y
  `avisos_minutos: [1]` en la config del servidor (ver abajo), o una sesión de 15 min ya
  iniciada si prefieres no tocar la config.

---

## Minuto 0:00 — Contexto (30 s)

> «En un cibercafé, desde caja se ve quién está en cada PC y se le avisa cuando se acaba el
> tiempo. Replicamos eso en nuestra red del laboratorio: el servidor está en DC01, nuestro
> Windows Server del dominio `lab.lan`, y en cada cliente hay un agente pequeño en Python que
> arranca con el usuario y se conecta al servidor. Los clientes **no abren puertos**; solo
> el agente inicia la conexión hacia DC01.»

**En pantalla:** panel con la tabla de equipos conectados (hostname, SO, usuario, IP).

---

## Minuto 0:30 — Estado en tiempo real (45 s)

> «Esta tabla se actualiza cada dos segundos. Cada fila es un equipo con sesión abierta.
> El icono indica el sistema operativo: Windows, Linux o macOS. Si alguien se desconecta,
> pasa a *Desconectado*; si vuelve la red, el agente se reconecta solo.»

**Acción:** señala 2–3 equipos con estado **Conectado** y nombra el usuario del dominio
(p. ej. `dquan` en Ubuntu).

---

## Minuto 1:15 — Aviso emergente y confirmación (1 min)

> «Voy a mandar un aviso a un solo equipo. La ventana sale encima de todo, con el título
> *Cibercafé*, y el usuario tiene que pulsar *Entendido*. Eso no es solo cortesía: el
> servidor registra el *visto* y lo vemos aquí en la columna *Visto ✓*.»

**Acción:**

1. Marca la casilla de un equipo Linux o Windows.
2. Escribe: «Prueba de demostración — por favor confirma.»
3. Nivel: **Aviso** → **Enviar aviso**.
4. En el cliente (o pide a un compañero): pulsar **Entendido**.
5. En el panel: la columna **Visto ✓** muestra la hora.

> «Si mandamos el mismo mensaje a varios equipos a la vez, cada uno confirma por separado.»

*(Opcional, 10 s: botón rápido «Te quedan 5 minutos» a *todos*.)*

---

## Minuto 2:15 — Sesión con tiempo (1 min 30 s)

> «Lo típico del cibercafé: asignar tiempo. Inicio una sesión en este equipo; el usuario ve
> un contador en la esquina. El servidor avisa solo cuando queda poco tiempo — por defecto
> a los 5 y 1 minuto — y al terminar bloquea la pantalla con el mensaje de pasar a caja.»

**Acción (sesión corta de 2 min, recomendada en clase):**

1. Selecciona un equipo de demostración.
2. Pulsa **Iniciar 2 min** (o equivalente en el panel).
3. Muestra en el cliente el contador **⏱** (esquina inferior derecha).
4. Al llegar el aviso automático (1 min con config de prueba): señala la ventana en el
   cliente.
5. Al llegar a cero: pantalla de bloqueo a pantalla completa.

> «Desde caja puedo alargar el tiempo: *+15 min* desbloquea y sigue la sesión.»

**Acción:** pulsa **+15 min** en el panel → el cliente se desbloquea y el contador continúa.

*(Si usas sesión de 15 min real, solo inicia la sesión y explica que los avisos saldrán a
los 5 y 1 minuto; no esperes en silencio — pasa a la siguiente sección.)*

---

## Minuto 3:45 — Resiliencia (45 s)

> «Si se cae el cable o el Wi‑Fi, el agente no se queda colgado: reintenta con espera
> creciente hasta 30 segundos. Y si reiniciamos DC01, cuando el servidor vuelve, todos los
> agentes reaparecen solos — no hay que tocar cada PC.»

**Acción:** si ya probaste reconexión o reinicio de DC01 en el checklist, menciónalo con una
fila del panel que pasó de *Desconectado* a *Conectado*. Si no hay tiempo en vivo, di que
está documentado en `docs/checklist-pruebas.md`.

---

## Minuto 4:30 — Cierre técnico (30 s)

> «Todo es Python estándar, sin instalar paquetes en los clientes. Un solo protocolo JSON
> por TCP en el puerto 5050. El panel es HTML y JavaScript servido por el mismo servidor,
> sin depender de internet. Los instaladores dejan el token y el autostart configurados por
> sistema operativo. El script anterior del curso usaba `msg.exe` y SSH; este agente unifica
> Windows, Linux y macOS y nos da el *visto* y las sesiones en un solo lugar.»

**En pantalla:** vuelve a la tabla con varios equipos **Conectado** y, si queda tiempo, abre
**Historial** o menciona que los eventos quedan registrados.

---

## Notas para el presentador

| Tema | Detalle |
|---|---|
| Config rápida para demo de 2 min | En `C:\CiberMensajeria\config.json`: `"avisos_minutos": [1]`. Reinicia el servidor. Restaura `[5, 1]` después. |
| Si un equipo no aparece | No improvises en vivo: usa otro de la tabla y menciona DNS/firewall (ver checklist). |
| Debian sin escritorio | El aviso va por `wall` en todas las terminales; no hay ventana tkinter. |
| Wayland en Ubuntu | La ventana puede quedar detrás en casos raros; es limitación conocida de tkinter. |
| Pregunta «¿es seguro el bloqueo?» | «Es un bloqueo de cibercafé para avisar al usuario, no un candado de seguridad. Se quita con *Desbloquear* o extendiendo la sesión.» |

---

## Cronómetro resumido

| Tiempo | Bloque |
|---|---|
| 0:00 – 0:30 | Qué es y arquitectura (DC01 + agentes) |
| 0:30 – 1:15 | Tabla del panel, equipos conectados |
| 1:15 – 2:15 | Mensaje manual + columna Visto ✓ |
| 2:15 – 3:45 | Sesión, contador, aviso automático, bloqueo, +15 min |
| 3:45 – 4:30 | Reconexión y reinicio del servidor |
| 4:30 – 5:00 | Stack técnico y cierre |
