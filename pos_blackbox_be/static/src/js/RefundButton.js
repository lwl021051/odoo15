odoo.define('pos_blackbox_be.RefundButton', function (require) {
    'use strict';

    const Chrome = require('point_of_sale.RefundButton');
    const Registries = require('point_of_sale.Registries');
    const { Gui } = require('point_of_sale.Gui');
    var core    = require('web.core');
    var _t      = core._t;

    const PosBlackboxBeRefundButton = (Chrome) =>
        class extends Chrome {
            _onClick() {
                if(this.env.pos.useBlackBoxBe() && !this.env.pos.check_if_user_clocked()) {
                    Gui.showPopup('ErrorPopup',{
                        'title': _t("POS error"),
                        'body':  _t("User must be clocked in."),
                    });
                    return;
                }
                return super._onClick();
            }
        };

    Registries.Component.extend(Chrome, PosBlackboxBeRefundButton);

    return Chrome;
});
