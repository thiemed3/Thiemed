# HR Payslip Docs v18

Genera el **PDF** de los recibos de nómina (`hr.payslip`), crea/actualiza un **adjunto** y un **documento** en la app **Documentos**, y permite **enviar por correo** al empleado.  
Actualizado para Odoo **18** con mejoras de robustez y dos acciones separadas: **Generar** y **Generar + Enviar**.

---

## 👀 Resumen de cambios recientes
- **Acciones separadas**:
  - **Generar documento de nómina (PDF + Documentos)**.
  - **Generar Documento y Enviar Nómina**.
  - _(El flujo “Solo enviar” fue retirado.)_
- **Render de PDF reforzado**: se **priorizan plantillas QWeb** (`hr_payroll.report_payslip_lang`, etc.) y, si fallan, **fallback** a cualquier `ir.actions.report` válido de `hr.payslip`.
- **Documentos tolerante**: crea el documento **con carpeta** si existe el modelo de carpetas (`documents.folder`/`documents.workspace`) y **sin carpeta** si no existe —sin romperse.
- **Correo**: el **adjunto PDF se agrega por código**, independiente de la configuración de la plantilla.

---

## ✨ Funcionalidad
Por cada recibo en lote o individual:
1. **Genera el PDF** del recibo.
2. **Crea/actualiza** el **adjunto** (`ir.attachment`) en el registro.
3. **Crea/actualiza** un **documents.document** vinculado al recibo  
   - Usa carpeta **Payroll** si tu base expone carpetas/workspaces.  
   - Asigna **propietario** al usuario interno del empleado (si existe).
4. (**Acción combinada**) **Envía email** al empleado con el **PDF adjunto** y marca `x_doc_sent = True`.

> Idempotente: si ya existe adjunto/documento, **se actualizan** en lugar de duplicarse.

---

## 🧭 Acciones disponibles (lista de Recibos)
- **Generar documento de nómina (PDF + Documentos)**  
  Solo genera y deja trazabilidad en el chatter.
- **Generar Documento y Enviar Nómina**  
  Genera (o actualiza) y **envía** el correo con el PDF adjunto.

> También hay un **cron** (opcional) que ejecuta la **combinada** sobre recibos `state = 'done'` y `x_doc_sent = False`.

---

## 🔁 Tarea programada (cron)
- **Nombre**: `Payslip Docs: generar documento y enviar`
- **Código**:
  ```python
  model.search([('state','=','done'),('x_doc_sent','=',False)], limit=100).action_generate_document_and_send_email()
