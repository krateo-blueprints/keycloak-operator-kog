#!/usr/bin/env python3
"""Every RestDefinition configurationFields entry must name a parameter its asset DECLARES, on every action it applies to.

oasgen-provider SILENTLY SKIPS a configurationFields entry whose parameter the OAS does not declare
(configuration_builder.go: `continue` on findParameterInOAS error, no log; oasgen-provider #828). The generated
*Configuration CRD then has no property for it, the value has nowhere to land, and the failure surfaces layers away.
This gate makes that a CI failure here instead. Covers `fromRestDefinition.actions: ["*"]` too.
"""
import glob, os, re, sys
import yaml

CHART = "helm/keycloak-config-kog"
errors = []; checked = 0
for rd_path in sorted(glob.glob(os.path.join(CHART, "templates", "rd-*.yaml"))):
    raw = open(rd_path).read()
    if "configurationFields" not in raw:
        continue
    # strip Helm template lines so the RD body parses as YAML
    body = "\n".join(l for l in raw.splitlines() if not l.strip().startswith("{{"))
    body = re.sub(r"\{\{[^}]*\}\}", "X", body)
    rd = yaml.safe_load(body)
    res = rd["spec"]["resource"]
    asset = os.path.join(CHART, "assets", os.path.basename(rd_path)[3:])  # rd-user.yaml -> user.yaml
    oas = yaml.safe_load(open(asset))
    verbs = {v["action"]: v for v in res.get("verbsDescription", [])}
    for cf in res.get("configurationFields", []):
        name, loc = cf["fromOpenAPI"]["name"], cf["fromOpenAPI"]["in"]
        acts = cf["fromRestDefinition"]["actions"]
        acts = list(verbs) if acts == ["*"] else acts
        for a in acts:
            checked += 1
            v = verbs.get(a)
            if not v:
                errors.append(f"{rd_path}: configurationFields {loc}/{name} names action {a!r}, which verbsDescription does not declare"); continue
            item = oas["paths"].get(v["path"], {})
            params = list(item.get("parameters", [])) + list(item.get(v["method"].lower(), {}).get("parameters", []))
            if not any(p.get("name") == name and p.get("in") == loc for p in params):
                errors.append(f"{rd_path}: configurationFields {loc}/{name} for {a} ({v['method']} {v['path']}) is NOT declared in {asset} -- oasgen would skip it silently")
print(f"Checked {checked} configurationFields action binding(s) against their assets.")
for e in errors: print(f"::error::{e}")
sys.exit(1 if errors else 0)
