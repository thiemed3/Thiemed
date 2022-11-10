# -*- coding: utf-8 -*-
"""
    This model is used to create a boolean social sharing options.
"""
import base64
from odoo import fields, models, tools, api, _
from odoo.modules.module import get_resource_path
from odoo.addons.website.tools import get_video_embed_code

class res_config(models.TransientModel):
    _inherit = "res.config.settings"

    facebook_sharing = fields.Boolean(string='Facebook', related='website_id.facebook_sharing',readonly=False)
    twitter_sharing = fields.Boolean(string='Twitter', related='website_id.twitter_sharing',readonly=False)
    linkedin_sharing = fields.Boolean(string='Linkedin', related='website_id.linkedin_sharing',readonly=False)
    mail_sharing = fields.Boolean(string='Mail', related='website_id.mail_sharing',readonly=False)
    is_load_more = fields.Boolean(string='Load More', related='website_id.is_load_more', readonly=False,
                                 help="Load next page products with Ajax")
    load_more_image = fields.Binary(string='Load More Image', related='website_id.load_more_image', readonly=False,
                               help="Display this image while load more applies.")
    button_or_scroll = fields.Selection(related='website_id.button_or_scroll',
        required=True,readonly=False,help="Define how to show the pagination of products in a shop page with on scroll or button.")
    prev_button_label = fields.Char(string='Label for the Prev Button', related='website_id.prev_button_label', readonly=False, translate=True)
    next_button_label = fields.Char(string='Label for the Next Button', related='website_id.next_button_label', readonly=False, translate=True)
    is_lazy_load = fields.Boolean(string='Lazyload', related='website_id.is_lazy_load', readonly=False,
                                 help="Lazy load will be enabled.")
    lazy_load_image = fields.Binary(string='Lazyload Image', related='website_id.lazy_load_image', readonly=False,
                                   help="Display this image while lazy load applies.")
    banner_video_url = fields.Many2one('ir.attachment', "Video URL", related='website_id.banner_video_url', help='URL of a video for banner.', readonly=False)
    number_of_product_line = fields.Selection(related='website_id.number_of_product_line',string="Number of lines for product name",
         readonly=False, help="Number of lines to show in product name for shop.")
    is_auto_play = fields.Boolean(string='Slider Auto Play', related='website_id.is_auto_play', default=True, readonly=False)

    is_pwa = fields.Boolean(string='PWA', related='website_id.is_pwa', readonly=False, help="Pwa will be enabled.")
    pwa_name = fields.Char(string='Name', related='website_id.pwa_name', readonly=False)
    pwa_short_name = fields.Char(string='Short Name', related='website_id.pwa_short_name', readonly=False)
    pwa_theme_color = fields.Char(string='Theme Color', related='website_id.pwa_theme_color', readonly=False)
    pwa_bg_color = fields.Char(string='Background Color', related='website_id.pwa_bg_color', readonly=False)
    pwa_start_url = fields.Char(string='Start URL', related='website_id.pwa_start_url', readonly=False)
    app_image_512 = fields.Binary(string='Application Image(512x512)', related='website_id.app_image_512',
                                  readonly=False)

    is_price_range_filter = fields.Boolean(string='Price Range Filter', related='website_id.is_price_range_filter', readonly=False, help="Enable the price range filter")
    price_filter_on = fields.Selection(related='website_id.price_filter_on',
                                         readonly=False)
    is_advanced_search = fields.Boolean(string='Enable Advanced Search', related='website_id.is_advanced_search', readonly=False, help="Enable the advance search")
    allowed_search_category = fields.Boolean(string='Allow Search In Category',related='website_id.allowed_search_category', readonly=False)
    allowed_search_blog = fields.Boolean(string='Enable Advance Blog',related='website_id.allowed_search_blog', readonly=False)
    allowed_search_brand = fields.Boolean(string='Enable Brand Search', related='website_id.allowed_search_brand',help='Enable the brand search in website shop',
                                         readonly=False)

    @api.onchange('is_load_more')
    def get_value_icon_load_more(self):
        if self.is_load_more == False:
            img_path = get_resource_path('emipro_theme_base', 'static/src/img/Loadmore.gif')
            with tools.file_open(img_path, 'rb') as f:
                self.load_more_image = base64.b64encode(f.read())

    @api.onchange('is_lazy_load')
    def get_value_icon_lazy_load(self):
        if self.is_lazy_load == False:
            img_path = get_resource_path('emipro_theme_base', 'static/src/img/Lazyload.gif')
            with tools.file_open(img_path, 'rb') as f:
                self.lazy_load_image = base64.b64encode(f.read())
