# Informe técnico — Diagnóstico de caídas del sitio salvatutiroides.cl

**Servidor:** Amazon Lightsail · `54.207.138.184` (São Paulo, sa-east-1)
**Sitio:** salvatutiroides.cl
**Fecha del diagnóstico:** 25 de septiembre de 2026
**Tipo de trabajo:** diagnóstico de solo lectura. **No se aplicaron cambios.**

---

## 1. Resumen ejecutivo

El sitio se cae de forma intermitente porque el servidor se queda sin memoria (RAM) y,
al agotarse, el sistema operativo mata procesos esenciales —principalmente la base de
datos MariaDB y los procesos de Apache que sirven el sitio— dejando la web sin responder.

La causa no es una falla del hosting ni del proveedor: es una **combinación de dos
problemas de configuración que se refuerzan entre sí**:

1. **La configuración del servidor web permite un consumo de memoria muy superior a la
   capacidad de la máquina.** Apache está habilitado para atender hasta 150 peticiones
   simultáneas y cada una puede reservar hasta 256 MB. En el peor caso, el servidor podría
   intentar consumir unos 15 GB en una máquina que solo tiene 1,9 GB.
2. **El sitio está recibiendo ataques automatizados de fuerza bruta** contra el formulario
   de acceso a WordPress y el protocolo XML-RPC. Estas peticiones hostiles ocupan procesos
   del servidor durante hasta 5 minutos cada una, y son justamente las que desbordan la
   memoria.

El resultado es una caída en cadena: las peticiones de ataque consumen la memoria →
el sistema mata la base de datos → el sitio devuelve errores → la base de datos tampoco
logra recuperarse automáticamente.

**Buena noticia:** se verificó la integridad del código de WordPress (núcleo y los 5
plugins instalados) y **el resultado fue correcto en todos los casos**. No hay indicios de
software malicioso ni de una intrusión. El problema es de capacidad y de configuración,
lo que significa que es solucionable con ajustes concretos y de bajo riesgo.

---

## 2. Diagnóstico: por qué se cae el servidor

### 2.1 Hallazgos técnicos

| Componente | Configuración actual | Problema |
|---|---|---|
| Servidor | Amazon Lightsail, Debian 12 | — |
| Memoria RAM | 1,9 GB, **sin memoria de intercambio (swap)** | Sin colchón: al agotarse la RAM el sistema mata procesos de inmediato |
| Disco | 59 GB, 8 % utilizado | Correcto, sin riesgo |
| Apache (servidor web) | Até 150 peticiones simultáneas | Capacidad muy superior a la memoria disponible |
| Timeout de Apache | 300 segundos (5 min) | Cada petición hostil retiene un proceso durante 5 minutos |
| PHP 8.3 (motor de WordPress) | 256 MB por petición, 300 segundos por ejecución | El peor caso combinado con Apache equivale a ~38 GB de demanda teórica |
| MariaDB (base de datos) | 151 conexiones máximas, 128 MB de memoria en caché | Sin límites de memoria asignados |
| Sistema | Sin límites de memoria por servicio | No existe ninguna barrera que proteja al sistema |
| Reinicio automático | Apache solo reinicia ante cierre ordenado | Si un proceso es eliminado por falta de memoria, el servicio no se recupera |
| Seguridad perimetral | Sin WAF, sin fail2ban, sin firewall local activo | No existe filtrado de tráfico hostil |

### 2.2 Consumo de memoria observado

En el momento del diagnóstico, con el servidor funcionando con normalidad:

- 7 procesos de Apache: entre 95 MB y 105 MB cada uno.
- Proceso principal de Apache: 44 MB.
- Base de datos MariaDB: 177 MB.
- **Total aproximado del sitio web: 650 MB–700 MB de los 1,9 GB disponibles.**

El margen actual existe porque el tráfico de ataque no estaba activo en ese momento. Cuando
se produce un pico de peticiones hostiles, el consumo crece hasta agotar la memoria.

### 2.3 Registros del sistema

El historial del sistema registra eventos de agotamiento de memoria (OOM) en al menos
cuatro reinicios previos, con las siguientes características:

- El núcleo del sistema (kernel) identificó el agotamiento de memoria de forma global.
- Procesos eliminados: `mariadbd` (base de datos) y `apache2` (servidor web).
- El servicio de base de datos registró: *"A process of this unit has been killed by the
  OOM killer"*.
- Un reinicio anterior duró aproximadamente 30 segundos antes de ser reiniciado,
  lo que indica un cierre no limpio.

Esto confirma que las caídas no son aleatorias ni del hardware, sino que corresponden a
los episodios de memoria agotada registrados.

### 2.4 Tráfico de ataque identificado

Del análisis del registro de accesos del sitio web, sobre un total de aproximadamente
**369.000 peticiones** registradas:

| Objetivo del ataque | Peticiones detectadas | Interpretación |
|---|---|---|
| `xmlrpc.php` | ~70.000 | Protocolo de WordPress usado para fuerza bruta de credenciales. Es la principal vía de amplificación del ataque. |
| `wp-login.php` | ~43.700 | Intentos automatizados de adivinar usuario y contraseña del panel de administración. |
| `wp-cron.php` | ~5.700 | Tareas automáticas disparadas por los propios ataques. |
| `/.env` y otros archivos sensibles | ~1.400 | Escaneo en busca de archivos de configuración expuestos. |
| **Errores HTTP 500** | **5.158** | Resultado directo de la falta de memoria y la caída de la base de datos. |

Direcciones IP que destacan con mayor actividad:

- `119.40.84.186` — 18.059 intentos de acceso al panel y 8.609 al protocolo XML-RPC.
- `185.235.15.48` — 13.926 intentos de acceso al panel de administración.
- `149.102.154.100`, `185.207.251.4`, `194.163.170.141` — miles de peticiones de
  reconocimiento sobre rutas que no existen.

El volumen es consistente con ataques automatizados de fuerza bruta contra WordPress,
originados desde múltiples servidores en la nube. **Al provenir de muchas direcciones IP
distintas, el bloqueo manual de IPs resulta insuficiente** y se requiere una estrategia de
filtrado en profundidad.

### 2.5 Errores registrados en el sitio

El registro de errores del sitio muestra, de forma consistente:

- **Agotamiento de memoria en PHP** durante el procesamiento de las peticiones.
- **Pérdida de conexión con la base de datos** (*"MySQL server has gone away"*).
- **Bloqueos de base de datos** (*"Lock wait timeout exceeded"*) por consultas que quedan
  esperando recursos ya inexistentes.

Estos tres mensajes forman una secuencia: se agota la memoria → se mata la base de datos →
las consultas se bloquean y fallan.

---

## 3. Plan de acción propuesto

El plan se organiza en tres etapas, ordenadas por prioridad y relación entre costo y
beneficio. Las etapas 1 y 2 son de bajo riesgo y reversibles.

### Etapa 1 — Contención inmediata (bajo riesgo, reversible)

Objetivo: evitar que el servidor vuelva a quedarse sin memoria.

1. **Habilitar memoria de intercambio (swap) de 1 GB.** No reemplaza la solución definitiva,
   pero impide que una descarga de memoria termine en una caída abrupta, dando tiempo a que
   el sistema se recupere solo.
2. **Limitar las peticiones simultáneas de Apache** de 150 a un número acorde a la memoria
   disponible. En conjunto con el punto 3, esto reduce drásticamente el consumo máximo
   théorique de memoria del servidor web.
3. **Reducir el consumo por petición de PHP** de 256 MB a 128 MB y el tiempo máximo de
   ejecución de 5 minutos a 1 minuto. Esto acota el daño por petición hostil individual.
4. **Asignar límites de memoria por servicio** para que el sistema proteja al conjunto
   cuando un componente intente crecer sin control.
5. **Configurar el reinicio automático** de Apache y MariaDB para que ambos se levanten
   solos tras cualquier interrupción, con una política de reintentos más tolerante.
6. **Ajustar parámetros de la base de datos** para limitar conexiones simultáneas y
   reducir el consumo de memoria en la caché.

### Etapa 2 — Protección frente a ataques

Objetivo: reducir el tráfico hostil que llega a la aplicación.

7. **Bloquear o limitar el protocolo XML-RPC** (`xmlrpc.php`), principal vía de amplificación
   del ataque. Su bloqueo es seguro siempre que no se utilice la aplicación móvil oficial de
   WordPress ni el plugin Jetpack.
8. **Aplicar límites de solicitudes al formulario de acceso** al panel de administración y
   bloquear las direcciones IP queecnicamente muestran actividad de ataque.
9. **Implementar un firewall de aplicaciones web (WAF)** con reglas automáticas de bloqueo
   por intentos fallidos. Se recomienda un sistema como fail2ban o una solución
   gestionada externa, dado que actualmente no existe ninguno instalado.
10. **Evaluar incorporar Cloudflare** (plan gratuito) como capa de protección que absorba el
    tráfico de ataque antes de que alcance al servidor.

### Etapa 3 — Continuidad y prevención

Objetivo: detectar cualquier problema a tiempo y sostener el servicio a largo plazo.

11. **Configurar monitoreo externo y alertas** de disponibilidad. A la fecha no existe
    ningún sistema de monitoreo activo que avise cuando el sitio deja de responder.
12. **Programar copias de seguridad (snapshots) automáticos** del servidor.
13. **Evaluar migrar a PHP-FPM con Apache en modo event** y/o aumentar la memoria
    disponible del plan de Lightsail. Ambas opciones son mejoras estructurales de mayor
    envergadura, a evaluar en una segunda etapa.
14. **Actualizar los plugins con versiones nuevas disponibles** (`safe-svg`,
    `google-site-kit`, `simple-tags`). El mantenimiento al día de las dependencias del
    sitio es la medida de seguridad más básica y reduce la superficie atacable. Se
    recomienda hacerlo en la misma visita que la Etapa 1, con copia de seguridad previa.

### Verificación de seguridad realizada

| Componente | Resultado |
|---|---|
| Núcleo de WordPress | ✓ Verificación correcta |
| Plugins instalados (5 de 5) | ✓ Verificación correcta, sin código alterado |
| Tema activo (Divi 5.13.1) | Sin actualizaciones pendientes detectadas |
| Plugins desactualizados | 3 con versión nueva disponible (`safe-svg`, `google-site-kit`, `simple-tags`) |
| Base de datos | No accesible desde Internet (correcto) |
| Archivo de configuración | Permisos restrictivos (correcto) |

---

## 4. Estado actual y próximos pasos

**No se realizó ningún cambio en el servidor.** Todo el diagnóstico fue de solo lectura.
El sitio se encuentra actualmente **operativo y en línea**.

Se requiere autorización del cliente para iniciar la **Etapa 1**, que es de bajo riesgo,
totalmente reversible y no afecta el contenido del sitio. Antes de aplicarla, se realizará
una copia de seguridad de los archivos de configuración modificados.

**Preguntas abiertas para definir el alcance:**

1. ¿Se utiliza la aplicación móvil oficial de WordPress o el plugin Jetpack? Esta
   información determina si es posible bloquear el protocolo XML-RPC de inmediato.
2. ¿Se autoriza aplicar únicamente la Etapa 1 (contención) o también la Etapa 2
   (protección frente a ataques)?
3. ¿Se autoriza ampliar la memoria del plan de Lightsail, o se mantiene la
   configuración actual?

---

## 5. Anexo — Detalle técnico de la configuración actual

Valores obtenidos durante el diagnóstico, para referencia del equipo técnico.

**Servidor**
- Sistema: Debian 12, kernel 6.1.0-53-cloud-amd64
- Memoria: 1,9 GB · Swap: 0
- Disco: 59 GB (8 % utilizado)

**Apache**
- Módulo de concurrencia: `prefork` · Versión: 2.4.68
- Peticiones simultáneas máximas: 150
- Servidores iniciales / mínimos / máximos en espera: 5 / 5 / 10
- Timeout: 300 segundos · KeepAlive: activado (5 segundos)
- Límites asignados por servicio: ninguno
- Política de reinicio: `Restart=on-abort` (no cubre fallo por memoria)

**PHP 8.3 (SAPI Apache)**
- Memoria por petición: 256 MB
- Tiempo máximo de ejecución: 300 segundos
- Tiempo máximo de recepción de datos: 60 segundos
- Tamaño máximo de subida: 64 MB
- Límites asignados por servicio: ninguno

**MariaDB**
- Versión: 10.11.18
- Conexiones máximas: 151 · Conexiones simultáneas observadas: 1 (máximo histórico: 28)
- Memoria en caché InnoDB: 128 MB
- Tamaño máximo de tabla temporal: 16 MB
- Límites asignados por servicio: ninguno
- Política ante falta de memoria: detener el servicio

**WordPress**
- Versión: 7.1.2 · Tema: Divi 5.13.1
- Plugins activos: `media-library-assistant`, `safe-svg`, `google-site-kit`, `wp-mail-smtp`
- Plugin inactivo: `simple-tags`
- **Actualizaciones de plugins pendientes:** `safe-svg`, `google-site-kit` y `simple-tags`
  tienen versión nueva disponible. Se recomienda mantener los plugins al día.

**Registro de ataques (principales direcciones IP)**

| Dirección IP | Peticiones | Actividad principal |
|---|---|---|
| `149.102.154.100` | 60.848 | Reconocimiento automatizado de rutas |
| `185.207.251.4` | 30.424 | Reconocimiento automatizado de rutas |
| `194.163.170.141` | 30.424 | Reconocimiento automatizado de rutas |
| `119.40.84.186` | 26.676 | **Fuerza bruta al panel y XML-RPC** |
| `185.235.15.48` | 13.972 | **Fuerza bruta al panel de administración** |

---

*Informe generado por Tierra Nube — Diagnóstico de solo lectura, 25 de septiembre de 2026.*
*Las modificacionesulingas requieren autorización previa del cliente.*
