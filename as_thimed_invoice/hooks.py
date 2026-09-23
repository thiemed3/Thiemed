# -*- coding: utf-8 -*-
def pre_init_hook(env):
    """ Corrige valores nulos en campos requeridos antes de actualizar el modelo / base de datos """
    env.cr.execute("update stock_move_line set company_id = 1 where company_id is null;")
    env.cr.execute("update helpdesk_ticket set x_studio_accion_inmediata = '' where x_studio_accion_inmediata is null;")
    env.cr.execute("update helpdesk_ticket set x_studio_accion_inmediata_1 = '' where x_studio_accion_inmediata_1 is null;")
