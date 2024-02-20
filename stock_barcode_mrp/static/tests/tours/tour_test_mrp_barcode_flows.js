odoo.define('test_mrp_barcode_flows.tour', function(require) {
'use strict';

var helper = require('stock_barcode.tourHelper');
var tour = require('web_tour.tour');

tour.register('test_receipt_kit_from_scratch_with_tracked_compo', {test: true}, [
    {
        trigger: '.o_barcode_client_action',
        run: 'scan kit_lot',
    },
    {
        trigger: '.o_barcode_line:contains("Kit Lot") .o_edit',
    },
    {
        trigger: '.o_digipad_button[data-button="increase"]',
    },
    {
        trigger: '.o_save',
    },
    {
        trigger: '.o_barcode_line:contains("Kit Lot") .o_add_quantity'
    },
    {
        trigger: '.o_barcode_line:contains("Kit Lot") .qty-done:contains("3")',
        run: 'scan simple_kit',
    },
    {
        extra_trigger: '.o_barcode_line:contains("Simple Kit")',
        trigger: '.btn.o_validate_page',
    },
    {
        extra_trigger: '.o_notification.bg-warning',
        trigger: '.o_barcode_line:contains("Compo Lot")',
        run: function() {
            helper.assertLinesCount(4);
            const $kit_lot_compo01 = $('.o_barcode_line:contains("Compo 01"):contains("Kit Lot")');
            const $kit_lot_compo_lot = $('.o_barcode_line:contains("Compo Lot"):contains("Kit Lot")');
            const $simple_kit_compo01 = $('.o_barcode_line:contains("Compo 01"):contains("Simple Kit")');
            const $simple_kit_compo02 = $('.o_barcode_line:contains("Compo 02"):contains("Simple Kit")');

            helper.assertLineQty($kit_lot_compo01, '3');
            helper.assertLineQty($kit_lot_compo_lot, '3');
            helper.assertLineQty($simple_kit_compo01, '1');
            helper.assertLineQty($simple_kit_compo02, '1');
        }
    },
    {
        trigger: '.o_barcode_line:contains("Compo Lot")',
    },
    {
        trigger: '.o_selected:contains("Compo Lot")',
        run: 'scan super_lot',
    },
    {
        extra_trigger: '.o_line_lot_name:contains("super_lot")',
        trigger: '.btn.o_validate_page',
    },
    {
        trigger: '.o_notification.bg-success'
    },
]);

});
