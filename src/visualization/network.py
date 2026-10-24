import plotly.graph_objects as go
from ..models.graph_model import graph

def network_figure(data,bits=None):
    fig=go.Figure(); active=graph(data); seen=set()
    for e in data['edges']:
        a,b=e['source'],e['target']; x,y=data['nodes'][a]['position'],data['nodes'][b]['position']
        state='Falla' if e['failed'] else 'Inactiva' if not active.has_edge(a,b) else 'Corte' if bits is not None and bits[a]!=bits[b] else 'Disponible'
        color={'Falla':'#ff6078','Inactiva':'#667085','Corte':'#ffaf56','Disponible':'#365973'}[state]
        fig.add_trace(go.Scatter(x=[x[0],y[0]],y=[x[1],y[1]],mode='lines',line=dict(color=color,width=3,dash='dot' if state in ('Falla','Inactiva') else 'solid'),name=state,legendgroup=state,showlegend=state not in seen,
                                 text=f"{data['nodes'][a]['name']} ↔ {data['nodes'][b]['name']}<br>Costo {e['cost']} · {state}",hoverinfo='text'))
        # Midpoint makes connection attributes easy to inspect.
        fig.add_trace(go.Scatter(x=[(x[0]+y[0])/2],y=[(x[1]+y[1])/2],mode='markers',marker=dict(size=9,color=color),showlegend=False,text=f"{a}–{b}: costo {e['cost']} · {state}",hoverinfo='text'))
        seen.add(state)
    for group,color in [(0,'#4bbcff'),(1,'#b798ff')]:
        nodes=[v for v in data['nodes'] if (bits[v['id']] if bits is not None else 0)==group]
        if not nodes: continue
        fig.add_trace(go.Scatter(x=[v['position'][0] for v in nodes],y=[v['position'][1] for v in nodes],mode='markers+text',text=[v['name'] for v in nodes],textposition='top center',
          customdata=[[v['demand'],v['generation'],v['operational'],v['id']] for v in nodes],hovertemplate='%{text}<br>ID %{customdata[3]}<br>Demanda %{customdata[0]} u.s.<br>Generación %{customdata[1]} u.s.<br>Operativo %{customdata[2]}<extra></extra>',
          marker=dict(size=22,color=color,line=dict(color='#d8f5ff',width=1),symbol=['circle' if v['operational'] else 'x' for v in nodes]),name=f'Grupo {group}' if bits is not None else 'Nodos'))
    fig.update_layout(height=520,paper_bgcolor='#0c1729',plot_bgcolor='#0c1729',font=dict(color='#dce8f8',family='Segoe UI'),margin=dict(l=30,r=30,t=45,b=30),legend=dict(orientation='h',y=-.04),xaxis=dict(visible=False),yaxis=dict(visible=False),hovermode='closest')
    return fig
