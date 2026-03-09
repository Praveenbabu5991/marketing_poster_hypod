"""Tests for BrandContext dataclass."""

import pytest

from brand.context import BrandContext


class TestBrandContext:

    def test_empty_context(self):
        bc = BrandContext()
        assert bc.name == ""
        assert bc.is_complete is False
        assert "brand name" in bc.missing_fields

    def test_complete_context(self):
        bc = BrandContext(
            name="TestBrand",
            tone="professional",
            logo_path="/logos/test.png",
            colors=["#ff0000"],
        )
        assert bc.is_complete is True
        assert bc.missing_fields == []

    def test_missing_fields(self):
        bc = BrandContext(name="Test")
        missing = bc.missing_fields
        assert "logo" in missing
        assert "brand colors" in missing
        assert "brand tone/voice" in missing
        assert "brand name" not in missing

    def test_to_prompt_text(self):
        bc = BrandContext(
            name="TestBrand",
            industry="Fashion",
            tone="luxurious",
            colors=["#1a1a2e", "#e94560"],
        )
        text = bc.to_prompt_text()
        assert "TestBrand" in text
        assert "Fashion" in text
        assert "luxurious" in text
        assert "#1a1a2e, #e94560" in text

    def test_to_dict_and_from_dict(self):
        bc = BrandContext(
            name="TestBrand",
            industry="Tech",
            tone="bold",
            colors=["#000"],
            product_images=["/img/product.jpg"],
        )
        d = bc.to_dict()
        bc2 = BrandContext.from_dict(d)
        assert bc2.name == "TestBrand"
        assert bc2.industry == "Tech"
        assert bc2.colors == ["#000"]
        assert bc2.product_images == ["/img/product.jpg"]

    def test_from_dict_none(self):
        bc = BrandContext.from_dict(None)
        assert bc.name == ""
        assert bc.is_complete is False

    def test_from_dict_empty(self):
        bc = BrandContext.from_dict({})
        assert bc.name == ""

    def test_prompt_text_not_set_values(self):
        bc = BrandContext()
        text = bc.to_prompt_text()
        assert "Not set" in text
        assert "Not uploaded" in text
        assert "None" in text
