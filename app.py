import json
import pandas as pd
import plotly.express as px
import streamlit as st
from src.models.graph_model import load_network, validate, fingerprint, ROOT
from src.models.objective import Objective
from src.algorithms.classical import brute_force, local_search, kernighan_lin
from src.algorithms.qaoa_solver import solve, circuit
from src.simulation.failures import scenario
from src.simulation.resilience import metrics
from src.visualization.network import network_figure
from src.experiments.metrics import gap, optimal_probability
from src.utils.export import bundle
from app_pages import PAGES
from src.ui.real_pages import REAL_PAGES, render_real_page

st.set_page_config(page_title='QuantumGrid Perú',page_icon='◈',layout='wide')
st.markdown('''<style>.stApp{background:#08111f}h1,h2,h3{letter-spacing:-.035em}h1{font-weight:750!important}
[data-testid="stSidebar"]{background:#0c1729} [data-testid="stMetric"]{background:#11213a;border:1px solid #24364e;border-radius:14px;padding:18px}
.eyebrow{color:#62d9f2;letter-spacing:.18em;font-size:12px;margin-bottom:12px}.subtitle{color:#9aafc9;font-size:18px;max-width:850px}
</style>''',unsafe_allow_html=True)
with st.sidebar:
    st.markdown('## ◈ QuantumGrid\n**PERÚ / LABORATORIO**')
    page=st.radio('Navegación',PAGES,label_visibility='collapsed')
    st.divider()
    size=st.select_slider('Tamaño de instancia',options=[4,6,8,10,12],value=12)
    alpha=st.number_input('α · costo normalizado',0.0,10.0,1.0,.1)
    beta=st.number_input('β · balance normalizado',.1,20.0,3.0,.1)
    seed=st.number_input('Semilla',0,100000,7)
    st.caption('Red sintética · simulación local Aer\n\nMapa y subredes reales: snapshots OSINERGMIN\n\nSin instrucciones de operación eléctrica.')

if st.session_state.get('size')!=size:
    st.session_state.update(size=size,data=load_network(size),runs={})
data=st.session_state.data; obj=Objective(alpha,beta)
key=fingerprint(data,obj.__dict__)
if st.session_state.get('input_hash')!=key:
    st.session_state.update(input_hash=key,runs={})
runs=st.session_state.runs
st.markdown('<div class="eyebrow">QISKIT FALL FEST 2026 / RETO 5.2</div>',unsafe_allow_html=True)
st.title('QuantumGrid Perú' if page=='Inicio' else page)
st.markdown('<p class="subtitle">Conectando decisiones inteligentes para construir redes más resilientes.</p>',unsafe_allow_html=True)
st.caption('Prototipo académico. Conectividad, balance agregado y operación eléctrica segura son conceptos diferentes.')
m=metrics(data)

if page in REAL_PAGES:
    render_real_page(page,alpha,beta,seed)
    st.stop()

def show_result(r):
    st.json({k:v for k,v in r.items() if k not in ['counts','trace','hamiltonian','parameters']},expanded=False)
    if r['bits'] is not None:
        st.plotly_chart(network_figure(data,r['bits']),width='stretch',key='result-'+r['method'])
        st.caption('Los colores representan etiquetas binarias. Una etiqueta puede contener varias componentes.')
        st.json({'después_del_corte_abstracto':metrics(data,r['bits'])},expanded=False)

if page=='Inicio':
    st.markdown('### Decisiones de conexión, con evidencia verificable')
    cols=st.columns(2)+st.columns(2)
    for c,label,value in zip(cols,['Nodos sintéticos','Componentes','Sin fuente (u.s.)','Cota abastecible (u.s.)'],[size,m['components'],m['disconnected_demand'],m['potentially_supplyable']]): c.metric(label,value)
    a=st.container(); b=st.expander('Cómo utilizar el laboratorio',expanded=False)
    with a: st.plotly_chart(network_figure(data),width='stretch')
    with b:
        st.markdown('### Un laboratorio de resiliencia\nExplore una red sintética, retire enlaces y contraste particiones clásicas con muestras QAOA.\n\n**01 / Observe** la conectividad.\n\n**02 / Experimente** con fallas y demanda.\n\n**03 / Compare** el mismo objetivo y valide las candidatas.')
        st.info('La cota abastecible suma min(demanda, generación) por componente. No representa energía efectivamente servida.')
elif page=='Explorador de red':
    st.plotly_chart(network_figure(data),width='stretch')
    st.dataframe(pd.DataFrame(data['nodes']),hide_index=True)
    st.dataframe(pd.DataFrame(data['edges']),hide_index=True)
    st.write('Puentes topológicos:',m['bridges'])
    st.caption('Posiciones de diagrama, no coordenadas geográficas. Prioridad, vulnerabilidad y capacidad son metadatos; no entran al Hamiltoniano base.')
elif page=='Simulador de fallas':
    st.write('Construya un escenario a partir de la red inicial. Aplicarlo invalida todos los resultados anteriores.')
    base=load_network(size)
    failed=st.multiselect('Conexiones afectadas',[f"{e['source']}–{e['target']}" for e in base['edges']])
    selected=st.multiselect('Nodos con demanda modificada',list(range(size)),default=list(range(size)))
    factor=st.slider('Factor de demanda',.1,3.0,1.0,.1)
    apply=st.button('Aplicar escenario',type='primary')
    if apply:
        pairs=[tuple(map(int,pair.split('–'))) for pair in failed]
        st.session_state.data=scenario(base,pairs,factor,selected); st.rerun()
    a,b=st.columns(2)
    with a:
        st.subheader('Inicial'); st.plotly_chart(network_figure(base),width='stretch')
    with b:
        st.subheader('Escenario activo'); st.plotly_chart(network_figure(data),width='stretch',key='after')
    st.json(m,expanded=False)
    with st.expander('Escenario personalizado · JSON editable'):
        raw=st.text_area('Nodos, enlaces, costos, demanda, generación y estados',json.dumps(data,ensure_ascii=False,indent=2),height=300,key=f'editor-{key}')
        if st.button('Validar y reemplazar escenario'):
            try:
                parsed=validate(json.loads(raw))
                if len(parsed['nodes'])!=size: raise ValueError('Mantenga el tamaño seleccionado; puede renombrar o editar nodos.')
                st.session_state.data=parsed; st.rerun()
            except (ValueError,KeyError,TypeError) as e: st.error(str(e))
elif page=='Optimización clásica':
    st.write('Exacto explora 2ⁿ⁻¹−1 particiones no vacías. Búsqueda local minimiza H. Kernighan–Lin minimiza el corte con cardinalidades equilibradas; sus candidatas se evalúan con H.')
    if st.button('Ejecutar los tres métodos',type='primary'):
        with st.spinner('Calculando soluciones y validadores…'):
            for fn in (brute_force,local_search,kernighan_lin):
                r=fn(data,obj) if fn==brute_force else fn(data,obj,seed=int(seed)); runs[r['method']]=r
    for name in ['Exacto','Búsqueda local','Kernighan–Lin']:
        if name in runs:
            with st.expander(name,expanded=name=='Exacto'): show_result(runs[name])
elif page=='Laboratorio cuántico':
    st.info('Optimización ideal por vector de estado Aer; medición final con shots. Grupos no vacíos se filtran después de medir. Conectividad y generación se diagnostican, no se optimizan.')
    with st.form('qaoa'):
        cols=st.columns(4)
        p=cols[0].slider('Capas p',1,4,1)
        maxiter=cols[1].slider('Iteraciones máximas',10,150,60,10)
        shots=cols[2].selectbox('Mediciones',[512,2048,8192],index=1)
        optimizer=cols[3].selectbox('Optimizador',['COBYLA','SLSQP','Powell'])
        launch=st.form_submit_button('Ejecutar QAOA en Aer',type='primary')
    if launch:
        with st.spinner('Construyendo el circuito y optimizando parámetros…'):
            try: runs['QAOA']=solve(data,obj,p=p,maxiter=maxiter,shots=shots,seed=int(seed),optimizer=optimizer)
            except Exception as e: st.error(f'La ejecución falló: {e}')
    if 'QAOA' in runs:
        r=runs['QAOA']; show_result(r)
        if 'trace' in r:
            st.plotly_chart(px.line(y=r['trace'],labels={'index':'Evaluación','y':'H esperado'},title='Convergencia observada'),width='stretch')
elif page=='Comparación':
    if not runs: st.info('Ejecute los métodos clásicos y QAOA para comparar resultados de este escenario.')
    else:
        optimum=runs.get('Exacto',{}).get('objective'); rows=[]
        for r in runs.values():
            rows.append({'Método':r['method'],'H normalizado':r['objective'],'Corte bruto':r['cut'],'Factible base':r['validation']['feasible'],
                         'Tiempo (s)':r['seconds'],'Brecha':gap(r['objective'],optimum) if optimum is not None and r['validation']['feasible'] else None,'Evaluaciones':r['evaluations'],'Semilla':r['seed']})
        st.dataframe(pd.DataFrame(rows),hide_index=True)
        st.plotly_chart(px.bar(pd.DataFrame(rows),x='Método',y='H normalizado',color='Método'),width='stretch')
        st.caption('Brecha en % si H* > 0; diferencia absoluta si H* = 0. Vacío = no aplica. Evaluaciones KL: solo candidatos evaluados externamente. Tiempos incluyen preparación y validación del solucionador.')
        if optimum is not None and 'counts' in runs.get('QAOA',{}): st.metric('Frecuencia de medir un óptimo factible',f"{optimal_probability(runs['QAOA'],data,obj,optimum):.2%}")
elif page=='Quantum Explain':
    st.markdown('### Del grafo a una distribución de candidatas')
    st.latex(r'H(z)=\alpha\frac{\sum_{(i,j)\in E_{activo}}w_{ij}(z_i-z_j)^2}{W_{ref}}+\beta\left(\frac{\sum_i d_i(1-2z_i)}{D}\right)^2')
    st.markdown('1. Cada nodo tiene un qubit: medir 0 o 1 asigna una etiqueta.\n2. La sustitución zᵢ=(1−Zᵢ)/2 transforma el QUBO en Ising.\n3. Las rotaciones RZZ aplican fases según el costo; RX mezcla amplitudes.\n4. SciPy ajusta 2p ángulos para reducir el costo esperado calculado con Aer.\n5. Se mide, se invierte el orden de bits de Qiskit y se evalúa cada candidata.\n6. Se descartan grupos vacíos y se diagnostican conectividad y generación. QAOA no garantiza el óptimo ni devuelve todas las soluciones.')
    p=runs.get('QAOA',{}).get('p',1)
    qc,op,offset,scale=circuit(data,obj,p)
    st.write(f'{qc.num_qubits} qubits · profundidad lógica {qc.depth()} · {qc.size()} compuertas · constante {offset:.6f} · escala {scale:.6f}')
    with st.expander('Circuito generado por Qiskit'):
        st.code(str(qc.draw(output='text',fold=110)))
        if st.button('Renderizar diagrama del circuito'):
            import matplotlib.pyplot as plt
            fig=qc.draw(output='mpl',fold=24); st.pyplot(fig); plt.close(fig)
    with st.expander('Hamiltoniano completo (incluye identidad)'): st.dataframe(pd.DataFrame([(s,float(c.real)) for s,c in op.to_list()],columns=['Pauli','Coeficiente']))
    if 'counts' in runs.get('QAOA',{}):
        counts=runs['QAOA']['counts']; top=sorted(counts,key=counts.get,reverse=True)[:24]
        st.plotly_chart(px.bar(x=top,y=[counts[x] for x in top],labels={'x':'Bitstring Qiskit (qubit 0 a la derecha)','y':'Conteos'},title='24 resultados más frecuentes; exportación incluye todos'),width='stretch')
elif page=='Resultados':
    st.download_button('Descargar escenario y ejecuciones JSON',bundle(data,obj,runs),'quantumgrid-run.json','application/json')
    if runs:
        flat=[{k:r.get(k) for k in ['method','objective','cut','seconds','evaluations','seed']} for r in runs.values()]
        st.download_button('Descargar comparación CSV',pd.DataFrame(flat).to_csv(index=False),'comparison.csv','text/csv')
    st.code(f'Huella del escenario y objetivo: {key}')
    path=ROOT/'results'/'benchmark.json'
    if path.exists():
        st.markdown('### Experimentos guardados · escenarios independientes')
        st.caption('Son ejecuciones del benchmark, no resultados del escenario activo.')
        st.download_button('Descargar benchmark reproducible',path.read_text(encoding='utf8'),'benchmark.json','application/json')
        report=ROOT/'docs'/'RESULTS.md'
        if report.exists(): st.markdown(report.read_text(encoding='utf8'))
    st.caption('Demanda efectivamente servida: no calculada. No hay flujo AC/DC, frecuencia, protecciones ni estabilidad dinámica.')
