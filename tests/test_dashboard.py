"""Smoke tests for the Streamlit dashboard, run headless via Streamlit's AppTest."""

import pytest
from streamlit.testing.v1 import AppTest

from src.config import ROOT

APP = str(ROOT / "src" / "dashboard" / "app.py")


def test_app_explains_missing_pipeline_outputs(tmp_path, monkeypatch):
    monkeypatch.setenv("OLIST_DATA_DIR", str(tmp_path))
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert any("python -m src.pipeline" in e.value for e in at.error)


def test_app_renders_every_tab_on_real_data(real_warehouse, monkeypatch):
    monkeypatch.setenv("OLIST_DATA_DIR", str(ROOT / "data"))
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception
    assert len(at.tabs) == 7
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["On-time delivery"].endswith("%")
    assert metrics["Flagged (significantly late)"] == "81"


def test_filters_change_figures_without_errors(real_warehouse, monkeypatch):
    monkeypatch.setenv("OLIST_DATA_DIR", str(ROOT / "data"))
    at = AppTest.from_file(APP, default_timeout=120).run()
    before = {m.label: m.value for m in at.metric}["Orders (selected period)"]
    at.multiselect[0].select("Northeast").run()
    assert not at.exception
    after = {m.label: m.value for m in at.metric}["Orders (selected period)"]
    assert after != before
    at.toggle[0].set_value(True).run()
    assert not at.exception
    assert {m.label: m.value for m in at.metric}["Sellers shown"] == "81"


@pytest.mark.parametrize("region", ["North", "South"])
def test_each_region_filter_renders(real_warehouse, monkeypatch, region):
    monkeypatch.setenv("OLIST_DATA_DIR", str(ROOT / "data"))
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.multiselect[0].select(region).run()
    assert not at.exception
