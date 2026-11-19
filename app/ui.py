import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv()
import streamlit as st
from app.agent import SupplierAgent, State
from app.language import Interpreter
from app.gateway import Gateway
st.set_page_config(page_title='Supplier Services',page_icon='▣',layout='centered')
st.markdown("""<style>
html,body,[class*="css"],.stApp {font-family:Arial,sans-serif;}
.stApp {background:#f8fafc;color:#14243a;}
p,li,input,textarea,button {font-size:17px!important;}
.block-container {max-width:900px;padding-top:2rem;}
</style>""",unsafe_allow_html=True)
st.title('Supplier Services')
st.caption('Kenya · Uganda · Tanzania')
if 'agent' not in st.session_state:
    st.session_state.agent=SupplierAgent(Interpreter(),Gateway())
    st.session_state.messages=[]
a=st.session_state.agent
for role,text in st.session_state.messages:
    with st.chat_message(role): st.markdown(text)
def submit(text):
    answer=a.handle(text)
    st.session_state.messages.extend([('user',text),('assistant',answer)])
    st.rerun()
if a.state==State.AWAITING_APPROVAL and a.pending:
    with st.container(border=True):
        st.subheader('Approval required')
        st.text('Company: '+a.pending['name'])
        st.text('Country: '+a.pending['country'])
        st.text('Tax ID: '+a.pending['tax_id'])
        if a.uncertain: st.warning('Previous create result is unconfirmed. Approve reconciles the same supplier safely.')
        c1,c2=st.columns(2)
        if c1.button('Approve',type='primary',use_container_width=True): submit('Approve')
        if c2.button('Cancel',use_container_width=True): submit('Cancel')
if a.trace:
    with st.expander('Architecture trace · '+a.state.value):
        st.caption('Trace ID: '+a.trace_id)
        st.table(a.trace)
if text:=st.chat_input('Ask about suppliers or start onboarding',max_chars=2000): submit(text)
