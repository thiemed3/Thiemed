
from odoo import api, fields, models, tools, _
from odoo.tools.translate import html_translate


class ProductTabLine(models.Model):
    _name = "product.tab.line"
    _description = 'Product Tab Line'
    _order = "sequence, id"

    def _get_default_icon_content(self):
        return """
            <span class="fa fa-info-circle mr-2"/>
            """

    product_id = fields.Many2one('product.template', string='Product Template')
    tab_name = fields.Char("Tab Name", required=True, translate=True)
    tab_content = fields.Html("Tab Content", sanitize_attributes=False, translate=html_translate, sanitize_form=False)
    icon_content = fields.Html("Icon Content", translate=html_translate, default=_get_default_icon_content)
    website_ids = fields.Many2many('website', help="You can set the description in particular website.")
    sequence = fields.Integer('Sequence', default=1, help="Gives the sequence order when displaying.")

    def checkTab(self, currentWebsite, tabWebsiteArray):
        if currentWebsite in tabWebsiteArray or len(tabWebsiteArray) == 0:
            return True
        else:
            return False
