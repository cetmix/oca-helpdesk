# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import ast

from odoo import _, api, fields, models


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    can_create_activity = fields.Boolean(related="team_id.is_set_activity")
    res_model = fields.Char(string="Source Document Model", index=True)
    res_id = fields.Integer(string="Source Document", index=True)

    record_ref = fields.Reference(
        selection="_referenceable_models",
        compute="_compute_record_ref",
        inverse="_inverse_record_ref",
        string="Source Record",
    )
    source_activity_type_id = fields.Many2one(comodel_name="mail.activity.type")
    date_deadline = fields.Date(string="Due Date", default=fields.Date.context_today)

    @api.model
    def _referenceable_models(self):
        """Select target model for source document"""
        model_ids_str = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("helpdesk_mgmt_activity.helpdesk_available_model_ids", "[]")
        )
        model_ids = ast.literal_eval(model_ids_str)
        if not model_ids:
            return []
        IrModelAccess = self.env["ir.model.access"].with_user(self.env.user.id)
        available_models = self.env["ir.model"].search_read(
            [("id", "in", model_ids)], fields=["model", "name"]
        )
        return [
            (model.get("model"), model.get("name"))
            for model in available_models
            if IrModelAccess.check(model.get("model"), "read", False)
        ]

    @api.depends("res_model", "res_id")
    def _compute_record_ref(self):
        """Compute Source Document Reference"""
        for rec in self:
            if rec.res_model and rec.res_id:
                try:
                    self.env[rec.res_model].browse(rec.res_id).check_access_rule("read")
                    rec.record_ref = "%s,%s" % (
                        rec.res_model,
                        rec.res_id,
                    )
                except Exception:
                    rec.record_ref = None
            else:
                rec.record_ref = None

    def _inverse_record_ref(self):
        """Set Source Document Reference"""
        for record in self:
            if record.record_ref:
                res_id = record.record_ref.id
                res_model = record.record_ref._name
            else:
                res_id, res_model = False, False
            record.write({"res_id": res_id, "res_model": res_model})

    def _check_activity_values(self):
        """Check activity values for helpdesk ticket"""
        if not self.can_create_activity:
            raise models.UserError(_("You cannot create activity!"))
        if not (self.res_id and self.res_model):
            raise models.UserError(_("Source Record is not set!"))
        if not self.source_activity_type_id:
            raise models.UserError(_("Activity Type is not set!"))
        if not self.date_deadline:
            raise models.UserError(_("Date Deadline is not set!"))

    def perform_action(self):
        self._check_activity_values()
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Helpdesk Ticket Action",
            "view_mode": "form",
            "res_model": "mail.activity",
            "view_type": "form",
            "context": {
                "default_res_model_id": self.env["ir.model"]._get_id(self.res_model),
                "default_res_id": self.res_id,
                "default_activity_type_id": self.source_activity_type_id.id,
                "default_date_deadline": self.date_deadline,
                "default_note": self.description,
                "default_ticket_id": self.id,
                "default_summary": self.name,
                "default_user_id": self.user_id.id,
            },
            "target": "new",
        }