"""Brand context dataclass for agent prompt injection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BrandContext:
    """Brand identity stored in agent state."""

    name: str = ""
    industry: str = ""
    overview: str = ""
    tone: str = ""
    logo_path: Optional[str] = None
    colors: list[str] = field(default_factory=list)
    target_audience: str = ""
    products_services: str = ""
    product_images: list[str] = field(default_factory=list)

    @property
    def primary_color(self) -> str:
        return self.colors[0] if self.colors else ""

    @property
    def secondary_color(self) -> str:
        return self.colors[1] if len(self.colors) > 1 else self.primary_color

    @property
    def is_complete(self) -> bool:
        return bool(self.name and self.logo_path and self.colors and self.tone)

    @property
    def missing_fields(self) -> list[str]:
        missing = []
        if not self.name:
            missing.append("brand name")
        if not self.logo_path:
            missing.append("logo")
        if not self.colors:
            missing.append("brand colors")
        if not self.tone:
            missing.append("brand tone/voice")
        return missing

    def to_prompt_text(self) -> str:
        """Formatted string for injection into agent system prompts."""
        additional = self.colors[2:] if len(self.colors) > 2 else []
        return (
            f"Brand Name: {self.name}\n"
            f"Industry: {self.industry}\n"
            f"Overview: {self.overview}\n"
            f"Tone/Voice: {self.tone}\n"
            f"Target Audience: {self.target_audience}\n"
            f"Products/Services: {self.products_services}\n"
            f"Primary Color: {self.primary_color or 'Not set'}\n"
            f"Secondary Color: {self.secondary_color or 'Not set'}\n"
            f"Additional Colors: {', '.join(additional) if additional else 'None'}\n"
            f"Logo Path: {self.logo_path or 'Not uploaded'}\n"
            f"Product Images: {', '.join(self.product_images) if self.product_images else 'None'}"
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "industry": self.industry,
            "overview": self.overview,
            "tone": self.tone,
            "logo_path": self.logo_path,
            "colors": self.colors,
            "target_audience": self.target_audience,
            "products_services": self.products_services,
            "product_images": self.product_images,
        }

    @classmethod
    def from_dict(cls, data: dict) -> BrandContext:
        if not data:
            return cls()
        return cls(
            name=data.get("name", ""),
            industry=data.get("industry", ""),
            overview=data.get("overview", ""),
            tone=data.get("tone", ""),
            logo_path=data.get("logo_path"),
            colors=data.get("colors", []),
            target_audience=data.get("target_audience", ""),
            products_services=data.get("products_services", ""),
            product_images=data.get("product_images", []),
        )

    @classmethod
    def from_db_model(cls, brand) -> BrandContext:
        """Create from SQLAlchemy Brand model."""
        return cls(
            name=brand.name,
            industry=brand.industry or "",
            overview=brand.overview or "",
            tone=brand.tone,
            logo_path=brand.logo_path,
            colors=brand.colors or [],
            target_audience=brand.target_audience or "",
            products_services=brand.products_services or "",
            product_images=brand.product_images or [],
        )
