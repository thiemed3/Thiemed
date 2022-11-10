odoo.define('theme_clarico_vega.ajax_cart', function (require) {
    "use strict";
    var sAnimations = require('website.content.snippets.animation');
    var publicWidget = require('web.public.widget');
    var core = require('web.core');
    var ajax = require('web.ajax');
    var _t = core._t;
    var WebsiteSale = new sAnimations.registry.WebsiteSale();
    var QWeb = core.qweb;
    var wUtils = require('website.utils');
    var xml_load = ajax.loadXML(
        '/website_sale_stock/static/src/xml/website_sale_stock_product_availability.xml',
        QWeb
    );
    var flag = 1;

    publicWidget.registry.WebsiteSale.include({
        _submitForm: function () {
            let params = this.rootProduct;
            params.add_qty = params.quantity;

            params.product_custom_attribute_values = JSON.stringify(params.product_custom_attribute_values);
            params.no_variant_attribute_values = JSON.stringify(params.no_variant_attribute_values);
            if (this.isBuyNow) {
                params.express = true;
                return wUtils.sendRequest('/shop/cart/update', params);
            }

            /*return new Promise(function () {});*/
            var frm = this.$form
            var variant_count = frm.find('#add_to_cart').attr('variant-count');
            var is_product = $(".not_product_page").length;
            var is_ajax_cart = frm.find('.a-submit').hasClass('ajax-add-to-cart');
            var is_quick_view = frm.find('.a-submit').hasClass('quick-add-to-cart');
            var product_id = frm.find('#add_to_cart').attr('product-id');
            var product_product = frm.find('input[name="product_id"]').val();
            var product_custom_attribute_values = frm.find('input[name="product_custom_attribute_values"]').val();
            var no_variant_attribute_values = frm.find('input[name="no_variant_attribute_values"]').val();
            if(!product_id) {
               product_id = frm.find('.a-submit').attr('product-id');
            }
            if(!variant_count) {
               variant_count = frm.find('.a-submit').attr('variant-count');
            }
            /** Stock availability message for ajax cart popup */
            var combination = [];
            xml_load.then(function () {
                var $message = $(QWeb.render(
                    'website_sale_stock.product_availability',
                    combination
                ));
                $('div.availability_messages').html($message);
            });
            if(is_product == 0 || is_ajax_cart || is_quick_view) {
                /** if product has no variant then success popup will be opened */
                var product_product = frm.find('input[name="product_id"]').val();
                var quantity = frm.find('.quantity').val();
                if(!quantity) {
                   quantity = 1;
                }
                ajax.jsonRpc('/shop/cart/update_custom', 'call',{'product_id':product_product,'add_qty':quantity, 'product_custom_attribute_values':product_custom_attribute_values,'no_variant_attribute_values':no_variant_attribute_values}).then(function(data) {
                    var ajaxCart = new publicWidget.registry.ajax_cart();
                    if(data) {
                        $('.ajax_cart_modal > .cart_close').trigger('click');
                        $('.quick_view_modal > .quick_close').trigger('click');
                        var $quantity = $(".my_cart_quantity");
                        var old_quantity = $quantity.html();
                        $quantity.parent().parent().removeClass('d-none');
                        $quantity.html(parseInt(quantity) + parseInt(old_quantity)).hide().fadeIn(600);

                        if(!product_id) {
                            product_id = frm.find('.product_template_id').attr('value');
                        }
                        setTimeout(function(){
                            ajaxCart.ajaxCartSucess(product_id, product_product);
                            $('input[name="product_custom_attribute_values"]').remove();
                        }, 700);
                        /* Resize menu */
                        setTimeout(() => {
                            $('#top_menu').trigger('resize');
                        }, 200);
                    }
                });
            } else {
            /** if product has multiple variants then variant selection popup will be opened */
                ajax.jsonRpc('/ajax_cart_item_data', 'call',{'product_id':product_id}).then(function(data) {
                    var WebsiteSale = new sAnimations.registry.WebsiteSale();
                    WebsiteSale._startZoom();
                    if($("#wrap").hasClass('js_sale'))
                    {
                        $("#ajax_cart_model_shop .modal-body").html(data);
                        $("#ajax_cart_model_shop").modal({keyboard: true});
                    } else {
                        $("#ajax_cart_model .modal-body").html(data);
                        $("#ajax_cart_model").modal({keyboard: true});
                    }
                    $('#ajax_cart_model, #ajax_cart_model_shop').removeClass('ajax-sucess');
                    $('#ajax_cart_model, #ajax_cart_model_shop').addClass('ajax-cart-item');

                    /** trigger click event for the variant change and qty */
                    if (flag) {
                        WebsiteSale.init();
                        $(document).on('click', '.ajax_cart_content input.js_product_change', function(ev){
                            WebsiteSale.onChangeVariant(ev);
                        });
                        $(document).on('change', '.ajax_cart_content .js_main_product [data-attribute_exclusions]', function(ev){
                            WebsiteSale.onChangeVariant(ev);
                        });
                        $(document).on('change', '.ajax_cart_content .js_product:first input[name="add_qty"]', function(ev){
                            WebsiteSale._onChangeAddQuantity(ev);
                        });
                        $(document).on('click', '.ajax_cart_content a.js_add_cart_json', function(ev){
                            WebsiteSale._onClickAddCartJSON(ev);
                        });
                        flag = 0;
                     }

                    /** Product gallery will be refreshed */

                    setTimeout(function(){
                        $('.ajax_cart_content #product_detail #thumbnailSlider').show();
                        var theme_script = new sAnimations.registry.product_detail();
                        theme_script.productGallery();
                        $('#mainSlider .owl-carousel').trigger('refresh.owl.carousel');
                        $('#thumbnailSlider .owl-carousel').trigger('refresh.owl.carousel');
                        WebsiteSale._startZoom();
                    }, 200);
                    $('.variant_attribute  .list-inline-item').find('.active').parent().addClass('active_li');
                    $( ".list-inline-item .css_attribute_color" ).change(function(ev) {
                        var $parent = $(ev.target).closest('.js_product');
                        $parent.find('.css_attribute_color').removeClass("active");
                        $parent.find('.css_attribute_color').parent('.list-inline-item').removeClass("active_li");
                        $parent.find('.css_attribute_color').filter(':has(input:checked)').addClass("active");
                        $parent.find('.css_attribute_color').filter(':has(input:checked)').parent('.list-inline-item').addClass("active_li");
                    });
                    setTimeout(function(){
                        var quantity = $('.ajax_cart_content').find('.quantity').val();
                        $('.ajax_cart_content').find('.quantity').val(quantity).trigger('change');
                    },500);
                });
            }
        },
        _onClickSubmit: function (ev, forceSubmit) {
            if ($(ev.currentTarget).is('#add_to_cart, #products_grid .a-submit') && !forceSubmit) {
                return;
            }
            /** If optional products exist, then it will shows variant popup for quick view and sliders */
            var $aSubmit = $(ev.currentTarget);
            if (!ev.isDefaultPrevented() && !$aSubmit.is(".disabled")) {
                ev.preventDefault();
                var is_quick_view = $aSubmit.hasClass('quick-add-to-cart');
                if (is_quick_view || ($('#ajax_cart_template').val() == 1 && $aSubmit.parents('.te_pc_style_main').length) ) {
                    var frm = $aSubmit.closest('form');
                    var product_product = frm.find('input[name="product_id"]').val();
                    var quantity = frm.find('.quantity').val();
                    var product_custom_attribute_values = frm.find('input[name="product_custom_attribute_values"]').val();
                    if(!quantity) {
                       quantity = 1;
                    }
                    ajax.jsonRpc('/shop/cart/update_custom', 'call',{'product_id':product_product,'add_qty':quantity, 'product_custom_attribute_values':product_custom_attribute_values}).then(function(data) {
                        var ajaxCart = new publicWidget.registry.ajax_cart();
                        if(data) {
                            var $quantity = $(".my_cart_quantity");
                            var old_quantity = $quantity.html();
                            $quantity.parent().parent().removeClass('d-none');
                            $quantity.html(parseInt(quantity) + parseInt(old_quantity)).hide().fadeIn(600);

                            $('.ajax_cart_modal > .cart_close').trigger('click');
                            $('.quick_view_modal > .quick_close').trigger('click');
                            var product_id = frm.find('.product_template_id').attr('value');
                            setTimeout(function(){
                                ajaxCart.ajaxCartSucess(product_id, product_product);
                                $('input[name="product_custom_attribute_values"]').remove();
                            }, 700);
                            /* Resize menu */
                            setTimeout(() => {
                                $('#top_menu').trigger('resize');
                            }, 200);
                        }
                    });
                } else {
                    $aSubmit.closest('form').submit();
                    $('.ajax_cart_modal > .cart_close').trigger('click');
                    $('.quick_view_modal > .quick_close').trigger('click');
                }
            }
            if ($aSubmit.hasClass('a-submit-disable')){
                $aSubmit.addClass("disabled");
            }
            if ($aSubmit.hasClass('a-submit-loading')){
                var loading = '<span class="fa fa-cog fa-spin"/>';
                var fa_span = $aSubmit.find('span[class*="fa"]');
                if (fa_span.length){
                    fa_span.replaceWith(loading);
                } else {
                    $aSubmit.append(loading);
                }
            }
        }
    });
    publicWidget.registry.ajax_cart = publicWidget.Widget.extend({
        selector: ".oe_website_sale",
        ajaxCartSucess: function(product_id, product_product){
            /** Success popup */
            ajax.jsonRpc('/ajax_cart_sucess_data', 'call',{'product_id':product_id, 'product_product':product_product}).then(function(data) {
                if($("#wrap").hasClass('js_sale')) {
                    $("#ajax_cart_model_shop .modal-body").html(data);
                    $("#ajax_cart_model_shop").modal({keyboard: true});
                } else {
                    $("#ajax_cart_model .modal-body").html(data);
                    $("#ajax_cart_model").modal({keyboard: true});
                }
                $('#ajax_cart_model, #ajax_cart_model_shop').removeClass('ajax-cart-item');
                $('#ajax_cart_model, #ajax_cart_model_shop').addClass('ajax-sucess');

            });
        }
    });
    $(document).on('click', '.ajax-sucess-continue', function(){
        $('.ajax_cart_modal > .cart_close').trigger('click');
    });
    $(document).on('click', '.ajax_cart_modal #buy_now', function(ev){
        WebsiteSale._onClickAdd(ev);
    });
    if (!$('#ajax_cart_product_template').length) {
        $(document).on('click', '.oe_website_sale #add_to_cart', async function(ev){
            if($('#add_to_cart').hasClass('quick-add-to-cart') || $('.a-submit').attr('optional-product') == 1) {
                ev.preventDefault();
            } else {
                var is_quick_view = $('#add_to_cart').hasClass('quick-add-to-cart');
                if(!is_quick_view) {
                    ev.preventDefault();
                    WebsiteSale._onClickAdd(ev);
                }
            }
        });
    }
});
