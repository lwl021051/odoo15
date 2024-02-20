/** @odoo-module **/

import barcodeScanner from '@web_enterprise/webclient/barcode/barcode_scanner';
import { methods } from "web_mobile.core";
import { patch } from 'web.utils';

patch(barcodeScanner, 'barcodes_mobile', {
    isBarcodeScannerSupported() {
        return methods.scanBarcode || this._super(...arguments);
    },

    async scanBarcode() {
        if (methods.scanBarcode) {
            const response = await methods.scanBarcode();
            return response.data;
        }
        return this._super(...arguments);
    },
});
