"""Publication gate for evidence-led opportunity cards, not a demand scoring model."""
def validate_card(card):
    if card.get('quality_gate_version',0)>=3 and card.get('lane')=='Project':
        case=card.get('business_case',{})
        fields=('first_customer','repeat_use','who_pays_and_why','current_alternatives','proposed_difference','week_one','week_one_acceptance','next_90_days','first_customer_route','kill_test','data_access','costs','biggest_unknown')
        if not isinstance(case,dict) or any(not isinstance(case.get(k),str) or not case[k].strip() for k in fields):
            raise ValueError('Business opportunity needs a customer, repeat use, buying reason, first-week workflow and a testable business case')
    if card.get('quality_gate_version', 0) < 2:
        if card.get('lane') == 'Project':
            raise ValueError('New project publication requires evidence-led quality gate v2')
        return  # Existing thesis investigations retain their immutable scope.
    required=('buyer','customer_test','week_test','growth_path','baseline',
              'proposed_difference','risk','evidence_level')
    if any(not isinstance(card.get(k),str) or not card[k].strip() for k in required):
        raise ValueError('Opportunity needs a complete customer and validation case')
    sources=card.get('provenance',[])
    if not sources or any(not s.get('finding') or not s.get('url','').startswith('https://') for s in sources):
        raise ValueError('Opportunity needs attributable evidence')
    if type(card.get('auto_eligible')) is not bool:
        raise ValueError('Opportunity needs an explicit default-selection decision')
    if card.get('recommended') and not card['auto_eligible']:
        raise ValueError('Exploratory opportunity cannot be the default recommendation')
    if card['auto_eligible'] and not any(
        s.get('full_thread_reviewed') is True and s.get('resolution_status')=='unresolved'
        and s.get('published_at') and s.get('verified_at') and s.get('remaining_gap')
        for s in sources
    ):
        raise ValueError('Default selection requires reviewed, dated evidence of a remaining unresolved gap')
