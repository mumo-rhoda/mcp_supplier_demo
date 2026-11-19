import pytest
from app.agent import SupplierAgent, State
from app.language import Extraction, Intent
class Parser:
    def __init__(self): self.next=None
    def parse(self,*args):
        if isinstance(self.next,Exception): raise self.next
        return self.next
class Tools:
    def __init__(self): self.calls=[]; self.fail=None; self.duplicate=False
    def call(self,name,args,trace):
        self.calls.append((name,args.copy(),trace))
        if self.fail: raise self.fail
        if name=='search_supplier': return {'suppliers':[]}
        if name=='validate_supplier': return {'valid':not self.duplicate,'reason':'Duplicate tax ID'}
        if name=='create_supplier': return {'ok':True,'supplier':{'id':'KE009'}}
        return {'suppliers':[]}
@pytest.fixture
def a(): return SupplierAgent(Parser(),Tools())
def send(a,intent,**fields):
    a.interpreter.next=Extraction.model_validate_json(__import__('json').dumps({'intent':intent,**fields}))
    return a.handle('natural language request')
def ready(a):
    send(a,'START_ONBOARDING',name='New Supplier',country='Kenya',tax_id='TAX123')
    assert a.state==State.AWAITING_APPROVAL
@pytest.mark.parametrize('value',['Germany','South Africa','none of the above','UK'])
def test_boundary(a,value):
    send(a,'START_ONBOARDING',country=value)
    assert a.state==State.CANCELLED and not a.gateway.calls
@pytest.mark.parametrize('text',['delete KE001','deactivate KE001','block supplier','change status KE001','update KE001'])
def test_unsupported(a,text):
    a.handle(text); assert not a.gateway.calls

def test_multiturn_correction_and_read(a):
    send(a,'START_ONBOARDING',name='New Supplier'); assert a.state==State.COLLECTING_COUNTRY
    send(a,'PROVIDE_COUNTRY',country='Kenya'); assert a.state==State.COLLECTING_TAX_ID
    send(a,'CORRECT_FIELD',country='Uganda'); assert a.draft['country']=='Uganda'
    before=a.draft.copy(); send(a,'LIST',country='Kenya'); assert a.draft==before
    send(a,'PROVIDE_TAX_ID',tax_id='ABC123'); assert a.state==State.AWAITING_APPROVAL
    before=a.pending.copy(); send(a,'ASK_ABOUT_PENDING'); assert a.pending==before
    send(a,'CORRECT_FIELD',name='New Name'); assert a.pending['name']=='New Name'
    assert not any(x[0]=='create_supplier' for x in a.gateway.calls)
    a.handle('Approve'); assert a.state==State.COMPLETED
    a.handle('Approve'); assert sum(x[0]=='create_supplier' for x in a.gateway.calls)==1

def test_approval_cannot_be_model_invented(a):
    ready(a); send(a,'APPROVE'); assert not any(x[0]=='create_supplier' for x in a.gateway.calls)

def test_cancel(a):
    ready(a); a.handle('start over'); assert a.state==State.CANCELLED and not a.draft and not a.pending

def test_duplicate_tax(a):
    a.gateway.duplicate=True
    send(a,'START_ONBOARDING',name='New Supplier',country='Kenya',tax_id='TAX123')
    assert a.state==State.CANCELLED

def test_duplicate_name(a):
    old=a.gateway.call
    a.gateway.call=lambda n,d,t: {'suppliers':[{'name':'New Supplier'}]} if n=='search_supplier' else old(n,d,t)
    send(a,'START_ONBOARDING',name='New Supplier',country='Kenya',tax_id='TAX123')
    assert a.state==State.CANCELLED

def test_malformed(a):
    send(a,'START_ONBOARDING',name='New Supplier',country='Kenya',tax_id='!')
    assert not a.gateway.calls
    a.interpreter.next=ValueError('secret error')
    assert 'secret' not in a.handle('bad response')

def test_failure_and_uncertain_write(a):
    ready(a); a.gateway.fail=RuntimeError('database password')
    result=a.handle('Approve')
    assert 'confirmed' in result and 'password' not in result
    assert a.pending and a.uncertain
    a.gateway.fail=None; a.handle('Approve'); assert a.state==State.COMPLETED

def test_failure_preserves_pending_for_read(a):
    ready(a); a.gateway.fail=RuntimeError()
    before=a.pending.copy(); send(a,'LIST')
    assert a.pending==before and a.state==State.AWAITING_APPROVAL

def test_missing_fields(a):
    send(a,'START_ONBOARDING'); assert a.state==State.COLLECTING_NAME
    send(a,'PROVIDE_NAME',name='Example Ltd'); assert a.state==State.COLLECTING_COUNTRY
    assert not a.gateway.calls
