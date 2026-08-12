from lxml import etree

from odoo.exceptions import RedirectWarning, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMedicalLinks(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env['res.partner']
        cls.Link = cls.env['res.partner.medical.link']
        cls.Influence = cls.env['res.partner.medical.influence']

        cls.doctor = cls.Partner.create({
            'name': 'Doctor Test Unitario',
            'company_type': 'person',
            'is_doctor': True,
            'phone': '+56911111111',
            'email': 'doctor.test@example.com',
            'city': 'Santiago',
        })
        cls.institution = cls.Partner.create({
            'name': 'Clinica Test Unitario',
            'is_company': True,
            'is_institution': True,
        })
        cls.influence = cls.Influence.create({
            'name': 'Influencia Test Unitario',
            'color': 3,
        })

    def _create_link(self):
        return self.Link.create({
            'doctor_id': self.doctor.id,
            'institution_id': self.institution.id,
            'job_position': 'Traumatologia',
            'influence_level': '3',
            'influence_ids': [(6, 0, self.influence.ids)],
            'institutional_email': 'doctor@clinica.example.com',
        })

    def test_create_medical_link(self):
        link = self._create_link()

        self.assertEqual(link.doctor_id, self.doctor)
        self.assertEqual(link.institution_id, self.institution)
        self.assertEqual(link.doctor_phone, self.doctor.phone)
        self.assertEqual(link.doctor_email, self.doctor.email)
        self.assertIn(self.influence, link.influence_ids)
        self.assertIn(self.institution, self.doctor.institution_ids)

    def test_invalid_partner_roles_are_rejected(self):
        company = self.Partner.create({'name': 'Empresa No Medico', 'is_company': True})
        person = self.Partner.create({'name': 'Persona No Institucion', 'is_company': False})

        with self.assertRaises(ValidationError):
            company.write({'is_doctor': True})

        with self.assertRaises(ValidationError):
            person.write({'is_institution': True})

        with self.assertRaises(ValidationError):
            self.doctor.write({'is_institution': True})

    def test_invalid_medical_link_partners_are_rejected(self):
        not_doctor = self.Partner.create({'name': 'Contacto Sin Rol', 'is_company': False})
        not_institution = self.Partner.create({'name': 'Empresa Sin Rol', 'is_company': True})

        with self.assertRaises(ValidationError):
            self.Link.create({
                'doctor_id': not_doctor.id,
                'institution_id': self.institution.id,
            })

        with self.assertRaises(ValidationError):
            self.Link.create({
                'doctor_id': self.doctor.id,
                'institution_id': not_institution.id,
            })

    def test_search_doctors_by_institution(self):
        self._create_link()

        doctors = self.Partner.search([('institution_ids', 'ilike', 'Clinica Test Unitario')])

        self.assertIn(self.doctor, doctors)

    def test_deactivate_role_redirects_when_links_exist(self):
        self._create_link()

        with self.assertRaises(RedirectWarning):
            self.doctor.write({'is_doctor': False})

    def test_wizard_cleans_links_and_deactivates_role(self):
        link = self._create_link()
        wizard = self.env['partner.role.deactivate.wizard'].create({
            'partner_id': self.doctor.id,
            'role': 'doctor',
        })

        result = wizard.action_clean_and_deactivate()

        self.assertEqual(result['type'], 'ir.actions.act_window_close')
        self.assertFalse(link.exists())
        self.assertFalse(self.doctor.is_doctor)


@tagged('post_install', '-at_install')
class TestMedicalLinksUI(TransactionCase):

    def test_loaded_views_are_valid(self):
        views = self.env['ir.ui.view'].browse([
            self.env.ref('ints_medics_module.view_res_partner_medical_influence_list').id,
            self.env.ref('ints_medics_module.view_res_partner_medical_link_list').id,
            self.env.ref('ints_medics_module.view_res_partner_medical_link_form').id,
            self.env.ref('ints_medics_module.view_partner_form_inherit_medical_links').id,
            self.env.ref('ints_medics_module.view_partner_role_deactivate_wizard_form').id,
            self.env.ref('ints_medics_module.view_res_partner_filter_inherit_medical_links').id,
        ])

        for view in views:
            view._check_xml()

    def test_partner_form_contains_medical_roles_and_tabs(self):
        view = self.env.ref('base.view_partner_form')

        combined_arch = etree.tostring(view._get_combined_arch(), encoding='unicode')

        self.assertIn('is_doctor', combined_arch)
        self.assertIn('is_institution', combined_arch)
        self.assertIn('Es médico', combined_arch)
        self.assertIn('Es institución', combined_arch)
        self.assertIn('institution_link_ids', combined_arch)
        self.assertIn('doctor_link_ids', combined_arch)

    def test_search_view_contains_institution_filter(self):
        view = self.env.ref('base.view_res_partner_filter')

        combined_arch = etree.tostring(view._get_combined_arch(), encoding='unicode')

        self.assertIn('institution_ids', combined_arch)

    def test_menu_and_actions_are_available(self):
        menu = self.env.ref('ints_medics_module.menu_medical_links_root')
        influence_action = self.env.ref('ints_medics_module.action_res_partner_medical_influence')
        wizard_action = self.env.ref('ints_medics_module.action_partner_role_deactivate_wizard')

        self.assertEqual(menu.parent_id, self.env.ref('contacts.res_partner_menu_config'))
        self.assertEqual(influence_action.res_model, 'res.partner.medical.influence')
        self.assertEqual(wizard_action.res_model, 'partner.role.deactivate.wizard')
        self.assertEqual(wizard_action.target, 'new')
