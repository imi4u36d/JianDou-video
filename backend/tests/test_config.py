"""Tests for configuration management."""

import pytest
from jiandou.storage.config import AppConfig, ServerConfig, EngineConfig, load_config


class TestAppConfig:
    def test_default_config(self):
        config = AppConfig()
        assert config.server.host == "0.0.0.0"
        assert config.server.port == 8000
        assert config.engine.model_version == "2.3"
        assert config.engine.fp16 is True
        assert config.queue.max_workers == 1
        assert config.generation.width == 768
        assert config.generation.height == 512

    def test_load_config_from_yaml(self):
        config = load_config()
        assert config is not None
        assert isinstance(config.server, ServerConfig)
        assert isinstance(config.engine, EngineConfig)
        assert config.engine.model_version in ("2.0", "2.3")

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("JIAN_DOU_SERVER__PORT", "9999")
        config = AppConfig()
        assert config.server.port == 9999

    def test_server_config_defaults(self):
        s = ServerConfig()
        assert s.host == "0.0.0.0"
        assert s.port == 8000
        assert s.cors_origins == ["*"]

    def test_config_serialization(self):
        config = AppConfig()
        d = config.model_dump()
        assert "server" in d
        assert "engine" in d
        assert d["server"]["port"] == 8000
