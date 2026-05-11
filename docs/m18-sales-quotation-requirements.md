# M18 Sales Quotation Detailed Requirements

## Objective

Build a reusable M18 integration architecture centered on Sales Quotation
as the first vertical slice, while also including foundational customer
lookup capabilities. The architecture must support:

- user-facing agent interaction
- quotation-specific business rules
- customer and customer-contact lookup rules
- code-to-ID resolution where required
- stable M18 API execution

This first phase focuses only on the official M18 Sales Quotation object:

- menu code: `oldqu`
- main table: `mainqu`
- line table: `qut`
- remarks table: `remqu`

## Business Problem

Users naturally provide business codes such as:

- customer code: `cusCode`
- product code: `proCode`
- unit code: `unitCode`

However, M18 uses two different write patterns:

- `bsFlow` endpoints can often accept business codes directly
- standard `save` endpoints often require internal IDs

The system must bridge this mismatch without exposing internal M18
complexity to the user.

## In Scope

Phase 1 must support the following quotation capabilities:

- search sales quotations
- load a quotation by `recordId`
- create a quotation draft using business codes
- create or update a quotation using explicit internal IDs
- translate M18 validation and lookup errors into business-readable output

Phase 1 must also support the following customer lookup capabilities:

- search customers
- load customer master data
- query customer contacts
- provide customer lookup data for quotation creation flows

## Out of Scope

Phase 1 does not include:

- approval workflow actions
- attachment handling
- EBI reporting
- bulk import
- batch update
- advanced cross-document linking
- automated workflow submission
- full master-data maintenance beyond lookup support

## Functional Requirements

### FR-1 Search Quotations

The system must support quotation search through:

- `GET /jsf/rfws/search/search?stSearch=oldqu&beId={beId}`

Inputs:

- `beId`
- optional `quickSearchStr`
- optional pagination parameters

Outputs:

- raw result payload from M18
- normalized summary for agent presentation

### FR-2 Load Quotation

The system must support quotation loading through:

- `GET /jsf/rfws/root/api/read/oldqu?menuCode=oldqu&id={id}`

Inputs:

- `recordId`
- optional `iRev`

Outputs:

- full quotation payload
- user-friendly summary

### FR-3 Create Draft by Codes

The system must support draft creation through:

- `POST /jsf/rfws/erp/bsFlow/save/oldqu`

Minimum inputs:

- `beCode`
- `cusCode`
- one or more quotation lines

Each draft line must support:

- `proCode`
- `unitCode`
- `qty`
- `up`
- optional `disc`

Expected outputs:

- `tranId`
- `tranCode`
- `status`
- `message`

### FR-4 Create or Update by IDs

The system must support standard create or update through:

- `PUT /jsf/rfws/root/api/save/oldqu?menuCode=oldqu`

Inputs:

- header values for `mainqu`
- line values for `qut`
- optional remarks for `remqu`

If the caller provides only business codes, the system must resolve them to
internal IDs before standard save.

Expected outputs:

- `recordId`
- `status`
- `messages`

### FR-6 Search Customers

The system must support customer search using the customer master object.

Typical inputs:

- `beId`
- optional `quickSearchStr`
- optional pagination parameters

Typical outputs:

- customer code
- customer ID
- display name / description
- last modified date when available

This capability is used both as a standalone business function and as a
supporting lookup for quotation flows.

### FR-7 Load Customer

The system must support loading a single customer master record by ID.

Typical inputs:

- `customerId`

Typical outputs:

- customer header data
- customer account or profile data when returned by M18
- any contact-related child data exposed by the customer object

### FR-8 Query Customer Contacts

The system must support customer-contact lookup.

Because customer contact storage may vary by M18 configuration, the design
must support two implementation patterns:

- contact data returned as part of customer master read output
- contact data queried from a dedicated child object or related lookup

Minimum business outputs should include, where available:

- contact name
- contact code or identifier
- phone
- email
- department
- position / title

If contact data is unavailable for the customer or not exposed by the current
M18 API response, the system must return a clear business message.

## Code vs ID Strategy

This is the key design rule for the whole system.

### Rule Set

- users should be allowed to provide business codes
- the agent must never resolve IDs directly
- the skill decides whether a write path should use codes or IDs
- the resolver layer performs `code -> ID` conversion when needed
- the API client only executes the final payload

### Path Selection

Use `bsFlow` when:

- creating a new draft
- the request provides business codes
- the operation benefits from M18 auto-completion defaults

Use standard `save` when:

- updating an existing quotation
- precise field-level control is required
- internal IDs are already available

For this verified UAT environment, standard quotation save has one confirmed
environment-specific rule:

- `qut.unitId` must follow the environment's quotation line unit strategy
- in the verified path for product `PGD798MB`, the successful `unitId` equals
  `proId`
- therefore standard quotation line unit resolution must remain configurable
  instead of assuming universal unit-master mapping

### Resolver Rules

- do not resolve IDs when `bsFlow` can be used directly
- resolve IDs only when standard `save` requires them
- fail clearly if zero or multiple matches are found
- never guess among multiple matches

## Error Handling Requirements

The system must handle:

- authentication failure
- permission failure
- record not found
- missing required fields
- M18 business-rule validation errors
- invalid business code lookups
- ambiguous lookup results
- server failure
- timeout
- customer code not found
- customer contact not found

Common M18 error translations:

- `core_101905`: required field is missing
- `core_141019`: record not found or no access
- `core_201`: unit ID conflict — the resolved unit is already in use; use `proId` as `unitId` instead

When M18 returns structured `messages` or `CheckMsg`, the system must prefer
structured content over generic HTTP text.

## Non-Functional Requirements

- credentials must not be hard-coded in source files
- token reuse and refresh must be supported
- request retry must be available for transient failures
- logs must be sufficient for troubleshooting
- business layers must remain separate from transport logic
- the design must be reusable for future objects such as `oldso`, `po`, `cus`,
  `pro`, and `EBI`

## Phase 1 Deliverables

Phase 1 should produce:

- one user-facing sales quotation agent definition
- one quotation skill definition
- one customer lookup skill definition
- one shared M18 API client
- one quotation-specific API wrapper
- one customer-specific API wrapper or a clearly documented reuse of the
  shared client
- one shared reference resolver
- one quotation domain service
- one customer domain service
- test scaffolding for API, resolver, and service behavior
- sample invocation examples

## UAT-Verified Values

The following values have been verified in the current UAT environment:

- `beId = 7`
- `beCode = PUS`
- `cusCode = 320`
- `cusId = 24`
- `proCode = PGD798MB`
- `proId = 497`
- `unitCode = PCS`
- customer contacts are stored in `data.cust`
- draft quotation creation required explicit `staffId = 197`
- verified quotation standard save used `curId = 3`
- verified quotation standard save used `flowTypeId = 5`
