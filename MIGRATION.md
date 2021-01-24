# v21
# Desinstalados y/o forzados
auth_session_timeout
webservices_generic
automatic_backup
unique_sku

# Dependencias obligatorias forzadas
date_range
account_financial_amount
account_partner_reconcile
l10n_cl_chart_of_account - NO EXISTE MODELO ACCOUNT.INVOICE en odoo 14
whin_process_thiemed - NO EXISTE MODELO ACCOUNT.INVOICE en odoo 14
l10n_cl_fe

# Disponibles para Odoo 14
mass_editing

# segment fault
initial_charges



# Dependencias
pip3 install pdfminer.six
pip3 install xmltodict
pip3 install dicttoxml
pip3 install pdf417gen
pip3 install cchardet 
pip3 install urllib3  
pip3 install signxml  
pip3 install pysftp   
pip3 install num2words
pip3 install xlsxwrite
pip3 install numpy    
pip3 install unidecode
pip3 install lxml     
pip3 install fdfgen   
pip3 install xlrd     
pip3 install fdfgen   
pip3 install acme_tiny
pip3 install IPy      
pip3 install wheel    
pip3 install raven    
pip3 install pyOpenSSL
pip3 install openupgradelib   
pip3 install xmltodict
pip3 install dicttoxml
pip3 install pdf417gen
pip3 install cchardet
pip3 install suds-jurko
pip3 install signxml


# No encontrados
studio_customization
digest_enterprise
account_financial_report_date_range
currency_rate_inverted
ms_query

# NO CARGADOS
'account_clean_cancelled_invoice_number',
'account_financial_report',
'account_financial_report_date_range',
'account_payment_group',
'account_payment_group_massive_unlink',
'bi_invoice_sale_order',
'currency_rate_inverted',
'digest_enterprise',
'initial_charges',
'l10n_cl_book_fix',
'l10n_cl_books',
'l10n_cl_fe',
'l10n_cl_financial_indicators',
'l10n_cl_report',
'l10n_cl_report_stock',
'l10n_cl_sale_order_references',
'l10n_cl_stock_picking',
'ms_query',
'stock_landed_costs_tags'


grep -rl '@api.one' /opt/git/ThiemedMigradoOdoo14 | xargs sed -i 's/@api.one/# @api.one/g'
grep -rl '@api.multi' /opt/git/ThiemedMigradoOdoo14 | xargs sed -i 's/@api.multi/# @api.multi/g'
