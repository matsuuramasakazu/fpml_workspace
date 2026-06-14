"""Tests for holiday calendar TOML files."""

import tomllib
from pathlib import Path


class TestHolidaysToml:
    """Verify TOML holiday calendar files are correctly formatted and populated."""

    def setup_method(self):
        """Setup test fixtures."""
        self.config_dir = Path(__file__).parent.parent.parent / "config"

    def test_holidays_gblo_exists(self):
        """Test: GBLO holiday calendar file exists."""
        gblo_file = self.config_dir / "holidays_GBLO.toml"
        assert gblo_file.exists(), "holidays_GBLO.toml must exist in config/"

    def test_holidays_gblo_valid_toml(self):
        """Test: GBLO file is valid TOML with [holidays] section."""
        gblo_file = self.config_dir / "holidays_GBLO.toml"
        with open(gblo_file, "rb") as f:
            data = tomllib.load(f)
        
        assert "holidays" in data, "TOML must contain [holidays] section"
        assert isinstance(data["holidays"], dict), "[holidays] must be a dict"

    def test_holidays_gblo_has_entries(self):
        """Test: GBLO has at least one holiday entry."""
        gblo_file = self.config_dir / "holidays_GBLO.toml"
        with open(gblo_file, "rb") as f:
            data = tomllib.load(f)
        
        holidays = data.get("holidays", {})
        assert len(holidays) > 0, "GBLO must have at least one holiday entry"

    def test_holidays_usny_exists(self):
        """Test: USNY holiday calendar file exists."""
        usny_file = self.config_dir / "holidays_USNY.toml"
        assert usny_file.exists(), "holidays_USNY.toml must exist in config/"

    def test_holidays_usny_valid_toml(self):
        """Test: USNY file is valid TOML with [holidays] section."""
        usny_file = self.config_dir / "holidays_USNY.toml"
        with open(usny_file, "rb") as f:
            data = tomllib.load(f)
        
        assert "holidays" in data, "TOML must contain [holidays] section"
        assert isinstance(data["holidays"], dict), "[holidays] must be a dict"

    def test_holidays_jpto_exists(self):
        """Test: JPTO holiday calendar file exists."""
        jpto_file = self.config_dir / "holidays_JPTO.toml"
        assert jpto_file.exists(), "holidays_JPTO.toml must exist in config/"

    def test_holidays_jpto_valid_toml(self):
        """Test: JPTO file is valid TOML with [holidays] section."""
        jpto_file = self.config_dir / "holidays_JPTO.toml"
        with open(jpto_file, "rb") as f:
            data = tomllib.load(f)
        
        assert "holidays" in data, "TOML must contain [holidays] section"
        assert isinstance(data["holidays"], dict), "[holidays] must be a dict"
