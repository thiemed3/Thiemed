# 📄 Gestión Automática de Recibos de Nómina (CL)

**Versión:** 18.0 | **Para:** Odoo 18 Enterprise | **País:** Chile

---

## 🎯 ¿Qué hace este módulo?

Automatiza completamente la generación y envío de recibos de nómina a los empleados:

✅ **Genera automáticamente** el PDF del recibo al confirmar una nómina  
✅ **Guarda el documento** en la aplicación Documentos (carpeta "Nóminas")  
✅ **Envía por email** el recibo al empleado automáticamente  
✅ **No duplica** - Si ya se generó, no lo vuelve a hacer  

---

## 👥 ¿Para quién es?

### 👔 Personal de RRHH
- Confirma nóminas como siempre
- El sistema hace todo solo: PDF + guardado + email

### 👨‍💼 Empleados
- Reciben su recibo por email automáticamente
- Pueden verlo en el Portal de Empleado > Documentos

### 👨‍💼 Gerentes/Administradores
- Acceso completo a todos los recibos
- Control centralizado en app Documentos

---

## 🚀 Cómo usar (Paso a paso)

### Para personal de RRHH:

#### 1️⃣ Confirmar nómina (como siempre)
```
Nómina > Crear nómina
- Seleccionar empleado
- Verificar período
- Calcular
- Click en "Confirmar"
```

#### 2️⃣ ¡Eso es todo!
El sistema automáticamente:
- ✅ Genera el PDF del recibo
- ✅ Lo guarda en Documentos > Nóminas
- ✅ Envía email al empleado

Verás un mensaje en el chatter:
```
✅ Documento generado y correo enviado exitosamente.
```

#### 3️⃣ Verificar (opcional)
Ve a **Documentos > Nóminas** y encontrarás:
```
📄 Recibo_NOMINA_001.pdf
   Owner: Juan Pérez
   Fecha: 2025-10-16
```

---

### Para empleados:

#### 📧 Recibes email automático
```
De: Recursos Humanos
Asunto: Tu recibo de nómina [Octubre 2025]

Hola Juan,

Tu recibo de nómina está listo.
Puedes descargarlo desde el adjunto o verlo en el Portal de Empleado.

[Descargar PDF]
```

#### 🌐 O entras al portal
```
Portal Empleado > Mis Documentos > Nóminas
📄 Recibo_NOMINA_001.pdf
   Descargar | Ver
```

---

## 🔧 Acciones manuales (si las necesitas)

Desde el listado de nóminas, selecciona una o varias y usa:

### 📄 "Generar Documento"
- Solo genera/asegura que el PDF exista
- No envía email
- Útil si necesitas regenerar el PDF

### 📧 "Enviar Email"
- Solo envía el email
- Requiere que el documento ya exista
- Útil si el envío automático falló

### 📄+📧 "Generar y Enviar"
- Hace ambas cosas
- Es lo que se ejecuta automáticamente al confirmar

---

## 📍 Dónde encontrar los recibos

### Como RRHH o Admin:
```
Documentos > Carpetas > Nóminas
```
Verás TODOS los recibos organizados por empleado.

### Como Empleado:
```
Portal Empleado > Documentos
```
Solo verás TUS propios recibos (seguridad).

---

## ⚠️ Requisitos importantes

Para que funcione correctamente:

1. ✅ **Email del empleado configurado**
   - Ir a: Empleados > [Empleado] > Información Laboral
   - Campo: "Email de trabajo"
   - O: Empleados > [Empleado] > Información Privada > Email

2. ✅ **Servidor de email configurado**
   - Ajustes > Técnico > Email > Servidores de Correo Saliente
   - Debe haber uno configurado y funcionando

3. ✅ **App Documentos instalada**
   - Solo en Odoo Enterprise
   - Se instala automáticamente con este módulo

---

## 🔒 Seguridad y privacidad

- 👥 **Empleados**: Solo ven sus propios recibos
- 👔 **RRHH Users**: Ven todos los recibos (solo lectura)
- 👨‍💼 **RRHH Managers**: Control total

---

## 💡 Tips y trucos

### ✅ Buenas prácticas:
- Confirma nóminas cuando los datos estén correctos
- Verifica emails de empleados nuevos antes de confirmar su primera nómina
- Revisa la carpeta Nóminas periódicamente

### ⚠️ Si el email no llega:
1. Verifica que el empleado tenga email configurado
2. Revisa la bandeja de spam
3. Ve al chatter de la nómina y busca errores
4. Usa el botón "Enviar Email" manualmente

### 🔍 Si no se genera el PDF:
1. Verifica que la nómina esté en estado "Hecho"
2. Revisa los logs de Odoo (pide ayuda a TI)
3. Usa el botón "Generar Documento" manualmente

---

## 📞 Soporte

**¿Tienes problemas?**
1. Revisa esta guía primero
2. Contacta a tu departamento de TI
3. Ellos pueden revisar los logs técnicos

**Autor:** Natalie Aliaga  
**Web:** https://www.tierranube.cl  
**Versión:** 18.0

---

## 🎓 Preguntas frecuentes

### ¿Puedo desactivar el envío automático?
Sí, desmarca la automatización en:
`Ajustes > Técnico > Automatización > Buscar "nómina"`

### ¿Puedo reenviar un recibo?
Sí, selecciona la nómina y usa "Enviar Email"

### ¿Se puede personalizar el email?
Sí (requiere configuración técnica):
`Ajustes > Técnico > Email > Plantillas > Buscar "payslip"`

### ¿Los recibos se guardan para siempre?
Sí, quedan en la app Documentos hasta que los elimines manualmente

### ¿Puedo cambiar la carpeta donde se guardan?
Actualmente no (por defecto es "Nóminas")

---

**¡Listo! Ahora tu proceso de nómina es 100% automático** ✨

Confirma → Sistema genera → Empleado recibe → ✅ Hecho
