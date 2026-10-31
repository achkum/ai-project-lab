"""Resolve required quality tier without silent fallback. Makes no model calls."""
class SetupRequired(RuntimeError):
    pass

def required_tier(task, *, ambiguous=False, repair_attempts=0):
    if ambiguous or repair_attempts >= 2:
        return "analysis"
    analysis = {"initial_analysis","prior_work","thesis_feasibility","venture_assessment",
                "architecture","final_substantive_review","security_sensitive_design"}
    implementation = {"approved_spec_implementation","routine_tests","routine_fixes","documentation"}
    economy = {"schema_checked_extraction","bounded_formatting"}
    deterministic = {"fetch","hash","schedule","count","schema_validate"}
    if task in analysis: return "analysis"
    if task in implementation: return "implementation"
    if task in economy: return "economy"
    if task in deterministic: return None
    raise ValueError("Unclassified task requires an explicit routing decision")

def resolve_model(policy, task, *, ambiguous=False, repair_attempts=0):
    tier = required_tier(task, ambiguous=ambiguous, repair_attempts=repair_attempts)
    if tier is None:
        return {"tier":"deterministic","model_id":None}
    model = policy.get("tiers",{}).get(tier,{}).get("model_id")
    if not isinstance(model,str) or not model.strip():
        raise SetupRequired("Bind a verified model to required tier: " + tier)
    for key in ("monthly_cap_sek","per_run_cap_sek"):
        cap = policy.get(key)
        if isinstance(cap,bool) or not isinstance(cap,(float,int)) or cap <= 0:
            raise SetupRequired("Paid execution is disabled until a positive cap is set: " + key)
    return {"tier":tier,"model_id":model}

