# Reportes de remuneraciones de Thiemed — Odoo 19

Compatibilidad de acceso a **Nómina general** y **Certificado de Antigüedad**.
El módulo se implementa en el repositorio principal; usa las versiones de
`payroll_cl` e `inventory_cl` registradas por Thiemed.

## Informes reutilizados

| Informe | Acción original | Modelo |
| --- | --- | --- |
| Nómina general | `l10n_cl_hr.payslip_general_report` | `hr.payslip.run` |
| Certificado de Antigüedad | `l10n_cl_hr_payroll_reports.hr_payroll_certificados_antiguedad` | `hr.version` |

Las acciones conservan sus nombres y plantillas originales. El módulo no crea
acciones `ir.actions.report` adicionales ni modifica la acción estándar
`hr_payroll.action_hr_payslip_run`.

## Pie exclusivo de los dos reportes

La versión `19.0.1.0.1` sustituye los emojis del pie por `Tel.:`, `Correo:`,
`Web:` y `RUT:` únicamente al renderizar estos dos documentos. Conserva el
contenido HTML y los datos existentes de contacto.

Se utilizan variantes QWeb con herencia **primaria** de los layouts Striped y
Standard, seleccionadas mediante un dispatcher propio. Solo Nómina general y
el documento del Certificado de Antigüedad invocan ese dispatcher. Los layouts
corporativos originales, `res.company.report_footer` y la factura no cambian.

No se alteran tablas, tipografía, márgenes, formato de papel, saltos de página,
campos laborales ni importes. Nómina general puede seguir ocupando dos páginas.

## Uso

### Nómina general

1. Entrar en **Nómina → Informes → Nómina general**.
2. Comprobar empresa, fechas y cantidad de liquidaciones del periodo.
3. Pulsar **Nómina general** en la fila, o abrir el periodo y pulsar el botón
   del mismo nombre en su formulario de consulta.

Se necesita el grupo existente `hr_payroll.group_hr_payroll_user`, además de
los permisos de lectura de todos los registros del informe. Las vistas propias
de este módulo son de consulta, sin el controlador especial de creación de
periodos de Odoo 19.

La impresión exige un solo periodo. Se rechazan periodos inexistentes o vacíos,
fechas incompatibles, liquidaciones sin líneas y compañías diferentes. La
validación se ejecuta también al renderizar la acción original directamente.

Se mantienen exactamente los conceptos y la agregación del reporte original:
lee `line.total`, conserva sus clasificaciones, su agrupación por nombre y todas
las liquidaciones vinculadas, sin introducir un filtro nuevo por estado. Incluye
haberes, descuentos, aportes patronales, anticipos y líquido.

Para evitar un PDF parcial, se compara la cantidad de liquidaciones y líneas
accesibles mediante ORM con dos consultas SQL de **solo conteo**. Esas consultas
no obtienen identidades ni importes, y solo permiten rechazar una lectura
incompleta. Todos los datos impresos se leen mediante ORM y con el usuario real.

### Certificado de Antigüedad

1. Abrir el trabajador en **Empleados** o **Nómina → Empleados**.
2. Pulsar **Certificado de Antigüedad** en la cabecera.

Se necesita el grupo existente `hr.group_hr_manager`: Odoo 19 restringe a ese
grupo las fechas contractuales y otros campos usados por el certificado. El
módulo no concede grupos ni permisos adicionales.

Si la ficha se abrió con una versión laboral seleccionada, el botón valida esa
versión. En otro caso, la resuelve con `_get_version()` para la fecha de emisión.
Se comprueban trabajador, empresa, permisos, actividad, fechas y los datos que
el texto original necesita. Una versión histórica, futura, finalizada o sin
datos suficientes produce un error explicativo, en lugar de un certificado
vacío o con datos de otra versión.

La herencia QWeb conserva el contenido y cambia exclusivamente:

- Fecha de ingreso: `contract_date_start`, en lugar del inicio de una versión.
- Fecha de término contractual usada por la condición de vigencia.
- Identificación del trabajador desde la versión validada.
- Lectura del idioma sin elevar permisos.

Se mantiene el texto original, sin añadir años de servicio, cláusulas ni cálculos.
El botón pasa `report_pdf_no_attachment=True` para descargar sin guardar un
adjunto automáticamente. El comportamiento de adjuntos de otros accesos a la
acción original permanece definido por dicha acción.

## Instalación y actualización

Agregar la raíz del repositorio a `addons_path` e instalar
`thiemed_payroll_report_compatibility`. Para actualizar, actualizar únicamente
ese módulo. Las dependencias de nómina deben estar ya instaladas y disponibles.

Ejemplo para una **copia local aislada**, usando la CLI de Odoo 19:

```bash
odoo -d thiemed_reportes_test \
  -i thiemed_payroll_report_compatibility \
  --max-cron-threads=0 --stop-after-init
```

La actualización utiliza `-u thiemed_payroll_report_compatibility`. La asociación
de vistas de la acción propia es idempotente: conserva una vista `list` y una
`form` después de actualizar.

## Pruebas

Ejecutar en una copia de pruebas con los módulos y datos existentes:

```bash
odoo -d thiemed_reportes_test \
  -u thiemed_payroll_report_compatibility \
  --test-enable --test-tags=/thiemed_payroll_report_compatibility \
  --max-cron-threads=0 --stop-after-init
```

También deben configurarse los parámetros de conexión, `addons_path` y
`data_dir` del entorno aislado. Para PDF real, `report.url` debe apuntar a su
propio servidor HTTP, no a la instancia de origen.

La suite usa periodos y versiones existentes. No crea ni modifica contratos,
liquidaciones, reglas salariales, estructuras ni asientos como fixtures. Crea
usuarios y reglas de acceso temporales dentro de las transacciones de prueba;
los escenarios de fechas y compañías incompatibles usan lecturas simuladas en
memoria. En una base sin datos comparables, las clases se omiten explícitamente.

Cobertura:

- Reutilización de acciones, vistas de consulta y acción estándar intacta.
- Puente explícito empleado → versión, con comprobación de pertenencia.
- Periodo único, fechas, empresas y datos obligatorios.
- Rechazo de consolidación parcial bajo reglas de acceso restrictivas.
- Permisos en botones y en renderizado directo.
- Conciliación de todas las secciones contra las líneas almacenadas por SQL.
- Fecha contractual frente a fecha efectiva de versión.
- Generación real de ambos PDF y comprobación de texto.
- Menú, botones y descarga PDF mediante HTTP autenticado de Odoo.
- Comparación de conteos y huellas completas de las tablas protegidas antes y
  después de generar los PDF.

### Evidencia local persistente

La verificación de integridad se ejecutó con un script auxiliar que no forma
parte del módulo versionado, desde un shell de Odoo y limitado a la copia local
de pruebas. Ese script configura solamente las URL técnicas de la copia, registra
las huellas **antes** de instalar y las contrasta después de instalar, probar y
generar los PDF.

Los artefactos se guardan fuera del código: `baseline.json`, `after.json`,
`evidence.json`, ambos PDF y sus textos. Contienen datos de trabajadores; no
deben añadirse al repositorio.

Las huellas incluyen empleados, versiones, periodos, liquidaciones, líneas,
entradas, días trabajados, reglas, estructuras, asientos y apuntes contables.

## Reversión y validación posterior

Para revertir la funcionalidad, desinstalar únicamente este módulo de
compatibilidad mediante Odoo y reiniciar con el código correspondiente. Sus
menús, vistas heredadas y validaciones desaparecen; las acciones originales
siguen perteneciendo a sus módulos de origen. Comprobar las huellas de datos y
la navegación estándar después de la reversión.

El paso a Staging requiere autorización independiente. Allí debe instalarse el
módulo, repetir permisos, navegación y PDFs con el código exacto de esa
instancia, y conciliar contra Odoo 18 si se dispone de una base equivalente o de
PDF originales comparables. Una cabecera PDF válida no sustituye esas pruebas.

## Resultado local — 30 de octubre de 2026

- Worktree: `/home/natu/odoo-lab/thiemed-v19-reportes`.
- Rama: `feature/payroll-report-compatibility-v19`, base `b6023cb`.
- Submódulos conservados: `payroll_cl=eac5a1c`, `inventory_cl=d6da8f1`.
- PostgreSQL y filestore propios, copiados de la base local de pruebas.
- Contenedores: `thiemed-reportes-db` y `thiemed-reportes-web`, en la red interna
  `thiemed-reportes-local`. El proxy `thiemed-reportes-access` publica solamente
  `http://127.0.0.1:8074`; Odoo y PostgreSQL permanecen en la red interna. Esa
  configuración auxiliar de proxy no forma parte del módulo versionado.
- Módulo instalado y actualizado; actualización final idempotente.
- Suite final: **17 pruebas, 0 fallos, 0 errores**, incluidas descargas HTTP
  autenticadas y denegación HTTP 403 para usuarios sin permisos.
- Nómina de septiembre de 2026: 12 liquidaciones; todas las secciones coinciden
  con las líneas almacenadas. PDF de 2 páginas, 35.934 bytes.
- Certificado: PDF de 1 página, 28.715 bytes; identidad, datos laborales, fecha
  contractual y texto revisados. Revisión visual de los tres PNG de los PDF.
- Las 11 huellas completas coinciden entre antes de instalar y después de las
  pruebas y la generación final. Incluyen las 307 liquidaciones, 7.731 líneas,
  203.308 asientos y 758.840 apuntes de la copia local.
- Evidencia exportada a `/tmp/opencode/thiemed-payroll-report-evidence/`:
  `final-tests.log`, `baseline.json`, `after.json`, `evidence.json`, PDF y PNG.

Limitaciones observadas:

- Los valores almacenados de septiembre contienen una diferencia aritmética de
  **$1** entre el líquido y haberes menos descuentos y anticipos. El consolidado
  reproduce exactamente las líneas existentes; su causa queda pendiente de
  conciliación con el origen.
- Algunos pictogramas del pie corporativo compartido aparecen como glifos en
  el render local. El contenido principal, las tablas y los datos son legibles.
- La copia conserva advertencias preexistentes de vistas Studio y de campos
  obligatorios de nómina con valores nulos. No bloquearon la suite final.
- La validación funcional automatizada cubre vistas, menú, botones y PDF por
  HTTP, sin una sesión gráfica de navegador automatizada.
- Comparación con datos equivalentes de Odoo 18 y validación en Staging
  pendientes de disponibilidad y autorización, respectivamente.
