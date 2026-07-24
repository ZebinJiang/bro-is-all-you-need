# Model Asset Lifecycle

## Scope

M12 separates five facts that were previously easy to conflate:

1. an immutable asset specification;
2. access evidence;
3. terms evidence;
4. acquisition evidence;
5. verification evidence.

Runtime authorization is a decision over all five identities. File presence, a
provider cache, a completion manifest, a source-code license, or a model card
cannot authorize runtime by itself.

The canonical runtime root remains `base_model/`. Assets, credentials, accepted
terms receipts, checkpoints, tokenizers, provider caches and model payloads are
never tracked. Model runtime remains local-only and never invokes acquisition.

## Compatibility Boundary

`ModelAssetSpec`, `ModelAssetManifest`, `ModelAssetBundle`,
`ModelAssetProvider`, `ModelAssetStore` and their existing constructors remain
available. A v2 completion manifest remains readable and deterministically
derives:

- `AssetAcquisitionReceipt`: provider, revision, exact inventory, provider
  version, downloader version and acquisition time;
- `AssetVerificationReceipt`: expected and observed inventory, size/hash
  decisions, safetensors policy, remote-code policy and terminal result.

This compatibility derivation does not invent access or terms evidence.
`ModelAssetResolver.resolve(key)` remains the established M11 local read-only
verification surface, so existing N1D6 factory callers do not fail merely
because they do not yet supply M12 policy objects. It never authorizes runtime.

M12 activation uses the distinct
`ModelAssetResolver.resolve_authorized(key, evidence)` surface. It requires an
exact `AssetAuthorizationPolicy` and `AssetLifecycleEvidence` before the store
reads or hashes payload members, and returns `AuthorizedModelAsset` rather than
`ResolvedModelAsset`. Later family activation can therefore require the
authorization-bearing result explicitly without confusing local verification
with runtime authorization. Missing policy or evidence fails before payload
verification.

## Independent Terms

`AssetTermsKind` keeps these identities separate:

- `code_license`
- `model_checkpoint`
- `tokenizer`
- `dataset_content`
- `conversion_input`
- `conversion_output`
- `derived_weight_provenance`

One category never satisfies another. In particular, an Apache-2.0 source
license is not checkpoint authorization, local possession of Gemma terms is not
acceptance, and a dataset backend license is not a license for dataset content.
Conversion input, conversion output and derived weights retain separate
provenance and terms decisions.

Terms states are `unknown`, `required`, `accepted_by_user`, `rejected` and
`not_applicable`. An `accepted_by_user` receipt is valid only when it cites a
full external receipt identity, an explicit user authority and a UTC acceptance
time. AutoVLA code has no API that transitions terms to accepted and does not
write user acceptance receipts.

## Access Evidence

Access states are `public`, `gated_unconfirmed`, `granted`, `denied` and
`unavailable`. A `granted` receipt requires a full external evidence identity
and a public HTTPS evidence source. Gated presence in a cache is not a grant.
Denied, unavailable and unconfirmed states cannot satisfy an authorization
policy.

Receipt objects contain no token, credential, signed URL, local absolute user
path or provider secret. User-owned access and terms evidence belongs under the
ignored `base_model/.receipts/<asset-key>/<revision>/` boundary. The read-only
layout uses `access.json` plus `terms/<terms-kind>.json`; symlinks, mismatched
filenames, unknown members and receipts for another spec/revision fail closed.
This wave defines no receipt writer, acquisition action or terms-acceptance
command.

## Acquisition And Verification

Acquisition receipts bind the exact asset key, specification identity,
provider, revision, complete inventory, provider/downloader versions and
timestamp. Partial inventories and superseded receipts cannot authorize.

Verification receipts bind their acquisition receipt identity and record:

- exact expected and observed inventories;
- exact size and SHA-256 decisions;
- checksum policy;
- safetensors-only decision for every weight role;
- remote-code policy;
- terminal `verified` or `rejected` result.

A verified terminal result requires identical complete inventories, successful
size and hash decisions, safetensors for every model, checkpoint or derived
weight role, and remote code disabled. A weight-role file with any extension
other than `.safetensors` is rejected at store publication and verification
boundaries. Non-weight normalization, tokenizer, processor, license,
configuration and metadata assets are not globally rejected solely for using
extensions such as `.npy`, `.npz` or `.bin`; their loaders remain responsible
for safe non-pickle modes. Asset lifecycle validation never deserializes them.

## Authorization

`ModelAssetResolver.resolve_authorized()` performs these checks in stable order:

1. policy identity exactly matches key, specification identity and revision;
2. exactly one non-superseded access receipt matches the required state;
3. terms receipt categories exactly equal the policy category set;
4. every terms identity, source, scope and required state matches;
5. acquisition provider, revision and complete inventory match the spec;
6. verification binds that acquisition and records the exact verified
   safetensors-only, no-remote-code result;
7. the store revalidates the local completion manifest, containment, size and
   hashes.

Missing, contradictory, stale, partial, rejected, mismatched, unexpected or
superseded evidence returns one stable first blocker. Error text does not echo
external receipt contents.

## Atomicity And Containment

Explicit `fetch` retains the existing private staging, bounded lock, exact
allow-list, symlink/traversal rejection, same-filesystem atomic publication and
no-overwrite behavior. Provider failure removes only the private staging
attempt. A valid final bundle is never overwritten. Persistent provider cache
state does not count as acquisition or verification evidence.

No runtime path enables `trust_remote_code`, arbitrary pickle/Torch loading,
implicit network access, dependency installation or public-identifier fallback.

## CLI

The stable status and action surfaces are:

- `list`: registered immutable specifications;
- `inspect`: one specification, inventory and declared legal metadata;
- `fetch`: explicit acquisition path; the only eventually network-capable
  command;
- `verify`: local exact manifest, containment, inventory and policy validation;
- `path`: path of an already verified local asset;
- `terms`: read-only access/terms receipt status and first blocker without
  reading payload files.

`terms` deliberately reports `gated_unconfirmed` and `required` when the
user-owned receipt root is absent. When strict receipt JSON exists it reports
those states and fingerprints, but still reports the missing authorization
policy instead of claiming runtime authorization. It does not infer public
access from an HTTPS URL and does not infer acceptance from a license file.
`verify` and `path` never download. Training and inference must consume only an
authorized resolver result or a family bundle whose production boundary
performs the same exact store validation.

## Deferred Legal And Access Blockers

This architecture does not resolve existing legal or access questions:

- GR00T N1.7 checkpoint terms conflict remains unresolved;
- Cosmos Reason2 gated acceptance evidence remains missing;
- Pi0.5 Gemma/checkpoint/tokenizer terms evidence remains missing;
- Pi0.5 checkpoint, tokenizer and normalization immutable identities remain
  missing;
- conversion input/output and derived-weight terms remain unresolved;
- V-JEPA2 remains unselected and unregistered.

No family is activated by this contract. No model payload was acquired, opened,
loaded or converted as part of this implementation.
