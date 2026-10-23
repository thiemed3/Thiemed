# -*- coding: utf-8 -*-
def migrate(cr, version):
    """ Script de migración ejecutado automáticamente al actualizar la versión del módulo """
    cr.execute("update stock_move_line set company_id = 1 where company_id is null;")
    cr.execute("update helpdesk_ticket set x_studio_accion_inmediata = '' where x_studio_accion_inmediata is null;")
    cr.execute("update helpdesk_ticket set x_studio_accion_inmediata_1 = '' where x_studio_accion_inmediata_1 is null;")
