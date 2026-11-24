from lxml import etree

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_repr


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    l10n_cl_dte_rate_date = fields.Date(
        string="Fecha tipo de cambio DTE", copy=False, readonly=True,
    )
    l10n_cl_dte_rate = fields.Float(
        string="Tipo de cambio DTE", digits=(16, 6), copy=False, readonly=True,
    )

    def _l10n_cl_create_dte(self):
        for picking in self:
            company = picking.company_id
            company_currency = company.currency_id
            source_currency = picking.sale_id.currency_id or company_currency
            date = picking._l10n_cl_dte_conversion_date()
            rate = picking._l10n_cl_get_conversion_rate(
                source_currency, company_currency, company, date,
            )
            picking.write({
                'l10n_cl_dte_rate_date': date,
                'l10n_cl_dte_rate': rate,
            })
        return super()._l10n_cl_create_dte()

    def _l10n_cl_dte_conversion_date(self):
        self.ensure_one()
        return (
            self.l10n_cl_dte_rate_date
            or self._l10n_cl_dte_date_from_attachment()
            or self._get_cl_current_datetime().date()
        )

    def _l10n_cl_dte_date_from_attachment(self):
        attachment = self.l10n_cl_dte_file
        if not attachment:
            return False
        try:
            root = etree.fromstring(attachment.raw)
            node = root.find('.//{*}FchEmis')
            return fields.Date.to_date(node.text) if node is not None and node.text else False
        except Exception:
            return False

    def _l10n_cl_find_rate_record(self, currency, company, date):
        root_company = company.root_id or company
        Rate = self.env['res.currency.rate'].sudo()
        domain = [
            ('currency_id', '=', currency.id),
            '|',
            ('company_id', '=', False),
            ('company_id', '=', root_company.id),
            ('name', '<=', date),
        ]
        return Rate.search(domain, order='name DESC, id DESC', limit=1)

    def _l10n_cl_get_conversion_rate(self, from_currency, to_currency, company, date):
        if from_currency == to_currency:
            return 1.0
        for currency in (from_currency, to_currency):
            if currency == (company.root_id or company).currency_id:
                continue
            rate_record = self._l10n_cl_find_rate_record(currency, company, date)
            if not rate_record or rate_record.rate <= 0:
                raise UserError(_(
                    "No hay tasa de cambio válida para %(currency)s con fecha %(date)s. "
                    "Registre una tasa antes de generar la guía de despacho."
                ) % {
                    'currency': currency.name,
                    'date': date,
                })
        return self.env['res.currency']._get_conversion_rate(
            from_currency, to_currency, company, date,
        )

    def _l10n_cl_convert_amount(self, amount, from_currency, to_currency, company, date, rate=None):
        if not amount or from_currency == to_currency:
            return amount
        rate = rate if rate is not None else self._l10n_cl_get_conversion_rate(
            from_currency, to_currency, company, date,
        )
        return amount * rate

    def _l10n_cl_get_tax_amounts(self):
        """
        Respeta company.tax_calculation_rounding_method:
        - round_per_line: redondea cada línea y suma.
        - round_globally: acumula sin redondear y redondea al final (evita el -/+ $1).
        Mantiene price_unit (sin desc) y price_unit_disc (con desc) para el PDF.
        """
        company = self.company_id
        currency = company.currency_id
        partner = self.partner_id
        rounding_method = company.tax_calculation_rounding_method
        round_per_line = (rounding_method == 'round_per_line')
        conversion_date = self._l10n_cl_dte_conversion_date()
        source_currency = self.sale_id.currency_id or currency
        stored_rate = (
            self.l10n_cl_dte_rate
            if self.l10n_cl_dte_rate_date == conversion_date and self.l10n_cl_dte_rate
            else None
        )

        totals = {
            'vat_amount': 0.0,
            'subtotal_amount_taxable': 0.0,
            'subtotal_amount_exempt': 0.0,
            'vat_percent': False,
            'total_amount': 0.0,
        }
        retentions = {}
        line_amounts = {}

        taxable_raw = 0.0
        exempt_raw = 0.0
        vat_raw = 0.0
        total_incl_raw = 0.0

        guide_price = partner.l10n_cl_delivery_guide_price
        if guide_price == 'none':
            return totals, retentions, line_amounts
        if guide_price == 'sale_order' and not self.sale_id:
            guide_price = 'product'

        tax_group_ila = self.env['account.chart.template'].with_company(company).ref('tax_group_ila', raise_if_not_found=False)
        tax_group_ret = self.env['account.chart.template'].with_company(company).ref('tax_group_retenciones', raise_if_not_found=False)
        TAX19_SII_CODE = 14
        max_vat_perc = 0.0

        for move in self.move_ids.filtered(lambda m: m.quantity > 0):
            product = move.product_id
            if not product:
                continue

            qty, uom = self._qty_in_move_uom(move)
            qty = qty or 0.0

            sol = move.sale_line_id or (self.sale_id.order_line.filtered(lambda l: l.product_id == product)[:1] if self.sale_id else False)
            is_kit_component = bool(getattr(move, 'bom_line_id', False))

            if is_kit_component:
                if self.sale_id and self.sale_id.pricelist_id:
                    price_doc, price_currency = self._safe_pricelist_price(
                        pricelist=self.sale_id.pricelist_id,
                        product=product, qty=qty or 1.0, partner=partner, uom=uom,
                        date=(self.date_done or self.scheduled_date or fields.Date.context_today(self)),
                    )
                else:
                    price_doc = product.uom_id._compute_price(product.lst_price, uom)
                    price_currency = getattr(product, 'currency_id', None) or currency
                price_unit = self._l10n_cl_convert_amount(
                    price_doc, price_currency, currency, company, conversion_date,
                    stored_rate if price_currency == source_currency else None,
                )
                discount = float(sol.discount or 0.0) if sol else 0.0
                taxes = (sol.tax_ids if sol else product.taxes_id).filtered(lambda t: t.company_id == company)
            else:
                if guide_price == 'sale_order' and sol:
                    price_doc = sol.product_uom_id._compute_price(sol.price_unit, uom)
                    price_currency = sol.currency_id or source_currency
                else:
                    price_doc = product.uom_id._compute_price(product.lst_price, uom)
                    price_currency = getattr(product, 'currency_id', None) or currency
                price_unit = self._l10n_cl_convert_amount(
                    price_doc, price_currency, currency, company, conversion_date,
                    stored_rate if price_currency == source_currency else None,
                )
                discount = float(sol.discount or 0.0) if guide_price == 'sale_order' and sol else 0.0
                taxes = sol.tax_ids if guide_price == 'sale_order' and sol else product.taxes_id.filtered(lambda t: t.company_id == company)

            price_after_disc = price_unit * (1 - (discount or 0.0) / 100.0)

            tax_res = taxes.compute_all(
                price_after_disc, currency=currency, quantity=qty,
                partner=partner, rounding_method=rounding_method,
            ) if taxes else None

            if not tax_res:
                base = price_after_disc * qty
                tax_res = {'total_excluded': base, 'total_included': base, 'taxes': []}

            line_excl_raw = tax_res['total_excluded']
            line_incl_raw = tax_res['total_included']

            vat_line_raw = 0.0
            no_vat_taxes = True
            for tx in tax_res.get('taxes', []):
                tax = self.env['account.tax'].browse(tx['id'])
                amt = tx['amount']
                if tax.l10n_cl_sii_code == TAX19_SII_CODE:
                    no_vat_taxes = False
                    vat_line_raw += amt
                    max_vat_perc = max(max_vat_perc, tax.amount)
                elif tax.tax_group_id and (
                    (tax_group_ila and tax.tax_group_id.id == tax_group_ila.id) or
                    (tax_group_ret and tax.tax_group_id.id == tax_group_ret.id)
                ):
                    key = (tax.l10n_cl_sii_code, tax.amount, tax.tax_group_id.name)
                    retentions[key] = retentions.get(key, 0.0) + amt

            if round_per_line:
                line_excl = currency.round(line_excl_raw)
                line_incl = currency.round(line_incl_raw)
                totals['total_amount'] += line_incl
                totals['vat_amount'] += currency.round(vat_line_raw)
                if no_vat_taxes:
                    totals['subtotal_amount_exempt'] += line_excl
                else:
                    totals['subtotal_amount_taxable'] += line_excl
            else:
                total_incl_raw += line_incl_raw
                vat_raw += vat_line_raw
                if no_vat_taxes:
                    exempt_raw += line_excl_raw
                else:
                    taxable_raw += line_excl_raw

            undisc_unit_excl = price_unit
            disc_unit_excl = (line_excl_raw / qty) if qty else price_after_disc
            line_amounts[move] = {
                "value": currency.round(line_incl_raw),
                "total_amount": currency.round(line_excl_raw),
                "price_unit": currency.round(undisc_unit_excl),
                "price_unit_disc": currency.round(disc_unit_excl),
                "exempt": no_vat_taxes and (line_excl_raw != 0.0),
            }
            if discount:
                if taxes:
                    undisc_res = taxes.compute_all(
                        price_unit, currency=currency, quantity=qty,
                        partner=partner, rounding_method=rounding_method,
                    )
                    base_undisc_raw = undisc_res['total_excluded']
                else:
                    base_undisc_raw = price_unit * qty
                disc_amount = base_undisc_raw * discount / 100.0
                line_amounts[move].update({
                    'discount': discount,
                    'total_discount': float_repr(currency.round(disc_amount), 0),
                    'total_discount_fl': currency.round(disc_amount),
                })

        if round_per_line:
            totals['subtotal_amount_taxable'] = currency.round(totals['subtotal_amount_taxable'])
            totals['subtotal_amount_exempt'] = currency.round(totals['subtotal_amount_exempt'])
            totals['vat_amount'] = currency.round(totals['vat_amount'])
            totals['total_amount'] = currency.round(
                totals['subtotal_amount_taxable'] + totals['subtotal_amount_exempt'] + totals['vat_amount']
            )
        else:
            totals['subtotal_amount_taxable'] = currency.round(taxable_raw)
            totals['subtotal_amount_exempt'] = currency.round(exempt_raw)
            totals['vat_amount'] = currency.round(vat_raw)
            totals['total_amount'] = currency.round(totals['subtotal_amount_taxable'] +
                                                    totals['subtotal_amount_exempt'] +
                                                    totals['vat_amount'])

        totals['vat_percent'] = max_vat_perc and float_repr(max_vat_perc, 2) or False

        retention_res = [{
            'tax_code': code,
            'tax_percent': percent,
            'tax_name': name,
            'tax_amount': currency.round(amount),
        } for (code, percent, name), amount in retentions.items()]

        return totals, retention_res, line_amounts

    # -------------------------- Helpers usados arriba --------------------------
    def _safe_pricelist_price(self, pricelist, product, qty, partner, uom=None, date=None):
        date = fields.Date.to_date(date) or fields.Date.context_today(self)
        uom = uom or product.uom_id
        try:
            return pricelist._get_product_price(product, qty, partner, uom=uom, date=date), pricelist.currency_id
        except Exception:
            product_currency = getattr(product, 'currency_id', None) or self.company_id.currency_id
            price = self._l10n_cl_convert_amount(
                product.lst_price, product_currency, pricelist.currency_id,
                self.company_id, date,
            )
            return price, pricelist.currency_id

    def _qty_in_move_uom(self, move):
        move_uom = move.product_uom
        if move.state == 'done':
            qty = 0.0
            for ml in move.move_line_ids:
                if not ml.qty_done:
                    continue
                qty += ml.product_uom_id._compute_quantity(ml.qty_done, move_uom, rounding_method='HALF-UP')
            return qty or 0.0, move_uom
        return (move.product_uom_qty or 0.0), move_uom

    # ------------------ PDF: reutiliza exactamente los mismos montos ------------------
    def _prepare_pdf_values(self):
        res = super()._prepare_pdf_values()
        amounts = res['amounts']
        total_line_amounts = res['total_line_amounts']
        res.update({
            'has_unit_price': any(l.get('price_unit', 0.0) != 0.0 for l in total_line_amounts.values()),
            'has_discount': any(l.get('total_discount', '0') != '0' for l in total_line_amounts.values()),
            'amount_untaxed': amounts['subtotal_amount_taxable'] + amounts['subtotal_amount_exempt'],
            'amount_tax': amounts['vat_amount'],
            'amount_total': amounts['total_amount'],
        })
        return res
