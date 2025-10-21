# HR Payslip → Documents & Email (Odoo 18)

Este módulo complementa **hr_payroll** y **documents** en Odoo 18 para:
- Generar el **PDF del recibo de nómina** (`hr.payslip`).
- Guardarlo como **adjunto** y crear/actualizar un **documento** en una carpeta de Documentos.
- **Asignar propietario** del documento al usuario interno del empleado (si existe).
- **Enviar por correo** el PDF al empleado con una plantilla de email.
- Ejecutar la acción **masivamente** desde el listado y **automáticamente** vía **cron**.

## Requisitos
- Odoo 18
- Módulos: `base`, `mail`, `hr`, `hr_payroll`, `documents`.

## Uso
1. Desde el listado de **Recibos** (`Nómina → Recibos`), selecciona uno o varios y usa la acción:
   **“Generar Documento y Enviar Nómina”**.
2. El sistema:
   - Renderiza el informe **PDF** de cada recibo.
   - Crea/actualiza el **adjunto** y el **documento** en Documentos.
   - Asigna como **propietario** del documento al usuario del empleado (si existe).
   - Envía el correo usando la plantilla **[RRHH] Envío de Recibo de Nómina**.
   - Marca el recibo con **“Nómina enviada”**.

## Automatización (Cron)
Se incluye una tarea programada **cada 1 hora** que procesa hasta 100 recibos en estado `done` y no enviados (`doc_sent = False`).
Corre con el usuario **Administrador** para evitar problemas de permisos en Documentos.

## Carpetas de Documentos
El módulo creará (si no existen):
- Carpeta raíz: **Shared** (configurable)
- Subcarpeta: **Payroll** (configurable)

Parámetros del sistema (Ajustes → Técnico → Parámetros del sistema):
- `hr_payslip_docs_v18.root_folder_name` → nombre de la carpeta raíz (por defecto: `Shared`)
- `hr_payslip_docs_v18.sub_folder_name`  → nombre de la subcarpeta (por defecto: `Payroll`)

## Prioridad del correo del empleado
Se intentará enviar al primer correo disponible en el siguiente orden:
1. `employee_id.user_id.partner_id.email`
2. `employee_id.work_contact_id.email` (si existe)
3. `employee_id.address_home_id.email`
4. `employee_id.work_email` (si existe)

Si no se encuentra correo, se registra un mensaje en el recibo y no se envía.

## Notas de implementación
- **Binding** de la acción de servidor mediante `binding_model_id`/`binding_type` (Odoo 18); **no** se usa `ir.values`.
- El **cron** define `user_id` (Administrador) para asegurar acceso a `documents`.
- No se añaden nuevas ACL sobre `hr.payslip` para evitar conflictos con las oficiales.
- Los textos están preparados para internacionalización; en Python se usa `_()`.

## Desinstalación
La desinstalación no elimina adjuntos ni documentos ya creados.

## Licencia
OEEL-1
