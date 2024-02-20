/** @odoo-module **/
import { HomeMenu } from "@web_enterprise/webclient/home_menu/home_menu";
import { url } from "@web/core/utils/urls";
import { patch } from "@web/core/utils/patch";

patch(HomeMenu.prototype, "web_studio.HomeMenuBackground", {
    setup() {
        this._super();
        if (!this.menus.getMenu("root").backgroundImage) {
            return;
        }
        this.backgroundImageUrl = url("/web/image", {
            id: this.env.services.company.currentCompany.id,
            model: "res.company",
            field: "background_image",
        });
    },
    mounted() {
        this._super();
        document.body.classList.toggle("o_home_menu_background_custom", this.menus.getMenu("root").backgroundImage);
    },
    willUnmount() {
        this._super();
        document.body.classList.remove("o_home_menu_background_custom");
    },
});
