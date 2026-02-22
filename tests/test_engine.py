from unittest.mock import patch

import yaml

from mongoose.core.engine import Engine
from mongoose.models.configuration import Configuration


def test_engine_initialization(tmp_path):
    config_content = {
        "configuration": {
            "collector": {
                "suricata": {"socket_path": "/tmp/suricata.socket", "enable": True},
                "nf_stream": {"interface": "eth0", "enable": False},
            },
            "enrichment": {"geoip": {"remote_service_url": "http://geoip", "enable": True}},
            "forwarder": {
                "file": {"output_dir": str(tmp_path / "output"), "enable": True},
                "webhooks": [{"url": "http://webhook", "enable": False}],
            },
        }
    }
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_content, f)

    engine = Engine(str(config_file), watch_configuration_changes=False)
    assert isinstance(engine.config, Configuration)
    assert engine.config.collector.suricata.enable is True
    assert engine.config.collector.nf_stream.enable is False


@patch("mongoose.collect.suricata_eve_collector.SuricataEveCollector.start")
@patch("mongoose.enrich.Enrich.start")
@patch("mongoose.forward.file.FileForwarder.start")
@patch("mongoose.enrich.Enrich.__init__", return_value=None)
def test_engine_start(mock_enrich_init, mock_file_start, mock_enrich_start, mock_suricata_start, tmp_path):
    config_content = {
        "configuration": {
            "collector": {
                "suricata": {"socket_path": "/tmp/suricata.socket", "enable": True},
                "nf_stream": {"interface": "eth0", "enable": False},
            },
            "enrichment": {"geoip": {"enable": True}},
            "forwarder": {
                "file": {"output_dir": str(tmp_path / "output"), "enable": True},
                "webhooks": [{"url": "http://webhook", "enable": False}],
            },
        }
    }
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_content, f)

    engine = Engine(str(config_file), watch_configuration_changes=False)
    engine.start()

    assert mock_suricata_start.called
    assert mock_enrich_start.called
    assert mock_file_start.called


@patch("mongoose.core.processing.ProcessingQueue.stop_processing")
def test_engine_stop(mock_stop_processing, tmp_path):
    config_content = {
        "configuration": {
            "collector": {
                "suricata": {"socket_path": "/tmp/suricata.socket", "enable": False},
                "nf_stream": {"interface": "eth0", "enable": False},
            },
            "enrichment": {"geoip": {"enable": False}},
            "forwarder": {
                "file": {"output_dir": str(tmp_path / "output"), "enable": False},
                "webhooks": [{"url": "http://webhook", "enable": False}],
            },
        }
    }
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_content, f)

    engine = Engine(str(config_file), watch_configuration_changes=False)
    engine.stop()
    assert mock_stop_processing.called


@patch("mongoose.core.engine.Engine.stop")
@patch("mongoose.core.engine.Engine.start")
@patch("mongoose.core.engine.Engine.load_config")
@patch("mongoose.core.engine.Engine._setup_components")
def test_engine_reload(mock_setup, mock_load, mock_start, mock_stop, tmp_path):
    config_content = {"configuration": {"collector": {}, "enrichment": {}, "forwarder": {}}}
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_content, f)

    engine = Engine(str(config_file), watch_configuration_changes=False)
    engine.reload()

    assert mock_stop.called
    assert mock_load.called
    assert mock_setup.called
    assert mock_start.called
