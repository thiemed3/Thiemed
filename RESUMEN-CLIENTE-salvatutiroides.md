# Informe de intervenciones aplicadas en salvatutiroides.cl

**Servidor:** Amazon Lightsail · `54.207.138.184`  
**Sitio:** `salvatutiroides.cl`  
**Fecha:** 28 de septiembre de 2026  
**Estado:** Aplicado y verificado (Etapas 1 y 2 completadas)

---

## Resumen ejecutivo para el cliente

Atendiendo a su autorización, se ejecutó con éxito el plan de contención de memoria y protección perimetral en el servidor. El sitio se encuentra operativo, con un consumo de memoria saludable (aprox. 525 MB usados de 1.9 GB) y protegido contra los vectores de ataque que provocaban las caídas previas.

---

## Detalle de mejoras implementadas

### 1. Endurecimiento de recursos y memoria (Etapa 1)
* **Memoria Swap de 1 GB:** Se configuró un espacio de intercambio (`/swapfile`) con un factor de uso conservador (`vm.swappiness=10`). Esto actúa como colchón ante picos repentinos de tráfico, evitando que el núcleo del sistema mate procesos de manera abrupta (OOM killer).
* **Ajuste de Apache (MPM Prefork):** 
  * Se redujo el límite de conexiones simultáneas concurrentes (`MaxRequestWorkers`) de **150 a 20**. El valor anterior permitía un consumo teórico de hasta 15 GB en una máquina de 2 GB.
  * Se redujo el tiempo máximo de espera por petición (`Timeout`) de 300 a **90 segundos**, impidiendo que peticiones maliciosas retengan procesos durante 5 minutos.
* **Límites de PHP:** Se ajustó el consumo máximo por petición (`memory_limit`) de 256 MB a **128 MB** y el tiempo de ejecución (`max_execution_time`) de 300 a **60 segundos**.

### 2. Recuperación automática ante incidentes (Etapa 1)
* **Políticas de systemd:** Se reconfiguraron los servicios de Apache y MariaDB con `Restart=on-failure` y un reintento automático de 10 segundos. Si en el futuro se produce un pico extremo de consumo, los servicios se reiniciarán solos de manera controlada sin requerir intervención manual.
* **Techos de memoria (Cgroups):** Se establecieron límites preventivos de memoria para evitar que un proceso desbocado acapare el 100% de la RAM del servidor.

### 3. Optimización de Base de Datos (Etapa 1)
* **MariaDB:** Se ajustaron los parámetros de conexiones máximas (`max_connections = 60`) y caché de tablas (`table_open_cache = 600`) para alinearlos a la capacidad real de una instancia de 2 GB de RAM, reduciendo el riesgo de errores *"MySQL server has gone away"*.

### 4. Bloqueo de ataques y seguridad perimetral (Etapa 2)
* **Bloqueo de XML-RPC:** Con base en su confirmación de que no se utiliza la aplicación móvil de WordPress ni Jetpack, se bloqueó por completo el acceso al archivo `xmlrpc.php` desde Apache. Esto neutraliza la principal vía de amplificación de ataques de fuerza bruta y escaneos automatizados.
* **Instalación y activación de Fail2ban:** Se instaló y configuró el sistema de prevención de intrusiones con 3 filtros activos para Apache (`apache-auth`, `apache-badbots`, `apache-overflows`), encargado de bloquear automáticamente las IPs que intenten vulnerar los formularios o realizar peticiones anómalas repetitivas.

---

## Estado actual de verificación en el servidor

* **Memoria RAM:** ~525 MB utilizados · ~1.4 GB disponibles.
* **Memoria Swap:** 1.0 GiB activa y disponible.
* **Servicios activos:** Apache2, MariaDB y Fail2ban operando sin errores.
