# Per-Company Contract Requirements (Dynamic Agreements)

Each operator company configures its own **`Operator Contract Setting`** records (top-level doctype, linked via `operator_company`). Contracts are **not** a single shared pattern — each company has its own templates, terms, fees, and a reusable **field-mapping child table** (`Contract Field Mapping`) that maps template labels → ATM Leads / Agreement Sign Form fields.

## How It Works

1. **Configure per company** — create an `Operator Contract Setting` per company:
   - `operator_company` (link), `contract_title`, `template_name` (esign `TempleteList`), `template_file` + `contract_attachment` (upload PDF/image)
   - `fee_type` (Flat / Revenue Share / Flat + Revenue Share / Per Transaction / Custom), `base_fee`, `revenue_share_percent`, `flat_fee`, `special_terms`
   - `lead_state_trigger` (Requested for Agreement Sent / Approved / Signed / Installed)
   - **`field_mappings` child table** (`Contract Field Mapping`): each row = `template_field_label` (exact PDF label) + `atm_leads_field` (dropdown of ATM Leads fields) + `source_doctype` (ATM Leads / Agreement Sign Form / Static) + optional `static_value`. This mapping is **reusable** for every lead/agreement of that company.

2. **API resolution** (`cclms/api/agreement_signing.py`):
   - `get_company_contract_settings(company)` → all enabled contracts for a company
   - `get_contract_settings_for_lead(lead)` → picks the contract whose `lead_state_trigger` matches the lead state; falls back to the first enabled contract
   - `create_agreement_from_lead(lead)` → creates a `DocumentList`, links `atm_lead_link`, auto-fills components via the `field_mappings` child table (+ Agreement Sign Form)
   - `request_agreement_for_lead(lead, guest_email)` → creates + auto-fills + assigns a guest, returns `/esignDash/doc/<name>` share URL (partner/manager role only)
   - `mark_lead_signed_from_esign(document)` → sets ATM Lead `Signed` + `sign_date` when the esign doc completes

## Field Mapping (reusable per company)

- **`Contract Field Mapping`** (child of `Operator Contract Setting`): `template_field_label` → `atm_leads_field` (dropdown of ATM Leads fields: business_name, owner_name, business_phone_number, email, full_address, city, state, zip_code, company, post_date, etc.) + `source_doctype` + `static_value`.
- Resolution order: Static → Agreement Sign Form → ATM Leads → empty.
- The mapping is stored per contract (per company), so the same PDF template can reuse the mapping for every lead automatically.

## Known Contract Templates (from site private files)

| Company | Contract / Template | Fee structure | Key fill fields |
|---|---|---|---|
| **Bitcoin Depot** | KPF RevShare (`Template.KPF.RevShare.2024-5-20.LIVE`) | $300/mo first 3 months → Effective Fee Revenue % | Location Legal Entity, Effective Date, DBA Name, Phone, Email, Payment Address, Sales Contact, Account Manager, Tenant/Landlord, lease end, Term, Premises, Additional Entity, Effective Fee Revenue %, signatures |
| **Bitcoin Depot** | KPF Distributors (`Template.KPF.Distributors.July2023`) | Per Trans. Fee + Flat Fee | same + County, Distributor, Per Trans. Fee, Flat Fee |
| **Crypto Base** | KPF Distributors / Placement | Per-transaction / flat | see above |
| **Rocket Coin / Un Bank / ByteFederal / Coin Works / CoinFlip / Athena / ATM Central / CoinConnections** | (not yet configured) | TBD per company | add an `Operator Contract Setting` per company |
| Generic | Harding Capital Lease, Site Acquisition Partnership, Placement/Remote BD Partner agreements | lease / partnership | lease-specific |

## Field Source Priority

For each fill-field, value is resolved in this order:
1. `Agreement Sign Form` field (e.g. `location_legal_entity`, `effective_date`, `tenant_or_landlord`, `contract_end_date`, `county`, `distributer`, `transection_fees`, `flat_fee`, `oprator_name`, `title`, `premises`, `additonal_entity`)
2. `ATM Leads` field (e.g. `business_name`, `business_type`, `address`, `full_address`, `city`, `state`, `state_code`, `zip_code`, `company`, `owner_name`, `email`, `business_phone_number`, `personal_cell_phone`, `executive_name`, `post_date`)
3. empty

## To Add a New Company's Contract

1. Open `Operator Companies` → the company → **Contract Requirements** → add a row.
2. Set title, pick/create the esign template (`TempleteList`), fee fields, special terms, trigger state.
3. Set `fill_fields_json`, e.g.:
   ```json
   {
     "Location DBA Name": "business_name",
     "Location Legal Entity": "owner_name",
     "Phone": "business_phone_number",
     "Email": "email",
     "Address to be used for payment": "full_address",
     "Effective Date": "post_date"
   }
   ```
4. In the portal, open a lead → **Request Agreement** → the contract is auto-resolved and pre-filled, then a guest can sign via the esign dash link.

> The whole flow is driven by the operator's config, so the same system serves different operators with different templates, fees, and terms — dynamic, not one-size-fits-all.
