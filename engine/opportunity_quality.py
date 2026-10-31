"""Publication gate for evidence-led opportunity cards, not a demand scoring model."""
def validate_card(card):
    if card.get('quality_gate_version', 0) < 2:
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
