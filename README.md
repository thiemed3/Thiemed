# Desinstalados y/o forzados
auth_session_timeout
webservices_generic
date_range
automatic_backup
unique_sku

# Dependencias obligatorias forzadas
account_financial_amount
account_partner_reconcile

# Disponibles para Odoo 14
mass_editing





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





# No encontrados
studio_customization
digest_enterprise
account_financial_report_date_range
currency_rate_inverted
ms_query




grep -rl '  @api.one' /opt/git/ThiemedMigradoOdoo14 | xargs sed -i 's/@api.one/# @api.one/g'
grep -rl '  # @api.multi' /opt/git/ThiemedMigradoOdoo14 | xargs sed -i 's/# # # @api.multi/# # # # @api.multi/g'