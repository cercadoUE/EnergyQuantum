import pytest
from streamlit.testing.v1 import AppTest
from app_pages import PAGES
from src.models.graph_model import ROOT

@pytest.mark.parametrize('page',PAGES)
def test_pages(page):
    app=AppTest.from_file(ROOT/'app.py',default_timeout=30).run()
    app.sidebar.radio[0].set_value(page).run()
    assert not app.exception

def test_classical_and_invalidation():
    app=AppTest.from_file(ROOT/'app.py',default_timeout=30).run()
    app.sidebar.select_slider[0].set_value(4).run()
    app.sidebar.radio[0].set_value('Optimización clásica').run()
    app.button[0].click().run()
    assert len(app.session_state['runs'])==3
    app.sidebar.number_input[1].set_value(2.0).run()
    assert not app.session_state['runs']
    assert not app.exception
