# n8n integration architecture

n8n is an integration gateway, not the source of truth. OrbitOps signs a narrowly scoped webhook containing `tenant_id`, `approved_action_id`, `idempotency_key`, and artifact references. n8n fetches sensitive payloads using a short-lived service token, performs connector work, then posts a signed result callback. Duplicate idempotency keys must return the first result.

Recommended workflows:

1. **CRM lead intake:** signed CRM webhook → normalize/map → OrbitOps `POST /leads` → optional workflow start → CRM external ID update.
2. **Email delivery:** approved-action webhook → fetch approved immutable draft → consent/suppression check → provider send → callback with provider message ID.
3. **WhatsApp delivery:** approved-action webhook → consent and quiet-hours check → Twilio/Meta send → delivery status callback → conversation event.
4. **Scheduled reporting:** cron → request report run → poll/event wait for approval → publish to S3/email/Slack only after approval.
5. **CRM synchronization:** OrbitOps domain event → upsert by external ID → retry transient errors → dead-letter and alert permanent mapping failures.

Keep credentials in n8n's encrypted credential store backed by an external database and KMS-managed secret. Restrict community nodes, pin versions, isolate execution workers, redact execution data, and export reviewed workflow JSON to source control. The sample in `n8n/lead-intake.workflow.json` is intentionally delivery-free.

