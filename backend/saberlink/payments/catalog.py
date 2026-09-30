"""Catálogo de Productos y Configuración de RevenueCat

Este módulo define el modelo de negocio para suscripciones:
- Productos (Products): SKUs reales en las tiendas
- Paquetes (Packages): Envoltorios del SDK
- Ofrecimientos (Offerings): Colecciones de paquetes
- Entitlements: Derechos de acceso

Sigue la arquitectura modular: puede eliminarse sin romper el core.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from enum import Enum
from dataclasses import dataclass


class Entitlement(Enum):
    """Entitlements (derechos de acceso) que ofrece la app."""
    PRO = "pro"  # Acceso completo a funciones premium


class PackageType(Enum):
    """Tipos de paquetes estándar de RevenueCat."""
    MONTHLY = "$rc_monthly"
    ANNUAL = "$rc_annual"
    LIFETIME = "$rc_lifetime"
    WEEKLY = "$rc_weekly"


@dataclass
class Product:
    """Producto real en las tiendas (App Store / Google Play)."""
    product_id: str
    package_type: PackageType
    price_display: str
    description: str
    
    # Límites de uso para este producto
    pdf_uploads_per_month: int
    text_queries_per_month: int


@dataclass
class Package:
    """Paquete del SDK que estandariza el tipo de cobro."""
    identifier: str
    package_type: PackageType
    product: Product
    offering_id: str


@dataclass
class Offering:
    """Colección de paquetes disponibles en un momento dado."""
    identifier: str
    description: str
    packages: List[Package]
    metadata: Dict


# Catálogo de productos para SaberLink
PRODUCT_CATALOG = {
    # Productos mensuales
    "com.saberlink.app.pro_monthly": Product(
        product_id="com.saberlink.app.pro_monthly",
        package_type=PackageType.MONTHLY,
        price_display="$9.99/mes",
        description="Acceso Pro mensual",
        pdf_uploads_per_month=50,
        text_queries_per_month=500
    ),
    
    # Productos anuales
    "com.saberlink.app.pro_yearly": Product(
        product_id="com.saberlink.app.pro_yearly",
        package_type=PackageType.ANNUAL,
        price_display="$89.99/año",
        description="Acceso Pro anual (mejor valor)",
        pdf_uploads_per_month=100,
        text_queries_per_month=1000
    ),
    
    # Producto semanal (opcional)
    "com.saberlink.app.pro_weekly": Product(
        product_id="com.saberlink.app.pro_weekly",
        package_type=PackageType.WEEKLY,
        price_display="$2.99/semana",
        description="Acceso Pro semanal",
        pdf_uploads_per_month=15,
        text_queries_per_month=150
    ),
}


# Ofrecimientos configurados
OFFERINGS = {
    "default": Offering(
        identifier="default",
        description="Oferta principal",
        packages=[
            Package(
                identifier="$rc_monthly",
                package_type=PackageType.MONTHLY,
                product=PRODUCT_CATALOG["com.saberlink.app.pro_monthly"],
                offering_id="default"
            ),
            Package(
                identifier="$rc_annual",
                package_type=PackageType.ANNUAL,
                product=PRODUCT_CATALOG["com.saberlink.app.pro_yearly"],
                offering_id="default"
            ),
        ],
        metadata={"priority": 1}
    ),
    
    "black_friday": Offering(
        identifier="black_friday",
        description="Oferta especial Black Friday",
        packages=[
            Package(
                identifier="$rc_monthly",
                package_type=PackageType.MONTHLY,
                product=PRODUCT_CATALOG["com.saberlink.app.pro_monthly"],
                offering_id="black_friday"
            ),
            Package(
                identifier="$rc_annual",
                package_type=PackageType.ANNUAL,
                product=PRODUCT_CATALOG["com.saberlink.app.pro_yearly"],
                offering_id="black_friday"
            ),
        ],
        metadata={"priority": 2, "discount": "20%"}
    ),
}


def get_product(product_id: str) -> Optional[Product]:
    """Obtener un producto del catálogo por su ID."""
    return PRODUCT_CATALOG.get(product_id)


def get_offering(offering_id: str = "default") -> Optional[Offering]:
    """Obtener un ofrecimiento por su ID."""
    return OFFERINGS.get(offering_id)


def get_package_limits(package_identifier: str) -> Dict:
    """Obtener límites de uso para un paquete específico."""
    # Buscar el paquete en los ofrecimientos
    for offering in OFFERINGS.values():
        for package in offering.packages:
            if package.identifier == package_identifier:
                return {
                    "pdf_uploads_per_month": package.product.pdf_uploads_per_month,
                    "text_queries_per_month": package.product.text_queries_per_month,
                    "package_type": package.package_type.value,
                    "product_id": package.product.product_id
                }
    
    # Retornar límites por defecto si no se encuentra
    return {
        "pdf_uploads_per_month": 5,
        "text_queries_per_month": 20,
        "package_type": "free",
        "product_id": "free"
    }


def get_entitlements_from_package(package_identifier: str) -> List[str]:
    """Determinar qué entitlements da un paquete."""
    if package_identifier in ["$rc_monthly", "$rc_annual", "$rc_lifetime", "$rc_weekly"]:
        return [Entitlement.PRO.value]
    return []


def map_revenuecat_to_catalog(revenuecat_package: Dict) -> Optional[Package]:
    """Mapear un paquete de RevenueCat a nuestro catálogo interno."""
    try:
        package_identifier = revenuecat_package.get("identifier", "")
        product_id = revenuecat_package.get("productIdentifier", "")
        
        # Buscar producto en nuestro catálogo
        product = get_product(product_id)
        if not product:
            return None
        
        # Determinar tipo de paquete
        package_type = None
        for pt in PackageType:
            if package_identifier.startswith(pt.value.replace("$", "")):
                package_type = pt
                break
        
        if not package_type:
            package_type = PackageType.MONTHLY  # Default
        
        return Package(
            identifier=package_identifier,
            package_type=package_type,
            product=product,
            offering_id="default"
        )
    except Exception:
        return None


def format_price_for_display(price_amount: float, currency_code: str = "USD") -> str:
    """Formatear precio para mostrar en la UI."""
    currency_symbols = {
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
        "MXN": "$",
    }
    
    symbol = currency_symbols.get(currency_code, currency_code)
    return f"{symbol}{price_amount:.2f}"


def get_usage_limits_from_entitlements(entitlements: Dict) -> Dict:
    """Determinar límites de uso basado en entitlements activos."""
    if Entitlement.PRO.value in entitlements:
        # Si tiene entitlement pro, buscar el producto asociado
        pro_entitlement = entitlements[Entitlement.PRO.value]
        product_id = pro_entitlement.get("productIdentifier", "")
        
        product = get_product(product_id)
        if product:
            return {
                "pdf_uploads_per_month": product.pdf_uploads_per_month,
                "text_queries_per_month": product.text_queries_per_month,
                "tier": "pro"
            }
    
    # Por defecto, tier gratuito
    return {
        "pdf_uploads_per_month": 5,
        "text_queries_per_month": 20,
        "tier": "free"
    }