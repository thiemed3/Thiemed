"""Read-only layout checks, reusable without creating payroll fixtures."""

from lxml import etree


PREFIX = 'thiemed_payroll_report_compatibility.'
REPLACEMENTS = {'📞': 'Tel.: ', '📧': 'Correo: ', '🌐': 'Web: ', '🏬': 'RUT: '}


def validate_footer_layouts(env):
    for suffix, original in (
        ('external_layout_payroll', 'web.external_layout'),
        ('external_layout_striped_payroll', 'web.external_layout_striped'),
        ('external_layout_standard_payroll', 'web.external_layout_standard'),
    ):
        derived = env.ref(PREFIX + suffix)
        base = env.ref(original)
        assert derived.mode == 'primary' and derived.inherit_id == base
        assert PREFIX not in etree.tostring(base._get_combined_arch(), encoding='unicode')

    for original in (
        'l10n_cl_hr.report_payslipgeneral',
        'l10n_cl_hr_payroll_reports.report_certificado_antiguedad_document',
    ):
        arch = env.ref(original)._get_combined_arch()
        assert len(arch.xpath("//t[@t-call='" + PREFIX + "external_layout_payroll']")) == 1

    companies = env['res.company'].search([]).with_context(lang='es_CL')
    company = companies.filtered(lambda record: record.report_footer)[:1]
    if not company:
        return {'scoped': True, 'render_checks': 'no existing company footer'}
    footer = str(company.report_footer or '')
    if not footer:
        return {'scoped': True, 'render_checks': 'no existing company footer'}
    expected = footer
    for symbol, label in REPLACEMENTS.items():
        expected = expected.replace(symbol, label)
    text = lambda source: ' '.join(''.join(etree.HTML(source).itertext()).split())
    expected_text = text(expected)
    qweb = env['ir.qweb'].with_context(lang='es_CL', inherit_branding=False)
    values = {
        'company': company, 'res_company': company, 'o': False, 'doc': False,
        'report_type': 'pdf', 'forced_vat': False, 'display_name_in_footer': False,
        'layout_document_title': False, 'address': False, 'information_block': False,
    }
    results = []
    for suffix, original in (
        ('external_layout_striped_payroll', 'web.external_layout_striped'),
        ('external_layout_standard_payroll', 'web.external_layout_standard'),
    ):
        private = etree.HTML(str(qweb._render(PREFIX + suffix, dict(values))))
        nodes = private.xpath("//*[@name='thiemed_payroll_footer']")
        assert len(nodes) == 1
        rendered = ' '.join(''.join(nodes[0].itertext()).split())
        assert rendered == expected_text
        assert not any(symbol in rendered for symbol in REPLACEMENTS)
        native = str(qweb._render(original, dict(values)))
        for symbol in REPLACEMENTS:
            if symbol in footer:
                assert symbol in native
        results.append(suffix)
    assert str(company.report_footer or '') == footer
    return {'scoped': True, 'private_layouts_rendered': results, 'global_footer_unchanged': True}
