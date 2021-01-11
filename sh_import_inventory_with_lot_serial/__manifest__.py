# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
{
    "name" : "Import Stock Inventory With Lot/Serial Number from CSV/Excel file",
    "author" : "Softhealer Technologies",
    "website": "https://www.softhealer.com",
    "category": "Warehouse",
    "summary": "This module useful to import stock inventory with lot/serial number from csv/excel.",
    "description": """
    
 This module useful to import stock inventory with lot/serial number from csv/excel. 

                    """,    
    "version":"11.0.1",
    "depends" : ["base","sh_message","stock","product"],
    "application" : True,
    # "data" : ['security/import_inventory_with_lot_serial_security.xml',
    #         'wizard/import_inventory_with_lot_serial_wizard.xml',
    #         'views/stock_view.xml',
            # ],         
    'external_dependencies' : {
        'python' : ['xlrd'],
    },                  
    "images": ["static/description/background.png",],              
    "auto_install":False,
    "installable" : True,
    "price": 25,
    "currency": "EUR"   
}
