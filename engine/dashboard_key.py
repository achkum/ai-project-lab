"""Owner-local access-key display. Never send this output to public logs."""
import json
from pathlib import Path

if __name__=='__main__':
    profile=json.loads(Path('config/profile.local.json').read_text())
    key=json.loads((Path(profile['runtime_root'])/'dashboard-access.json').read_text())
    print('Private dashboard key (do not share or commit):')
    print(key['token'])
