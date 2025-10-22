# HR Payslip Docs v18

- Genera el **PDF** del recibo (`hr.payslip`).
- Crea/actualiza un **adjunto** y un **documento** en la app **Documentos** (en carpeta *Payroll* si hay modelo de carpetas).
- **Envía** el PDF por email al empleado (plantilla con `report_template_ids`).
- **Acción masiva** desde lista y **cron** para procesar recibos `done`.

## Notas
- Si tu base no expone `documents.folder`/`documents.workspace`, el documento se crea **sin** `folder_id`.
- El cron usa `x_doc_sent` (arreglado).
