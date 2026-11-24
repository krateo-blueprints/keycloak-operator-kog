---
type: Log
title: keycloak-config-kog — log
description: Curated chronological history of keycloak-config-kog — notable changes, validation milestones and design decisions, not a generated changelog.
resource: oci://ghcr.io/krateo-blueprints/charts/keycloak-config-kog
tags: [log, history, keycloak]
timestamp: 2026-08-11T00:00:00Z
---

# Log

Curated history; release notes live in GitHub Releases.

## 2026-11-24 — the repository is `keycloak-operator-kog`

Renamed from `krateo-keycloak-operator-kog` (krateo-blueprints repository standard, R1); GitHub redirects the old name. The
published chart keeps its name, `keycloak-config-kog`. Added `LICENSE` (Apache-2.0). `home` and `sources` name the repository,
and the shared release workflows move to krateo-blueprints/charts 1.11.0, whose publisher resolves a renamed owner.

## 2026-11-24 — KeycloakDefaultClientRegistrationPolicy, adopt-only (0.16.0)

**Why.** On a fresh install the registration-policy CRs race the realm they belong to. Keycloak refuses the create while the
realm does not exist (404); a second later the realm exists **with its own default policies**, and rest-dynamic-controller
retries the create without looking again (oasgen-provider #919). Keycloak does not refuse a second policy of the same name, so
the realm ended with two "Trusted Hosts", two "Allowed Client Scopes" and two "Max Clients Limit", and the CRs matched two
and could not converge. It failed closed (anonymous registration refused). Two earlier fresh installs had converged by luck.

**What.** `KeycloakDefaultClientRegistrationPolicy`: findby, get and update, **no create and no delete**. It waits until the
realm has the policy (Ready False `NoCreateVerbDeclared` until then, recovering by itself), keeps it as declared, and leaves
it as it is when the CR is deleted, whatever the deletion policy says. Same spec as `KeycloakClientRegistrationPolicy`, which
stays for policies the realm does not have. The `clientoptionalclientscope` schema description names its own kind.

**Validated live on kc-roll057** (oasgen 0.91.1, Keycloak 26.6.3): the race provoked on purpose, 3 CRs applied before each of
16 realms was created at once. New kind: 24/24 Ready, 3 policies in each of 8 realms. Control, the existing kind: 0/24 Ready,
6 policies in each of 8 realms. Then 48 observes without an update over 420 s, a hand change reverted in 19 s, and a CR
deleted with `deletion-policy: delete` left its policy in place.

## 2026-11-24 — KeycloakClientOptionalClientScope, missing policy keys are drift, realm offline sessions (0.15.0)

**Needs oasgen-provider (and its CRDs) >= 0.91.1.** An older RestDefinition CRD prunes `statusSchema` and
`requirePresentFields` silently, and before 0.89.0 rejects the new kind.

**What.**
- `KeycloakClientOptionalClientScope`: one client scope assigned to one client as optional, by their names. Keycloak ignores
  `optionalClientScopes` on a client update, and a requested scope the client does not hold is a hard `invalid_scope`.
  Delegated to RESTActions. Its observe raises on any failure that is not a 404, so "unknown" never reads as "absent"; its
  delete re-reads the client's scopes and raises while the scope is still there. Both are needed: snowplow answers 200 when
  a stage failed and rest-dynamic-controller only warns, and Keycloak's DELETE answers 204 whether or not it removed
  anything. No `get`: Keycloak has none for an assignment, and a list `get` would hold the finalizer forever.
- `KeycloakClientRegistrationPolicy`: every `config` key is `requirePresentFields`. Keycloak's defaults omit keys, and a
  declared key missing from Keycloak's object was ignored, so an adopted policy read Ready while its restriction was never
  sent. **An upgrade sends such keys**: check the policies you adopted. An empty list clears a key (the only way to: the
  component PUT keeps a key left out of it). Limit: a policy whose whole `config` ends up empty keeps being re-sent
  (oasgen-provider #912).
- `KeycloakRealm`: `offlineSessionIdleTimeout`, `offlineSessionMaxLifespanEnabled`, `offlineSessionMaxLifespan`.

**Validated live on kc-roll057** (oasgen 0.91.1, Keycloak 26.6.3, throwaway realms, test variants removed):
- assign → Ready with typed status; quiet over 400 s; a hand unassign re-assigned (129 s); the client's other scopes
  unchanged throughout;
- observe broken with a non-404 → `ObserveFailed`, not re-created; a DELETE without effect, and a refused lookup → finalizer
  held (11 and 12 refused retries), then released once restored; realm deleted first → released;
- a declared key Keycloak lacked was sent, then quiet; the 0.14.0 kind beside it stayed Ready without it (control); `[]`
  cleared it in one update and settled, and drift on the neighbouring key was still corrected afterwards; a single-key
  policy set to `[]` kept being re-sent (#912).

**Corrected while building it.** `continueOnError` on a mutation stage was never needed for Keycloak's empty 204s (snowplow
>= 1.12.48 accepts them); removing it does not make a delete failure propagate either. A first draft refused empty lists at
admission: wrong, 5 of the 8 keys are legitimately empty.

## 2026-11-22 — KeycloakClientScopeProtocolMapper and an optional KeycloakClientScope id (0.14.0)

**Why.** Anonymously registered agent clients get their audience, groups and username claims from a shared client scope
(`mcp`), and the audience follows a cluster's hostname, so the scope's mappers must stay in sync. Keycloak ignores
`protocolMappers` on a client-scope PUT (and `defaultClientScopes` on a client PUT): both are create-only (measured on
26.6.3). Client PUTs DO update inline `protocolMappers`.

**What.** `KeycloakClientScopeProtocolMapper` (CRUD on `/client-scopes/{clientScopeId}/protocol-mappers/models`, findby on
`name`, `partialFields: config`), and `KeycloakClientScope` `spec.id` (optional, sent on create) so a chart can give a scope
a deterministic id. Removing `id` from the scope's excludedSpecFields left `spec.required` unchanged (measured on oasgen
0.80.0), so existing CRs are unaffected.

**Validated live on kc-roll057** (oasgen 0.80.0, throwaway realm, test variants removed afterwards): a scope created with a
chosen id got exactly that id; three scope mappers (audience, groups, username) created; an audience change in the CR
reached Keycloak; across two resyncs only `External resource is up to date`; a hand overwrite reverted in 62 s; deleting
one mapper CR removed only that mapper.

**A false alarm, recorded so it is not repeated.** A raw `PUT .../protocol-mappers/models/{id}` without `id` in the body
returns 500, which read as "KeycloakProtocolMapper updates never worked". Live, the installed kind updates fine: with
`partialFields` the rdc merges Keycloak's current object, `id` included, into the PUT body. A raw-API imitation of the
rdc is not the rdc; no change was made to `KeycloakProtocolMapper`.

## 2026-11-22 — KeycloakClientRegistrationPolicy (0.13.0)

**Why.** The third kind for personal-agent sign-in: anonymous dynamic client registration has to be limited to
loopback redirects and the `mcp` scope, and registered clients must start disabled (Diego's decision).

**Measured first** (Keycloak 26.6.3, throwaway realms, deleted): the realm's internal id is a UUID, not its name, and a
POST without `parentId` attaches the component to the realm; the 201 Location ends in the new id; a PUT with only the
spec fields (no id, no parentId) is accepted and keeps the component under the realm; config round-trips exactly as
lists of strings; `GET ...?name=` returns BOTH subTypes of a default and a `subType` parameter is ignored.

**One defect found live and fixed before release.** With the default `identifiersMatchPolicy` (OR) the findby returned on
the first identifier that agreed (`name`) and never compared `subType` (rdc: "findby adopted an external resource on a
SUBSET of the declared identifiers ... notConsulted [subType]"); it adopted the right twin only because the anonymous one
is listed first. The findby now declares `identifiersMatchPolicy: AND`, proved by a CR for the authenticated
`Allowed Client Scopes` adopting the authenticated component (status.id equal), not the anonymous one.

**Validated live on kc-roll057** (oasgen 0.80.0): two anonymous defaults adopted by name + subType and updated
(`Trusted Hosts` to loopback-only, `Allowed Client Scopes` to `mcp` only), the authenticated twin adopted and left as it
was, a new `client-disabled` component created; every CR's status.id equals the Keycloak component it should own;
across two resyncs only `External resource is up to date`; a hand overwrite reverted in 139 s with one update; deleting
the CRs removed only the created component (`delete`) and kept the adopted ones (`orphan`). A first run's update of
`Allowed Client Scopes` was refused by Keycloak because the test realm had no `mcp` scope: documented in usage.

## 2026-11-21 — KeycloakClientProfiles and KeycloakClientPolicies (0.12.0)

**Why.** Personal agents (OpenClaw via anonymous dynamic client registration, Hermes pre-registered) will sign in to
agentiko-mcp-server's `/mcp` as their users. Diego's decisions: loopback-only redirects, anonymously registered
clients disabled until an admin enables them, no CIMD. Enforcing that on registration needs Keycloak's client
policies, which no kind could express.

**Measured before writing the schema** (Keycloak 26.6.3, throwaway realms, deleted): a new realm has empty profiles and
policies; a PUT round-trips exactly (configuration stored verbatim, a boolean stays a boolean and the string
`"true"` a string); an unknown executor is refused (400). So the kinds are typed: executor and condition ids are
enums, configuration keys typed from the serverinfo configProperties of each provider.

**Validated live on kc-roll057** (oasgen 0.80.0): both RestDefinitions Ready and their CRDs generated with the enum and
the typed keys; the CRs reached Ready and Keycloak's documents equal the spec; across two resyncs each controller
logged only `External resource is up to date` (no write), while a hand overwrite was reverted in 140 s with exactly one
`Successfully requested update of external resource` (the positive control for the quiet count); deleting the CRs left
both documents in place. A first run's quiet count was void (a log filter that matched nothing) and was redone with
the controller's own messages.

## 2026-11-18 — KeycloakUser findby asks for ONE user instead of reading Keycloak's first page

**Measured defect.** The user `findby` listed `GET /admin/realms/{realm}/users` with no parameters, and Keycloak 26
answers that with a default page of **100** users. In a throwaway realm with 105 unmanaged users, a KeycloakUser whose
username sorted **after** the page was created once (Keycloak count 1) and then never found again: the existence check
listed the first page, matched nothing, and the CR went to `CreateOutcomeUnknown` and stayed there. A user sorting
inside the page (the control) reached Ready. So any realm with more than 100 users could strand a managed user right
after creating it, and could not adopt an existing user beyond the page. **Only users page**: in the same realm
`/groups`, `/clients` and `/client-scopes` returned every item (105, 111 and 119).

**Fix.** The asset declares the `username` and `exact` query parameters on that operation. `username` is filled from
`spec.username`; `exact` is a `configurationFields` constant for the `findby` action, so the search is an exact match
and is **not** a CR field (a user cannot turn it off, and a configuration value wins over a same-named spec field).
The Configuration CR carries it at `spec.configuration.query.findby.exact: true`. Exact matters beyond paging: from
oasgen-provider 0.83.0 a findby **refuses** two matching items, and Keycloak's default `username` search is a substring
match. Adding `configurationFields` to an RD that had none is accepted by admission (measured with a server dry-run),
and the provider regenerates the Configuration CRD on the `spec.resource` hash change.

## 2026-11-17 — unreleased: floors 0.78.0; KeycloakUser `groups` is create-only

**Floors raised to oasgen-provider and oasgen-provider-crd `>= 0.78.0`.** oasgen-provider retracted
0.77.0: on a findby-addressed kind a create whose outcome cannot be determined stays Creating forever
instead of reaching `CreateOutcomeUnknown`. Measured on this chart's kinds on 0.78.0 and 0.80.0
(disposable GKE, through the installer): the arm reaches `CreateOutcomeUnknown`, with no extra POSTs.

**`KeycloakUser.spec.groups` applies on create only.** Measured on 0.10.0 / oasgen 0.80.0: a user
created with `groups: [tenants]` joined `tenants`; there were 0 updates over two resyncs (no drift
loop); and changing `groups` to `[platform-admins]` sent exactly one update and changed **no**
membership, because Keycloak's user PUT ignores the field. The description said "create/update" and
now says create-only. Membership changes after create belong to group-membership resources.

## 2026-11-16 — 0.10.0: Keycloak's own keys in a map survive an update; group attributes are lists

**Partial fields.** Keycloak fills some maps with keys the CR does not declare, and an update sent each
map whole. Seven update verbs now declare those maps as `partialFields`, so the controller merges the
CR's keys over what Keycloak holds instead of replacing the map: realm `attributes`; client
`attributes` and `authenticationFlowBindingOverrides`; client scope `attributes`; group `attributes`
and `clientRoles`; and the `config` of identity-provider mappers, protocol mappers and required
actions. `KeycloakIdentityProvider` is left out: its `config` carries `clientSecret`, which Keycloak
returns masked, and a CR without `clientSecretRef` would replay the mask as the secret
(oasgen-provider #739).

Measured on a disposable GKE cluster through the installer (Keycloak 26, krateo-keycloak-realm 0.5.3),
with a free-form probe key seeded into every map through the Admin API, then a spec change through the
installer, and Keycloak read before and after:

| | oasgen-provider 0.74.0, no partial fields | oasgen-provider 0.77.0, this release |
|---|---|---|
| realm `attributes` | probe and `realmReusableOtpCode` **deleted** (seven `ciba*`/`oauth2Device*`/`par*` defaults regenerated by Keycloak) | **all 15 keys kept**, probe included |
| client `attributes` | nothing deleted: Keycloak's client update keeps omitted keys | nothing deleted |
| group `attributes` | not measurable (the type bug below refused the change) | the CR's key added, existing keys kept |

No value in any declared map came back masked. Every key seeded through the Admin API, including
names no schema declares, was returned by the read.

**Floors: oasgen-provider and oasgen-provider-crd >= 0.77.0, both, and in that order.** On an older
RestDefinition CRD the field is pruned at admission and the RD stays Ready, so the release is a silent
no-op: measured, all 13 stored RDs without the field after a clean upgrade. And installing this release
first and the CRD later does not repair it: helm's three-way diff does not re-send a field the cluster
pruned, so the RDs stay without it until a later chart change touches those lines (measured; a rollback
and re-upgrade restored it). 0.77.0 rather than 0.76.0 because from 0.76.0 a lost create response on a
kind with an `observeApiRef` stuck at `CreateOutcomeUnknown` until a person cleared it; 0.77.0
re-checks it on the next pass, so nothing needs doing by hand. Of this chart's two such kinds,
`KeycloakAuthenticationExecution` creates and was exposed; `KeycloakServiceAccountRoleMapping`, as the
realm chart deploys it, does not: its service-account user already exists, so it reconciles through
an update (measured) and never takes the create path.

**Group attributes are lists of strings.** The bundled group OpenAPI typed each attribute value as a
string, while Keycloak holds `Map<String, List<String>>`, so the generated `KeycloakGroup` CRD refused
every group attribute the realm chart sent (`spec.attributes.pf in body must be of type string`). It went
unnoticed because the default groups carry none. Now typed as Keycloak types it; measured, a group
attribute `pf: ["077"]` reaches Keycloak. CI now compares every bundled asset with Keycloak's own
OpenAPI (`hack/check-assets-vs-upstream.py`: 13 assets, 170 shared properties; the realm's
`smtpServer`, typed for validation, is the one listed difference), so a drift like this fails the PR.

## 2026-11-15 — 0.9.2: the Remember me session timeouts are declared

KeycloakRealm declared `rememberMe` but not `ssoSessionIdleTimeoutRememberMe` and
`ssoSessionMaxLifespanRememberMe`, so the CRD pruned them and a Remember me session could only use the
ordinary SSO timeouts. Both are now declared (int32; 0 = use the ordinary timeouts), as in Keycloak's
RealmRepresentation. krateo-keycloak-realm 0.5.3 renders them and requires this release. Measured on a
disposable GKE cluster (oasgen-provider 0.71.0, Keycloak 26.6.3): set to 28800 / 36000 they reach Keycloak
with one realm PUT and no further PUT; with 0.9.1's CRD the same values are pruned from the stored CR
while it stays Ready (the reason the realm chart pins this release). No other change.

## 2026-11-14 — 0.9.1: oasgen-provider floor 0.67.0

Raises `krateo.io/requires-oasgen-provider` to `>= 0.67.0`; nothing else changes. On oasgen-provider
0.66.0 (now retracted) a `KeycloakUserProfile` whose realm does not exist at its first observe, which
is every fresh krateo-keycloak-realm install because the realm and its profile are created together,
re-queued about 5 times a second and never turned Ready, even after the realm existed, until its
controller restarted (oasgen-provider #674; 0.65.0 backed off and recovered). 0.67.0 fixes it and keeps
0.66.0's keyed comparison of `protocolMappers`. Verified on a disposable GKE cluster with Keycloak 26.6.3,
each arm on a userprofile controller running rest-dynamic-controller 0.67.0 from start to end (pod
restart count and start time unchanged): a profile on a missing realm logged 2 "create not requested"
lines in 13 minutes instead of about 295 a minute, and turned Available about 6 minutes after the
realm was created, without a restart. krateo-keycloak-realm installed fresh on a realm that did not
exist yet hit the race (the profile's first observe in the same second as the realm's create) and every
object was Ready within 7 minutes, `krateo-ide` with no update. An orphaned `*Configuration` CRD
(foreign owner annotation, stale schema) is adopted in place, same UID, schema replaced.

## 2026-11-14 — 0.9.0: a client's protocol mappers are matched by name

Keycloak returns a client's protocol mappers in its own order: stable for one object across reads, PUTs
and restarts, but neither the declared order nor the same between objects. The comparison was
positional, so a client whose mappers came back reordered was re-PUT on every resync until
`DriftNotConverging` latched (krateo-ide's MCP client is one). `KeycloakClient.protocolMappers` is now
declared a list-map keyed by `name` (`name` required), which oasgen-provider 0.66.0 carries into the CRD
and uses to match entries by key. Floor raised to oasgen-provider >= 0.66.0.
Proven on a disposable GKE cluster (oasgen-provider 0.66.0, Keycloak 26.6.3): under the 0.8.1 CRD a
five-mapper client served as `[m5, m4, groups, mcp-audience, m3]` was PUT four times in ten minutes; the
upgrade to this chart regenerated the CRD from the changed asset alone (RestDefinition generation
unchanged, controller not restarted) and the same client took no further PUT. Clients created under
0.8.1 kept working. Mapper removal was measured through Helm and server-side apply, and Keycloak's PUT
was measured directly: a present list is authoritative, `[]` removes all, absent keeps all
([api.md](api.md#keycloakclientprotocolmappers) has the table and the SSA empty-list caveat).

## 2026-11-13 — status fields audited against a live Keycloak (CI)

rest-dynamic-controller skips a declared status field the server does not return without any error, so
a field that can never populate looks like a working one on a Ready CR (found in another KOG: a Nova
field gated behind a microversion). `hack/audit-status-fields-live.py` reads every non-delegated kind's
`additionalStatusFields` and get/findby paths from the rendered RestDefinitions, creates one object per
kind and checks each field in the get response and the findby item. Against Keycloak 26.6.3 all ten
are returned, except `KeycloakUserProfile.unmanagedAttributePolicy`, which Keycloak omits until a
policy is set (measured: absent unset, `ADMIN_VIEW` once set) and is documented as conditional. It runs
in CI (`status-fields`, a throwaway Keycloak container), so a Keycloak bump that drops a field fails a
check instead of going quiet. Delegated kinds compose their status in RESTActions and stay covered by
`tests/delegation`.
Hardened after a review by aruba-provider-kog: every field gets one verdict (`ok`, `ABSENT`, `NOT-MEASURED`
for a failed question such as a non-2xx get or an unresolved path parameter, `cond`, or `STALE` for an
exemption that no longer holds), findby reports `NOT-CHECKED(<reason>)` rather than a silent skip, the
run prints its denominator and fails on zero fields or a kind without a fixture, kinds are reconciled
before anything is created, and teardown runs in `finally`. `--selftest` drives each verdict offline.

## 2026-11-13 — 0.8.1: the token endpoint follows `keycloak.baseUrl`

`auth.externalSecret.tokenEndpoint` defaults to empty, meaning `<keycloak.baseUrl>/realms/master/protocol/openid-connect/token`.
It was a separate hard-coded default (`keycloak-service.keycloak-system…`), so an install that pointed
`keycloak.baseUrl` at another namespace, or at a Keycloak served under a path prefix (keycloak chart
0.4.0 `keycloak.http.relativePath`, needed by path-mode gateways), had to set the same Keycloak twice,
and a mismatch minted the token at a different or non-existent Keycloak. An explicit value still wins.
With the default `baseUrl` the derived URL is the previous default byte for byte, and releases upgraded
with `--reuse-values` keep their explicit value. CI gate `hack/check-token-endpoint.py`.

## 2026-11-13 — 0.8.0: KeycloakServiceAccountRoleMapping; client URI and scope lists are sets

**`KeycloakServiceAccountRoleMapping`**: the exact set of one client's roles held by another client's
service-account user (first user: identity-lifecycle's client, `realm-management` `manage-users`,
`view-users`, `query-groups`). Keycloak addresses both by UUID only and has no set-replace call, so the
lifecycle is delegated to Snowplow RESTActions (observe / apply / delete), like
`KeycloakAuthenticationExecution`. Proven in-cluster on a disposable GKE cluster with the pinned stack
(oasgen-provider 0.63.1 with the rdc snowplow/authn wiring, snowplow 1.12.67, authn 0.46.0, Keycloak
26.6.3): the CRD generates with typed status (`roles` a string array), the role set converges, a role
added and a role removed by hand are both reverted at the next reconcile, and deleting the CR (deletion
policy `delete`) removes every held role and releases the finalizer once the get reads an empty list.
After an update, Ready is set at once and `status.roles` catches up at the next observe. Offline: 30
assertions in `tests/delegation`; live replay: `hack/validate-serviceaccountrolemapping-live.sh` (17).

**Client lists are sets.** `KeycloakClient` `redirectUris`, `webOrigins`, `defaultClientScopes` and
`optionalClientScopes` are `uniqueItems`: Keycloak keeps them as sets and returns them in its own order
(measured: declared `[localhost, 127.0.0.1, zzz]` came back `[127.0.0.1, zzz, localhost]`), so a client
with two or more redirect URIs was re-PUT on every reconcile until the controller latched
`DriftNotConverging`. With sets (oasgen-provider >= 0.62.0 compares them as sets) the same client
converges with no update. Still order-sensitive: `protocolMappers`, a list of objects, which the
controller compares by position; a client declaring two or more mappers latches `DriftNotConverging`
(the client itself is correct in Keycloak). That needs keyed comparison in rest-dynamic-controller.

## 2026-11-12 — 0.7.3: upgrades with `helm upgrade --reuse-values` from 0.6.0 work

`helm upgrade --reuse-values` from 0.6.0 to 0.7.0, 0.7.1 or 0.7.2 failed: `nil pointer evaluating
interface {}.enabled` on `restDefinitions.userprofile`. Reuse-values upgrades with the previous
release's values, which have no `userprofile`, and does not apply the new chart's values.yaml defaults
(measured on GKE, and with a server-side dry-run against a 0.6.0 release). Every template now reads
`restDefinitions` through one helper that merges the chart's defaults under the supplied values. The
defaults are in `files/restDefinitions.defaults.yaml`, because Helm does not expose values.yaml through
`.Files`; CI keeps that file equal to values.yaml's `restDefinitions`. A fresh install renders
byte-identically to 0.7.2. CI gate `hack/check-reuse-values.py` renders the chart under the values of
0.6.0, 0.7.0, 0.7.1 and 0.7.2 and requires the same objects as a default render.

## 2026-11-12 — 0.7.2: restDefinitions.user is declared in the schema

`values.schema.json` never declared `restDefinitions.user` (missing from 0.6.0 to 0.7.1) although
`values.yaml` sets it, so the key could not be set through a Krateo Composition or an installer that
mirrors the schema: it was pruned silently and the default always applied. It is declared now, and CI
gate `hack/check-values-declared.py` requires every `values.yaml` key to be declared. No asset,
template or default changed: a schema widening only. Found by the installer session.

## 2026-11-12 — 0.7.1: the realm's event types and listeners are sets

`enabledEventTypes` and `eventsListeners` declare `uniqueItems: true` (the CRD gets
`x-kubernetes-list-type: set`). With oasgen-provider 0.62.0, which compares such arrays as sets, the
order Keycloak returns them in is no longer drift. Requires oasgen-provider >= 0.62.0 (Chart.yaml
annotation `krateo.io/requires-oasgen-provider`). Descriptions and docs no longer name
`SEND_EXECUTE_ACTIONS`/`SEND_ERROR`, which are not Keycloak EventTypes.

Measured on GKE (Keycloak 26.6.3), one realm with 23 event types, before and after on the same cluster:
oasgen-provider 0.61.0 PUT it at 15:16:30, 15:19:30, 15:22:30 and 15:25:30Z and then stopped ("Drift is
not converging"), leaving it `Ready=False`; 0.62.0 issued no PUT over 15 minutes, observing it up to
date every 3 minutes, `Ready=True`. Positive control: removing `LOGIN` from the live realm produced
exactly one restoring PUT, then up to date again.

## 2026-11-12 — 0.7.0: KeycloakUserProfile

New kind `KeycloakUserProfile`: a realm's declarative user profile (attributes, who may view and
edit them, validators). Keycloak keeps one profile per realm and it always exists, so the kind has
no create and no delete verb: it adopts the realm's profile and replaces it whole (PUT) when it
differs, and deleting the CR leaves the profile in place. The schema is typed (the built-in
validators are modelled), so the generated CRD validates it. See [usage](usage.md).

Measured on a disposable GKE cluster against the shipped stack (Keycloak 26.6.3, keycloak-operator
and keycloak 0.2.6, oasgen-provider 0.60.0), with krateo-keycloak-realm rendering the CR:

- Before the profile existed (realm chart 0.2.0), an attribute set at user creation was dropped.
- After it: the profile was applied with one PUT. The live profile equals the CR except
  `multivalued: false`, Keycloak's default, which is not treated as drift: no further PUT over the
  following minutes, only periodic up-to-date observations.
- Users created before the profile existed (one with only a username, one with every field) both
  accepted admin updates afterwards (204).
- An attribute with view/edit `[admin]`: kept on create, found by `?q=<name>:<value>`, a 37-character
  value refused by `length.max: 36` (400). The user does not see it in the account API, and the
  account API refuses the user's attempt to set it (400 `error-user-attribute-read-only`) while a
  normal profile change by the same user succeeds (204).
- An out-of-band profile edit removing the attribute was reverted by the controller after 63 s. A
  user's stored value survived the window in which the attribute was undeclared.
- Removing the CR (the realm chart with `userProfile.enabled: false`, orphan policy) left the realm's
  profile unchanged; re-enabling adopted it again.

The first reconcile can log one `Cannot observe` (the token Secret is forbidden) when the CR and its
Configuration are created in the same apply: the RBAC that the Configuration grants arrives a moment
later, and the next reconcile succeeds (1.4 s in the run above).

Also: `hack/gen_oas_assets.py` is removed. It no longer reproduced four of the shipped assets, so
running it would have reverted released fixes; the assets are hand-curated and are the source of
truth. README and docs/release.md now describe the current CI and release workflow.

## 2026-11-11 — 0.6.0: realm mail (password and XOAUTH2), events and action-link lifetimes

`KeycloakRealm` gains `smtpServer` (password or token authentication), the user-event settings, the
action-token lifespans and `verifyEmail`, for an access-request flow where an administrator approves a
request and Keycloak emails the new user a set-password link. SMTP credentials are Secret-sourced
(`smtpCredentialsRef`: the user, and the password or the OAuth2 client secret) and never stored in the
CR. Validated live on disposable GKE clusters against the shipped stack (keycloak-operator 0.2.4,
keycloak 0.2.5 on CloudNativePG, Keycloak 26.6.3) on rest-dynamic-controller 0.56.0 and 0.59.0, with
Keycloak admin events as the oracle for every write: a real set-password email delivered through
SMTP AUTH (password) and through `AUTH XOAUTH2` (token, against a stub that accepts only the token it
issued); the masked secret is never compared and an idle realm is never re-PUT; a masked value echoed
back never overwrites the stored one; wrong credentials fail the send with HTTP 500. Two findings went
into the docs and upstream: Keycloak stores no `SEND_EXECUTE_ACTIONS`/`SEND_ERROR` events for an
admin-triggered email, and an in-place change of a referenced Secret never reaches the vendor
(rotate by repointing to a new Secret; oasgen-provider#598).

## 2026-08-11 — Documentation Standard adoption

The repo adopts the Krateo Documentation Standard (OKF): the invariant docs bundle
(`docs/{index,overview,usage,configuration,api,examples,release,log}.md` + `llms.txt`),
a runnable `examples/sso-realm`, and the shared `lint-docs` check wired into a new
`lint.yaml`. The pre-existing `docs/ARCHITECTURE.md` and `docs/images/README.md` gain
OKF frontmatter (type `Architecture`). `README.md` is restructured into the six
standard sections.

## 2026-07-21 — KeycloakAuthenticationExecution proven in-cluster

The full step-up ladder reconciled on a kind cluster with published images only
(oasgen-provider 0.12.0 / rdc 0.11.0 / snowplow 1.7.13 cache-off / authn 0.24.0):
`kubectl apply` of the 9-CR sample converged the complete LoA ladder into a live
Keycloak 26 — exact order by declarative priority, requirements, both LoA configs —
and `kubectl delete` held the finalizer until the single-execution GET returned a real
404. Mid-run Keycloak restarted and wiped its dev database; the controllers rebuilt the
whole ladder from the CRs unattended. `KeycloakAuthenticationFlow` and `KeycloakRealm`
also reconciled Ready=True in the same e2e.

## Earlier — the seven core resources validated

`KeycloakRealm`, `KeycloakGroup`, `KeycloakClientScope`, `KeycloakClient`,
`KeycloakProtocolMapper`, `KeycloakIdentityProvider` and
`KeycloakIdentityProviderMapper` each reconciled into a real Keycloak 26.6.3 on a live
kind cluster (`oasgen-provider` 0.10 + rest-dynamic-controller). Findings baked into
the design:

- Path params must be declared at the **operation** level in the OAS asset
  (oasgen-provider ignores path-item-level parameters).
- The server-generated `{id}` must be excluded from spec and sourced from `status.id`
  via `requestFieldMapping`.
- Nested array fields (`protocolMappers`) need a named `$ref`, not an inline object.
- `KeycloakIdentityProviderMapper` needs both `alias` (path) **and**
  `identityProviderAlias` (body) — omitting the latter yields a misleading
  `409 Duplicate resource`.
- The ESO admin-token path works end-to-end on ESO ≥ 0.19: the client-secret Secret
  must carry the `external-secrets.io/type: webhook` label, the `krateo-kog` client
  needs `serviceAccountsEnabled` + admin rights, the `ExternalSecret` is
  `external-secrets.io/v1`, and `result.jsonPath: "$"` returns the whole token
  response so the template can pick `.access_token`.

## Design origin

Two deliverables bring Keycloak into the platform: this **configuration** KOG and the
sibling **lifecycle** blueprint that wraps the official Keycloak Operator. The
operator-for-lifecycle / KOG-for-config split avoids two systems owning the same
realm; the Bitnami chart was intentionally avoided (deprecated Aug 2025). Every OAS
asset patches in a `bearer` `securityScheme` (Keycloak's published OAS omits one), so
no auth-bridge proxy is required.
