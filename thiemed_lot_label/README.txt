CAMBIO NECESARIO EN LA VISTA QWEB EXISTENTE

Después de:
<t t-foreach="docs" t-as="lot">

agregar:
<t t-foreach="copies" t-as="copy">

Y cerrar ese nuevo bucle antes de cerrar el bucle de docs.

Ejemplo:
<t t-name="thiemed.label_lot_70x30_zpl">
  <t t-foreach="docs" t-as="lot">
    <t t-foreach="copies" t-as="copy">
      <t t-translation="off">
^XA
...
^XZ
      </t>
    </t>
  </t>
</t>

El wizard aparece en el menú Acción del lote y permite indicar la cantidad de etiquetas por lote.
