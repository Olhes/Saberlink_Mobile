"""Flujo de Compras y Verificación de Estado

Este módulo maneja el núcleo operativo de compras:
- Carga de ofertas (Get Offerings)
- Ejecución de compra (Purchase Package)
- Verificación de entitlements
- Restaurar compras (Restore Purchases)
- Manejo de errores y estados

Sigue la arquitectura modular: puede eliminarse sin romper el core.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from enum import Enum
from datetime import datetime
import json


class PurchaseState(Enum):
    """Estados posibles de una compra."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEFERRED = "deferred"  # Aprobación parental
    REFUNDED = "refunded"


class PurchaseError(Enum):
    """Tipos de errores de compra."""
    USER_CANCELLED = "user_cancelled"
    PAYMENT_DECLINED = "payment_declined"
    NETWORK_ERROR = "network_error"
    INVALID_PRODUCT = "invalid_product"
    ALREADY_OWNED = "already_owned"
    PERMISSION_DENIED = "permission_denied"
    UNKNOWN = "unknown"


def get_offerings_for_user(user_id: str, offering_id: str = "default") -> Dict:
    """Cargar ofertas disponibles para un usuario específico.
    
    Args:
        user_id: ID del usuario
        offering_id: ID del ofrecimiento (default, black_friday, etc.)
        
    Returns:
        Dict con la información del ofrecimiento y paquetes disponibles
    """
    from saberlink.payments.catalog import get_offering
    
    offering = get_offering(offering_id)
    if not offering:
        return {
            "success": False,
            "error": "offering_not_found",
            "message": f"Ofrecimiento {offering_id} no encontrado"
        }
    
    # Formatear paquetes para la respuesta
    formatted_packages = []
    for package in offering.packages:
        formatted_packages.append({
            "identifier": package.identifier,
            "package_type": package.package_type.value,
            "product_id": package.product.product_id,
            "price_display": package.product.price_display,
            "description": package.product.description,
            "limits": {
                "pdf_uploads_per_month": package.product.pdf_uploads_per_month,
                "text_queries_per_month": package.product.text_queries_per_month
            }
        })
    
    return {
        "success": True,
        "offering_id": offering.identifier,
        "description": offering.description,
        "packages": formatted_packages,
        "metadata": offering.metadata
    }


def validate_purchase_eligibility(user_id: str, package_identifier: str) -> Dict:
    """Validar si un usuario puede comprar un paquete específico.
    
    Args:
        user_id: ID del usuario
        package_identifier: Identificador del paquete ($rc_monthly, $rc_annual, etc.)
        
    Returns:
        Dict con resultado de validación
    """
    from saberlink.payments.subscription import validate_subscription
    from saberlink.payments.catalog import get_package_limits
    
    # Verificar suscripción actual
    current_sub = validate_subscription(user_id)
    
    # Obtener límites del paquete
    package_limits = get_package_limits(package_identifier)
    
    # Verificar si ya tiene el mismo o mejor paquete
    if current_sub["current_tier"] == "pro":
        current_limits = get_package_limits("$rc_annual")  # Asumir anual como pro
        
        # Si ya tiene anual, no puede comprar mensual
        if package_identifier == "$rc_monthly" and current_sub["current_tier"] == "pro":
            return {
                "eligible": False,
                "reason": "already_has_better_tier",
                "message": "Ya tienes una suscripción Pro activa"
            }
    
    return {
        "eligible": True,
        "current_tier": current_sub["current_tier"],
        "target_tier": package_limits.get("tier", "pro")
    }


def simulate_purchase(user_id: str, package_identifier: str) -> Dict:
    """Simular una compra (para modo sandbox/desarrollo).
    
    Args:
        user_id: ID del usuario
        package_identifier: Identificador del paquete
        
    Returns:
        Dict con resultado de la compra simulada
    """
    from saberlink.payments.catalog import get_package_limits, get_entitlements_from_package
    from saberlink.payments.subscription import process_subscription_update
    
    # Simular validación
    eligibility = validate_purchase_eligibility(user_id, package_identifier)
    if not eligibility["eligible"]:
        return {
            "success": False,
            "state": PurchaseState.FAILED.value,
            "error": eligibility["reason"],
            "message": eligibility["message"]
        }
    
    # Obtener límites del paquete
    package_limits = get_package_limits(package_identifier)
    entitlements = get_entitlements_from_package(package_identifier)
    
    # Crear datos simulados de RevenueCat
    mock_revenuecat_data = {
        "entitlements": {},
        "originalAppUserId": user_id,
        "latestExpirationDate": None
    }
    
    # Configurar entitlements según el paquete
    for entitlement in entitlements:
        mock_revenuecat_data["entitlements"][entitlement] = {
            "isActive": True,
            "expiresDate": None,
            "productIdentifier": package_limits.get("product_id", "unknown"),
            "periodType": package_identifier.replace("$rc_", "")
        }
    
    # Procesar la actualización de suscripción
    try:
        result = process_subscription_update(user_id, mock_revenuecat_data)
        
        return {
            "success": True,
            "state": PurchaseState.COMPLETED.value,
            "transaction_id": f"sim_{datetime.now().timestamp()}",
            "package_identifier": package_identifier,
            "entitlements": entitlements,
            "new_limits": package_limits,
            "updated_subscription": result
        }
    except Exception as e:
        return {
            "success": False,
            "state": PurchaseState.FAILED.value,
            "error": PurchaseError.UNKNOWN.value,
            "message": str(e)
        }


def restore_purchases(user_id: str) -> Dict:
    """Restaurar compras previas del usuario.
    
    Este es obligatorio por políticas de Apple/Google para que usuarios
    que reinstalen la app recuperen sus suscripciones activas.
    
    Args:
        user_id: ID del usuario
        
    Returns:
        Dict con resultado de la restauración
    """
    from saberlink.payments.subscription import validate_subscription
    
    try:
        # En un entorno real, esto llamaría a Purchases.restorePurchases()
        # Aquí validamos el estado actual desde nuestro almacenamiento
        current_sub = validate_subscription(user_id)
        
        if current_sub["subscription_expires"]:
            # Verificar si la suscripción aún está activa
            expiration_date = datetime.fromisoformat(current_sub["subscription_expires"])
            if expiration_date > datetime.now():
                return {
                    "success": True,
                    "restored": True,
                    "subscription": current_sub,
                    "message": "Suscripción restaurada exitosamente"
                }
            else:
                return {
                    "success": True,
                    "restored": False,
                    "subscription": current_sub,
                    "message": "Suscripción expirada"
                }
        else:
            return {
                "success": True,
                "restored": False,
                "message": "No hay suscripciones activas para restaurar"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": PurchaseError.UNKNOWN.value,
            "message": f"Error al restaurar compras: {str(e)}"
        }


def check_entitlement_status(user_id: str, entitlement: str) -> Dict:
    """Verificar si un usuario tiene un entitlement específico.
    
    Args:
        user_id: ID del usuario
        entitlement: ID del entitlement (ej: "pro")
        
    Returns:
        Dict con estado del entitlement
    """
    from saberlink.payments.subscription import validate_subscription
    from saberlink.payments.catalog import get_usage_limits_from_entitlements
    
    current_sub = validate_subscription(user_id)
    
    # Verificar si tiene el entitlement basado en su tier actual
    if entitlement == "pro" and current_sub["current_tier"] == "pro":
        return {
            "has_access": True,
            "entitlement": entitlement,
            "tier": current_sub["current_tier"],
            "subscription_expires": current_sub["subscription_expires"],
            "limits": get_usage_limits_from_entitlements({entitlement: {"isActive": True}})
        }
    
    return {
        "has_access": False,
        "entitlement": entitlement,
        "tier": current_sub["current_tier"],
        "limits": get_usage_limits_from_entitlements({})
    }


def handle_purchase_error(error: Dict) -> Dict:
    """Manejar diferentes tipos de errores de compra.
    
    Args:
        error: Dict con información del error
        
    Returns:
        Dict con error formateado para el usuario
    """
    error_code = error.get("code", "unknown")
    error_message = error.get("message", "Error desconocido")
    
    # Mapear errores a tipos conocidos
    error_mapping = {
        "USER_CANCELLED": {
            "type": PurchaseError.USER_CANCELLED.value,
            "user_message": "Cancelaste la compra",
            "recoverable": True
        },
        "PAYMENT_DECLINED": {
            "type": PurchaseError.PAYMENT_DECLINED.value,
            "user_message": "El pago fue declinado",
            "recoverable": True
        },
        "NETWORK_ERROR": {
            "type": PurchaseError.NETWORK_ERROR.value,
            "user_message": "Error de conexión. Intenta nuevamente.",
            "recoverable": True
        },
        "INVALID_PRODUCT": {
            "type": PurchaseError.INVALID_PRODUCT.value,
            "user_message": "Producto no disponible",
            "recoverable": False
        },
        "ALREADY_OWNED": {
            "type": PurchaseError.ALREADY_OWNED.value,
            "user_message": "Ya posees este producto",
            "recoverable": False
        },
        "PERMISSION_DENIED": {
            "type": PurchaseError.PERMISSION_DENIED.value,
            "user_message": "Permiso denegado para la compra",
            "recoverable": False
        }
    }
    
    mapped_error = error_mapping.get(error_code, {
        "type": PurchaseError.UNKNOWN.value,
        "user_message": error_message,
        "recoverable": True
    })
    
    return {
        "error": mapped_error["type"],
        "user_message": mapped_error["user_message"],
        "recoverable": mapped_error["recoverable"],
        "original_error": error
    }


def get_customer_info(user_id: str) -> Dict:
    """Obtener información completa del cliente (CustomerInfo).
    
    Esto incluye entitlements activos, fechas de expiración, etc.
    
    Args:
        user_id: ID del usuario
        
    Returns:
        Dict con información completa del cliente
    """
    from saberlink.payments.subscription import validate_subscription
    from saberlink.payments.catalog import get_usage_limits_from_entitlements
    
    current_sub = validate_subscription(user_id)
    
    # Construir entitlements activos
    active_entitlements = {}
    if current_sub["current_tier"] == "pro":
        active_entitlements["pro"] = {
            "isActive": True,
            "expiresDate": current_sub["subscription_expires"],
            "productIdentifier": "com.saberlink.app.pro_yearly",  # Default
            "periodType": "annual"
        }
    
    return {
        "originalAppUserId": user_id,
        "entitlements": {
            "all": active_entitlements,
            "active": active_entitlements
        },
        "latestExpirationDate": current_sub["subscription_expires"],
        "managementURL": None,  # URL para gestionar suscripción en la tienda
        "allPurchasedProductIdentifiers": [] if current_sub["current_tier"] == "free" else ["com.saberlink.app.pro_yearly"],
        "subscription": {
            "isActive": current_sub["current_tier"] == "pro",
            "expirationDate": current_sub["subscription_expires"]
        }
    }