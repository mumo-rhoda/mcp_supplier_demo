from pathlib import Path
from streamlit.testing.v1 import AppTest
from app.agent import State

def test_minimal_ui_and_cancel():
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app/ui.py'),default_timeout=30).run()
    assert not app.exception
    assert app.title[0].value=='Supplier Services'
    a=app.session_state['agent']
    a.draft={'name':'Example Ltd','country':'Kenya','tax_id':'ABC123'}
    a.pending=a.draft.copy(); a.state=State.AWAITING_APPROVAL
    app.run()
    assert [b.label for b in app.button]==['Approve','Cancel']
    app.button[1].click().run()
    assert not app.exception
    assert a.state==State.CANCELLED and not a.pending
