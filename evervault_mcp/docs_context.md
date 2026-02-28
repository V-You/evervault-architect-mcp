# Evervault documentation context

Curated reference for the AI agent to answer questions about Evervault
without leaving the IDE. Source: https://docs.evervault.com/

---

## Core concepts

Evervault is a developer-first platform for orchestrating secure data flows.
It enables collection, storage, processing, and forwarding of sensitive
information without adding compliance burden.

At its core, Evervault encrypts sensitive data into ciphertext which can be
safely stored in your infrastructure and decrypted at runtime.

### Dual custody encryption model

Evervault does not use a traditional token vault. Instead, it uses a dual
custody model: you store the encrypted data, Evervault manages the keys.

Advantages over token vaults:
- Faster: no database lookups on Evervault's side
- More secure: an attacker would need to breach both your infrastructure
  and Evervault to access decrypted values

### Encrypted data format

Encrypted values look like: `ev:debug:Tk9D:GWgxSXez:...`

The `ev:` prefix identifies Evervault-encrypted data. These tokens can be
safely stored in your database, passed through APIs, and logged without
exposing the underlying plaintext.

---

## Core products

### Relay

Relay is a configurable network proxy that can automatically encrypt or
decrypt data in transit -- between your app and your own APIs, or any
third-party APIs.

Key features:
- No code changes required -- operates at the network layer
- Path matching: `/**` (catchall) or `/checkout` (specific)
- Field selection via JSONPath: `$.card.number`
- Supports encrypt and decrypt actions on request and response
- Route-level configuration for granular control

When to use Relay:
- Securing API traffic without touching application code
- Encrypting data before it reaches your database
- Decrypting data for third-party integrations (e.g., payment processors)

API: POST/GET/PATCH/DELETE /relays
Docs: https://docs.evervault.com/relay

### Functions

Functions are secure serverless code environments that decrypt encrypted
data at runtime. You write custom logic in Node.js or Python, and Evervault
automatically decrypts any encrypted values passed as input.

Key features:
- Auto-decryption of ev:... tokens in function input
- Your infrastructure never sees plaintext
- Node.js and Python runtimes supported
- Triggered via API: POST /functions/{function_name}/runs

When to use Functions:
- Processing sensitive data with custom business logic
- Third-party integrations that need plaintext (e.g., analytics, CRM)
- PII scrubbing or transformation pipelines

API: POST /functions/{function_name}/runs
Docs: https://docs.evervault.com/functions

### Enclaves

Enclaves let you build, deploy, and scale applications in a confidential
computing environment (AWS Nitro Enclaves). They provide hardware-level
isolation for your most sensitive workloads.

Key features:
- Hardware-level isolation via AWS Nitro
- Configured via enclave.toml and Dockerfile
- Egress allowlists for controlled network access
- Attestation for verifiable security guarantees

When to use Enclaves:
- Processing highly sensitive data (healthcare, financial)
- Workloads requiring verifiable security guarantees
- Multi-party computation scenarios

Docs: https://docs.evervault.com/enclaves

---

## Encryption types

### Standard encryption
- Non-deterministic: same plaintext produces different ciphertext each time
- Use for: data that does not need to be searchable or indexable
- Examples: addresses, notes, documents

### Deterministic encryption
- Same plaintext always produces the same ciphertext
- Use for: fields that need to be searchable, indexable, or used as keys
- Examples: email addresses, phone numbers, SSNs
- Configured via the "role" parameter when encrypting

---

## API reference summary

Base URL: https://api.evervault.com
Auth: HTTP Basic (app_id:api_key)
OpenAPI spec: https://docs.evervault.com/api-spec.json

### Core endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | /encrypt | Encrypt any JSON value |
| POST | /decrypt | Decrypt any JSON value |
| POST | /inspect | Get metadata for an encrypted token |
| POST | /functions/{name}/runs | Run a Function |
| POST | /client-side-tokens | Create a client token |

### Relay endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | /relays | Create a Relay |
| GET | /relays | List all Relays |
| GET | /relays/:id | Retrieve a Relay |
| PATCH | /relays/:id | Update a Relay |
| DELETE | /relays/:id | Delete a Relay |

---

## Compliance

Evervault is a PCI DSS Level 1 Service Provider. Using Evervault to handle
card data can help reduce your PCI compliance scope.

Products for compliance:
- PCI compliance: become PCI DSS compliant in days
- ASV scans: identify security weaknesses in public-facing systems
- Page protection: track third-party scripts and protect pages

Docs: https://docs.evervault.com/compliance/pci-compliance

---

## Payments

Evervault provides tools for secure payment flows:
- Card collection: safely collect and encrypt card data
- 3D Secure: reduce fraud with additional authentication
- Network tokens: use network tokens instead of card numbers
- Card account updater: automatically update card details
- BIN lookup: retrieve metadata for card numbers
- Card reveal: safely display encrypted card numbers

Docs: https://docs.evervault.com/cards/card-collection

---

## SDKs and developer tools

- Node.js SDK: @evervault/sdk
- Python SDK: evervault
- API keys: manage in the Evervault Dashboard (App Settings)
- CLI: available for Function and Enclave deployment

Docs: https://docs.evervault.com/sdks
