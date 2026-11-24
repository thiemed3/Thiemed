from unittest.mock import patch

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


DATE = '2099-01-15'
CLP_PER_UNIT = {
    'UF': 40000.0,
    'USD': 1000.0,
    'EUR': 1100.0,
}


@tagged('post_install', '-at_install')
class TestStockPickingMulticurrency(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.currency_clp = cls.company.currency_id
        cls.tax = cls.env['account.tax'].search([
            ('company_id', '=', cls.company.id),
            ('type_tax_use', '=', 'sale'),
            ('amount', '=', 19.0),
        ], limit=1)
        cls.assertTrue(cls.tax, 'Se requiere el impuesto IVA 19% de venta para esta prueba')
        cls.country_cl = cls.env.ref('base.cl')

    def _currency(self, name):
        if name == 'CLP':
            return self.currency_clp
        currency = self.env['res.currency'].search([('name', '=', name)], limit=1)
        self.assertTrue(currency, 'No existe la moneda %s' % name)
        return currency

    def _set_rate(self, currency, clp_per_unit):
        self.env['res.currency.rate'].create({
            'currency_id': currency.id,
            'name': DATE,
            'rate': 1.0 / clp_per_unit,
            'company_id': (self.company.root_id or self.company).id,
        })
        return clp_per_unit

    def _new_currency(self):
        return self.env['res.currency'].create({
            'name': 'ZZZ',
            'full_name': 'Moneda sin tasa',
            'symbol': 'Z',
            'decimal_places': 2,
            'rounding': 0.01,
        })

    def _create_picking(self, currency, price, qty=2.0, discount=0.0, reason='1', guide_price='sale_order'):
        pricelist = self.env['product.pricelist'].create({
            'name': 'Lista prueba %s' % currency.name,
            'currency_id': currency.id,
            'company_id': self.company.id,
        })
        partner = self.env['res.partner'].create({
            'name': 'Cliente prueba %s' % currency.name,
            'country_id': self.country_cl.id,
            'l10n_cl_delivery_guide_price': guide_price,
            'property_product_pricelist': pricelist.id,
        })
        product = self.env['product.product'].create({
            'name': 'Producto prueba %s' % currency.name,
            'is_storable': True,
            'list_price': 0.0,
            'taxes_id': [Command.set(self.tax.ids)],
        })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'pricelist_id': pricelist.id,
            'company_id': self.company.id,
            'order_line': [Command.create({
                'product_id': product.id,
                'product_uom_qty': qty,
                'price_unit': price,
                'discount': discount,
                'tax_ids': [Command.set(self.tax.ids)],
            })],
        })
        with patch.object(type(self.env['base.automation']), '_process', return_value=True):
            order.with_context(send_email=False).action_confirm()
        picking = order.picking_ids[:1]
        picking.write({'l10n_cl_delivery_guide_reason': reason})
        picking.action_assign()
        move = picking.move_ids[:1]
        move.quantity = qty
        picking.write({'l10n_cl_dte_rate_date': DATE})
        return picking, move

    def _assert_amounts(self, totals, line, unit, excluded, vat, included):
        self.assertAlmostEqual(line['price_unit'], unit, places=2)
        self.assertAlmostEqual(line['total_amount'], excluded, places=2)
        self.assertAlmostEqual(totals['vat_amount'], vat, places=2)
        self.assertAlmostEqual(totals['total_amount'], included, places=2)

    def test_clp_regression_uses_sale_order_price(self):
        picking, move = self._create_picking(self.currency_clp, 100.0)
        totals, _retentions, lines = picking._l10n_cl_get_tax_amounts()
        self._assert_amounts(totals, lines[move], 100.0, 200.0, 38.0, 238.0)
        self.assertEqual(
            picking._l10n_cl_get_conversion_rate(
                self.currency_clp, self.currency_clp, self.company, DATE,
            ),
            1.0,
        )

    def test_uf_conversion_and_shared_values_for_xml_and_pdf(self):
        currency = self._currency('UF')
        rate = self._set_rate(currency, CLP_PER_UNIT['UF'])
        picking, move = self._create_picking(currency, 0.5)
        picking.write({'l10n_cl_dte_rate': rate})

        totals, _retentions, lines = picking._l10n_cl_get_tax_amounts()
        pdf = picking._prepare_pdf_values()
        self._assert_amounts(totals, lines[move], 20000.0, 40000.0, 7600.0, 47600.0)
        self.assertEqual(pdf['amounts'], totals)
        self.assertEqual(pdf['total_line_amounts'], lines)
        self.assertTrue(pdf['has_unit_price'])
        self.assertEqual(picking.l10n_cl_delivery_guide_reason, '1')
        self.assertNotEqual(lines[move]['total_amount'], 0.0)

    def test_usd_conversion_preserves_discount(self):
        currency = self._currency('USD')
        rate = self._set_rate(currency, CLP_PER_UNIT['USD'])
        picking, move = self._create_picking(currency, 10.0, discount=10.0)
        picking.write({'l10n_cl_dte_rate': rate})

        totals, _retentions, lines = picking._l10n_cl_get_tax_amounts()
        self._assert_amounts(totals, lines[move], 10000.0, 18000.0, 3420.0, 21420.0)
        self.assertAlmostEqual(lines[move]['price_unit_disc'], 9000.0, places=2)
        self.assertEqual(lines[move]['total_discount'], '2000')

    def test_eur_conversion(self):
        currency = self._currency('EUR')
        rate = self._set_rate(currency, CLP_PER_UNIT['EUR'])
        picking, move = self._create_picking(currency, 10.0)
        picking.write({'l10n_cl_dte_rate': rate})

        totals, _retentions, lines = picking._l10n_cl_get_tax_amounts()
        self._assert_amounts(totals, lines[move], 11000.0, 22000.0, 4180.0, 26180.0)

    def test_missing_rate_raises_user_error(self):
        currency = self._new_currency()
        picking, _move = self._create_picking(currency, 10.0)
        with self.assertRaises(UserError) as error:
            picking._l10n_cl_get_tax_amounts()
        self.assertIn('No hay tasa de cambio válida', str(error.exception))

    def test_free_delivery_reason_is_not_modified(self):
        currency = self._currency('UF')
        rate = self._set_rate(currency, CLP_PER_UNIT['UF'])
        picking, move = self._create_picking(currency, 0.0, reason='4')
        picking.write({'l10n_cl_dte_rate': rate})

        self.assertEqual(picking.l10n_cl_delivery_guide_reason, '4')
        totals, _retentions, lines = picking._l10n_cl_get_tax_amounts()
        self.assertEqual(totals['total_amount'], 0.0)
        self.assertEqual(lines[move]['total_amount'], 0.0)

    def test_none_price_keeps_zero_amounts_and_translation_reason(self):
        currency = self._currency('UF')
        self._set_rate(currency, CLP_PER_UNIT['UF'])
        picking, _move = self._create_picking(currency, 10.0, reason='1', guide_price='none')

        with patch.object(type(picking), '_l10n_cl_get_conversion_rate', side_effect=AssertionError('No debe convertir con none')):
            totals, retentions, lines = picking._l10n_cl_get_tax_amounts()
        pdf = picking._prepare_pdf_values()

        self.assertEqual(totals, {
            'vat_amount': 0.0,
            'subtotal_amount_taxable': 0.0,
            'subtotal_amount_exempt': 0.0,
            'vat_percent': False,
            'total_amount': 0.0,
        })
        self.assertEqual(retentions, {})
        self.assertEqual(lines, {})
        self.assertFalse(pdf['has_unit_price'])
        self.assertFalse(pdf['has_discount'])
        self.assertEqual(pdf['amount_total'], 0.0)
        self.assertEqual(picking.l10n_cl_delivery_guide_reason, '1')

    def test_tax_compute_all_uses_supported_rounding_method(self):
        currency = self._currency('UF')
        rate = self._set_rate(currency, CLP_PER_UNIT['UF'])
        picking, _move = self._create_picking(currency, 0.5)
        picking.write({'l10n_cl_dte_rate': rate})
        tax_class = type(self.tax)
        original_compute_all = tax_class.compute_all
        original_method = self.company.tax_calculation_rounding_method
        self.addCleanup(lambda: setattr(self.company, 'tax_calculation_rounding_method', original_method))

        for method in ('round_globally', 'round_per_line'):
            self.company.tax_calculation_rounding_method = method
            calls = []

            def spy(recordset, *args, **kwargs):
                calls.append(kwargs)
                return original_compute_all(recordset, *args, **kwargs)

            with patch.object(tax_class, 'compute_all', spy):
                totals, _retentions, _lines = picking._l10n_cl_get_tax_amounts()
            self.assertTrue(calls)
            self.assertTrue(all('round' not in kwargs for kwargs in calls))
            self.assertTrue(all(kwargs.get('rounding_method') == method for kwargs in calls))
            self.assertAlmostEqual(totals['total_amount'], 47600.0, places=2)
