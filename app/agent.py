from enum import StrEnum
import json
import re
import uuid
from app.language import Intent, Extraction
from app.policy import country, fields_error, name_key
class State(StrEnum):
    IDLE='IDLE'
    COLLECTING_NAME='COLLECTING_NAME'
    COLLECTING_COUNTRY='COLLECTING_COUNTRY'
    COLLECTING_TAX_ID='COLLECTING_TAX_ID'
    CHECKING_DUPLICATE='CHECKING_DUPLICATE'
    VALIDATING='VALIDATING'
    AWAITING_APPROVAL='AWAITING_APPROVAL'
    COMPLETED='COMPLETED'
    CANCELLED='CANCELLED'
class SupplierAgent:
    def __init__(self,interpreter,gateway):
        self.interpreter=interpreter; self.gateway=gateway
        self.state=State.IDLE; self.draft={}; self.pending=None
        self.trace=[]; self.trace_id=''; self.uncertain=False
    def event(self,layer,detail): self.trace.append({'layer':layer,'detail':detail})
    def move(self,state):
        self.state=state; self.event('Policy',state.value)
    def clear(self,state):
        self.draft={}; self.pending=None; self.uncertain=False; self.move(state)
    def tool(self,name,args):
        self.event('MCP',name)
        result=self.gateway.call(name,args,self.trace_id)
        self.event('FastAPI → SQLite','Request succeeded')
        return result
    def handle(self,text):
        self.trace_id=str(uuid.uuid4()); self.trace=[]
        self.event('Streamlit','Message received')
        text=text.strip()
        if not text or len(text)>2000: return 'Please enter a request of 1–2,000 characters.'
        low=text.lower().strip(' .!')
        # Consent and cancellation are application controls, not model-authorized writes.
        if low in ('cancel','never mind','nevermind','start over'):
            e=Extraction(intent=Intent.CANCEL)
        elif low in ('approve','i approve','yes, approve'):
            e=Extraction(intent=Intent.APPROVE)
        elif re.search(r'\b(delete|deactivate|block)\b|change\s+(?:the\s+)?status',low) or (re.search(r'\b(update|edit)\b',low) and re.search(r'\b[A-Z]{2}\d+\b',text,re.I)):
            e=Extraction(intent=Intent.UNSUPPORTED_ACTION)
        elif low in ('none','none of the above','neither','not any of them','another country','other country') or low in ('germany','south africa'):
            e=Extraction(intent=Intent.PROVIDE_COUNTRY,country=text)
        else:
            try:
                e=self.interpreter.parse(text,self.state.value,self.draft.copy())
                self.event('GPT / LiteLLM','Structured intent: '+e.intent.value)
            except Exception:
                self.event('GPT / LiteLLM','Unavailable or invalid response')
                return 'Language service unavailable or response invalid. Your draft is preserved. Please retry.'
        try: return self.dispatch(e,low)
        except Exception:
            self.event('Service','Request failed')
            if self.state==State.AWAITING_APPROVAL and self.uncertain:
                return 'The create result could not be confirmed. Approve again to safely reconcile the same supplier, or check its status before cancelling.'
            if self.draft and self.state in (State.CHECKING_DUPLICATE,State.VALIDATING): self.move(State.COLLECTING_TAX_ID)
            return 'Supplier service temporarily unavailable. Your draft is preserved; retry your request. No create was requested.'
    def dispatch(self,e,raw=''):
        i=e.intent
        if i==Intent.CANCEL:
            uncertain=self.uncertain
            self.clear(State.CANCELLED)
            return 'Draft cleared. The earlier create result is unconfirmed; cancellation does not undo a committed record. Search for the supplier before onboarding again.' if uncertain else 'Onboarding cancelled. The draft has been cleared.'
        if i==Intent.UNSUPPORTED_ACTION:
            return 'I cannot delete, update, deactivate, block or change the status of existing suppliers. I can list, search, check status and onboard suppliers.'
        if i==Intent.APPROVE:
            if raw not in ('approve','i approve','yes, approve'):
                return 'To authorize creation, type Approve or use the approval card.'
            if self.state!=State.AWAITING_APPROVAL or not self.pending: return 'There is no supplier awaiting approval.'
            self.uncertain=True
            result=self.tool('create_supplier',self.pending.copy())
            self.uncertain=False
            if not result.get('ok'):
                self.clear(State.CANCELLED); return result.get('reason','Creation refused.')
            sid=result['supplier']['id']; self.clear(State.COMPLETED)
            return f'Supplier {sid} is registered.'
        if i in (Intent.LIST,Intent.SEARCH,Intent.STATUS):
            if e.country and not country(e.country): return 'Only Kenya, Uganda and Tanzania are supported.'
            if i==Intent.LIST:
                if e.status and e.status.lower() not in ('active','inactive'): return 'Status filters are active or inactive.'
                result=self.tool('list_suppliers',{'country':country(e.country),'status':e.status.lower() if e.status else None})
            elif i==Intent.SEARCH:
                if not e.name or not e.name.strip(): return 'Which supplier name should I search for?'
                result=self.tool('search_supplier',{'name':e.name.strip()})
            else:
                if not e.supplier_id or not re.fullmatch(r'(KE|UG|TZ)\d{3,8}',e.supplier_id.upper()): return 'Provide a supplier ID such as KE001.'
                result=self.tool('get_supplier_status',{'id':e.supplier_id.upper()})
            items=result.get('suppliers') if 'suppliers' in result else [result.get('supplier')]
            items=[x for x in items if x]
            answer='No matching suppliers found.' if not items else '\n'.join(f"• {x['id']} | {x['name']} | {x['country']} | {x['status']}" for x in items)
            if self.draft: answer+='\n\nYour onboarding draft is preserved.'
            return answer
        if i==Intent.ASK_ABOUT_PENDING:
            if self.pending: return 'Approval authorizes one supplier creation with these details: '+json.dumps(self.pending)+'. Type Approve to create, correct a field, or Cancel.'
            return 'No creation is awaiting approval. Current draft: '+json.dumps(self.draft)
        if e.country and not country(e.country):
            self.clear(State.CANCELLED)
            return 'I cannot continue onboarding for that country. Only suppliers registered in Kenya, Uganda and Tanzania are supported.'
        if i==Intent.GENERAL_QUESTION:
            return 'I can list, search, check supplier status or onboard a supplier in Kenya, Uganda or Tanzania. For pending creation, type Approve, ask about details, correct a field or Cancel.'
        if self.uncertain:
            return 'Resolve the unconfirmed create first: Approve reconciles the same supplier; Cancel clears the draft without undoing any committed record.'
        if i==Intent.START_ONBOARDING:
            self.clear(State.IDLE)
        elif i in (Intent.PROVIDE_NAME,Intent.PROVIDE_COUNTRY,Intent.PROVIDE_TAX_ID,Intent.CORRECT_FIELD):
            if self.state in (State.IDLE,State.COMPLETED,State.CANCELLED): return 'Start with “onboard” and a company name.'
        else: return 'Please clarify your request.'
        supplied={k:getattr(e,k) for k in ('name','country','tax_id') if getattr(e,k) is not None}
        if not supplied and i!=Intent.START_ONBOARDING: return 'Please supply the field you want to set.'
        self.pending=None; self.uncertain=False
        for k,v in supplied.items(): self.draft[k]=country(v) if k=='country' else v.strip()
        return self.advance()
    def advance(self):
        for field,state,prompt in [('name',State.COLLECTING_NAME,'What is the company name?'),('country',State.COLLECTING_COUNTRY,'Which country is the supplier registered in: Kenya, Uganda or Tanzania?'),('tax_id',State.COLLECTING_TAX_ID,'What is the supplier tax ID?')]:
            if not self.draft.get(field): self.move(state); return prompt
        error=fields_error(self.draft)
        if error:
            self.move(State.COLLECTING_NAME if 'name' in error.lower() else State.COLLECTING_TAX_ID)
            return error+' Please correct that field.'
        self.move(State.CHECKING_DUPLICATE)
        candidates=self.tool('search_supplier',{'name':self.draft['name']})['suppliers']
        if any(name_key(x['name'])==name_key(self.draft['name']) for x in candidates):
            self.clear(State.CANCELLED); return 'A supplier with that company name already exists. No supplier was created.'
        self.move(State.VALIDATING)
        result=self.tool('validate_supplier',self.draft.copy())
        if not result.get('valid'):
            reason=result.get('reason','Validation failed.'); self.clear(State.CANCELLED); return reason
        self.pending=self.draft.copy(); self.move(State.AWAITING_APPROVAL)
        return 'Supplier validated. Review the approval card, then Approve or Cancel. No supplier has been created yet.'
