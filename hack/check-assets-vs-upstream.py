#!/usr/bin/env python3
"""Every bundled OAS asset must type each property the way Keycloak's own OpenAPI does.

WHY: the assets under helm/keycloak-config-kog/assets/ are what oasgen-provider generates the CRDs from,
so a property typed differently from Keycloak's API produces a CRD that refuses (or silently reshapes)
what Keycloak actually holds. Measured 2026-11-16: assets/group.yaml typed GroupRepresentation.attributes
as a map of strings while Keycloak holds Map<String, List<String>>, so every group attribute the realm chart
sent failed admission ("spec.attributes.pf in body must be of type string"). It had gone unnoticed because
the default groups carry no attributes.

WHAT: for every schema an asset shares by name with hack/keycloak-openapi-full.yaml (Keycloak's OpenAPI,
vendored), compare each shared property's TYPE SHAPE ($ref resolved; map/array/scalar/object), and fail on
any difference not listed in INTENDED with its reason.
"""
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "helm/keycloak-config-kog/assets"
UPSTREAM = ROOT / "hack/keycloak-openapi-full.yaml"

# Deliberate differences: (asset file, schema, property) -> why it differs from upstream.
INTENDED = {
    ("realm.yaml", "RealmRepresentation", "smtpServer"):
        "typed as an object with declared properties so the realm chart's SMTP settings are validated; "
        "upstream declares a free map of strings",
}


def shape(s, schemas, depth=0):
    if depth > 8 or not isinstance(s, dict):
        return s
    if "$ref" in s:
        return shape(schemas.get(s["$ref"].split("/")[-1], {}), schemas, depth + 1)
    t = s.get("type")
    if t == "array":
        return ["array", shape(s.get("items", {}), schemas, depth + 1)]
    if t == "object" and "additionalProperties" in s and not s.get("properties"):
        ap = s["additionalProperties"]
        return ["map", shape(ap, schemas, depth + 1) if isinstance(ap, dict) else ap]
    if t == "object" or s.get("properties"):
        return "object"
    return t


def main():
    up = yaml.safe_load(UPSTREAM.read_text())["components"]["schemas"]
    failures, intended_seen, compared = [], set(), 0
    files = sorted(ASSETS.glob("*.yaml"))
    for f in files:
        schemas = (yaml.safe_load(f.read_text()).get("components") or {}).get("schemas") or {}
        for name, sch in schemas.items():
            if name not in up:
                continue
            for prop, ps in (sch.get("properties") or {}).items():
                ups = (up[name].get("properties") or {}).get(prop)
                if ups is None:
                    continue
                compared += 1
                a, b = shape(ps, schemas), shape(ups, up)
                if json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True):
                    continue
                key = (f.name, name, prop)
                if key in INTENDED:
                    intended_seen.add(key)
                    continue
                failures.append(f"{f.name}: {name}.{prop} is {a} here, {b} in Keycloak's OpenAPI")
    stale = sorted(set(INTENDED) - intended_seen)
    for k in stale:
        failures.append(f"INTENDED entry no longer differs (remove it): {k}")
    if compared == 0:
        failures.append("compared 0 properties: the asset or upstream paths are wrong, so this check proved nothing")
    print(f"{len(files)} assets, {compared} shared properties compared, {len(intended_seen)} intended difference(s)")
    for line in failures:
        print("::error::" + line)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
