"""Webhooks y Sincronización con RevenueCat

Este módulo maneja:
- Webhooks del servidor de RevenueCat
- Sincronización de estado en tiempo real
- Eventos de suscripción (renovación, cancelación, reembolso)
- Validación de accesos desde el backend

Sigue la arquitectura modular: puede eliminarse sin romper el core.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from enum import Enum
from datetime import datetime
import json
import hmac
import hashlib


class WebhookEvent(Enum):
    """Tipos de eventos de webhook de RevenueCat."""
    SUBSCRIPTION_STARTED = "subscription_started"
    SUBSCRIPTION_RENEWED = "subscription_renewed"
    SUBSCRIPTION_EXPIRED = "subscription_expired"
    SUBSCRIPTION_CANCELLED = "subscription_cancelled"
    SUBSCRIPTION_PAUSED = "subscription_paused"
    SUBSCRIPTION_RESUMED = "subscription_resumed"
    NON_SUBSCRIPTION_PURCHASE = "non_subscription_purchase"
    IN_APP_PURCHASE = "in_app_purchase"
    TEST = "test"


class WebhookPayload:
    """Payload de webhook de RevenueCat."""
    
    def __init__(self, event_type: str, data: Dict):
        self.event_type = event_type
        self.data = data
        self.app_user_id = data.get("app_user_id")
        self.event_id = data.get("event_id")
        self.product_id = data.get("product_id")
        self.entitlement_id = data.get("entitlement_id")
        self.price = data.get("price")
        self.currency = data.get("currency")
        self.expiration_date = data.get("expiration_date")
        self.is_in_intro_offer = data.get("is_in_intro_offer", False)
        self.is_trial = data.get("is_trial", False)
    
    def to_dict(self) -> Dict:
        """Convertir a diccionario."""
        return {
            "event_type": self.event_type,
            "app_user_id": self.app_user_id,
            "event_id": self.event_id,
            "product_id": self.product_id,
            "entitlement_id": self.entitlement_id,
            "price": self.price,
            "currency": self.currency,
            "expiration_date": self.expiration_date,
            "is_in_intro_offer": self.is_in_intro_offer,
            "is_trial": self.is_trial,
            "data": self.data
        }


def verify_webhook_signature(payload: bytes, signature: str, webhook_secret: str) -> bool:
    """Verificar la firma del webhook de RevenueCat.
    
    Args:
        payload: El cuerpo del webhook como bytes
        signature: La firma recibida en el header X-Signature
        webhook_secret: El secreto del webhook configurado en RevenueCat
        
    Returns:
        True si la firma es válida, False en caso contrario
    """
    try:
        expected_signature = hmac.new(
            webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # RevenueCat usa el formato "sha256=<signature>"
        if signature.startswith("sha256="):
            signature = signature[7:]
        
        return hmac.compare_digest(expected_signature, signature)
    except Exception:
        return False


def process_webhook_event(event_type: str, event_data: Dict) -> Dict:
    """Procesar un evento de webhook de RevenueCat.
    
    Args:
        event_type: Tipo de evento (subscription_started, etc.)
        event_data: Datos del evento
        
    Returns:
        Dict con resultado del procesamiento
    """
    webhook = WebhookPayload(event_type, event_data)
    
    try:
        # Procesar según el tipo de evento
        if event_type == WebhookEvent.SUBSCRIPTION_STARTED.value:
            return _handle_subscription_started(webhook)
        elif event_type == WebhookEvent.SUBSCRIPTION_RENEWED.value:
            return _handle_subscription_renewed(webhook)
        elif event_type == WebhookEvent.SUBSCRIPTION_EXPIRED.value:
            return _handle_subscription_expired(webhook)
        elif event_type == WebhookEvent.SUBSCRIPTION_CANCELLED.value:
            return _handle_subscription_cancelled(webhook)
        elif event_type == WebhookEvent.SUBSCRIPTION_PAUSED.value:
            return _handle_subscription_paused(webhook)
        elif event_type == WebhookEvent.SUBSCRIPTION_RESUMED.value:
            return _handle_subscription_resumed(webhook)
        elif event_type == WebhookEvent.NON_SUBSCRIPTION_PURCHASE.value:
            return _handle_non_subscription_purchase(webhook)
        elif event_type == WebhookEvent.TEST.value:
            return _handle_test_event(webhook)
        else:
            return {
                "success": False,
                "error": "unknown_event_type",
                "message": f"Tipo de evento desconocido: {event_type}"
            }
    except Exception as e:
        return {
            "success": False,
            "error": "processing_error",
            "message": str(e)
        }


def _handle_subscription_started(webhook: WebhookPayload) -> Dict:
    """Manejar inicio de suscripción."""
    from saberlink.payments.subscription import process_subscription_update
    
    # Construir datos de RevenueCat simulados
    revenuecat_data = {
        "entitlements": {
            webhook.entitlement_id or "pro": {
                "isActive": True,
                "expiresDate": webhook.expiration_date,
                "productIdentifier": webhook.product_id,
                "periodType": "unknown"
            }
        },
        "originalAppUserId": webhook.app_user_id,
        "latestExpirationDate": webhook.expiration_date
    }
    
    # Actualizar suscripción
    result = process_subscription_update(webhook.app_user_id, revenuecat_data)
    
    return {
        "success": True,
        "event": "subscription_started",
        "user_id": webhook.app_user_id,
        "updated_subscription": result
    }


def _handle_subscription_renewed(webhook: WebhookPayload) -> Dict:
    """Manejar renovación de suscripción."""
    from saberlink.payments.subscription import process_subscription_update
    
    # Similar a subscription_started pero con renovación
    revenuecat_data = {
        "entitlements": {
            webhook.entitlement_id or "pro": {
                "isActive": True,
                "expiresDate": webhook.expiration_date,
                "productIdentifier": webhook.product_id,
                "periodType": "renewed"
            }
        },
        "originalAppUserId": webhook.app_user_id,
        "latestExpirationDate": webhook.expiration_date
    }
    
    result = process_subscription_update(webhook.app_user_id, revenuecat_data)
    
    return {
        "success": True,
        "event": "subscription_renewed",
        "user_id": webhook.app_user_id,
        "updated_subscription": result
    }


def _handle_subscription_expired(webhook: WebhookPayload) -> Dict:
    """Manejar expiración de suscripción."""
    from saberlink.payments.subscription import process_subscription_update
    
    # Downgrade a free tier
    revenuecat_data = {
        "entitlements": {},
        "originalAppUserId": webhook.app_user_id,
        "latestExpirationDate": webhook.expiration_date
    }
    
    result = process_subscription_update(webhook.app_user_id, revenuecat_data)
    
    return {
        "success": True,
        "event": "subscription_expired",
        "user_id": webhook.app_user_id,
        "updated_subscription": result
    }


def _handle_subscription_cancelled(webhook: WebhookPayload) -> Dict:
    """Manejar cancelación de suscripción."""
    from saberlink.payments.subscription import process_subscription_update
    
    # Downgrade a free tier inmediatamente o al final del período
    revenuecat_data = {
        "entitlements": {},
        "originalAppUserId": webhook.app_user_id,
        "latestExpirationDate": webhook.expiration_date
    }
    
    result = process_subscription_update(webhook.app_user_id, revenuecat_data)
    
    return {
        "success": True,
        "event": "subscription_cancelled",
        "user_id": webhook.app_user_id,
        "updated_subscription": result
    }


def _handle_subscription_paused(webhook: WebhookPayload) -> Dict:
    """Manejar pausa de suscripción."""
    # Para pausas, podríamos mantener el acceso pero no contar periodo
    return {
        "success": True,
        "event": "subscription_paused",
        "user_id": webhook.app_user_id,
        "message": "Suscripción pausada temporalmente"
    }


def _handle_subscription_resumed(webhook: WebhookPayload) -> Dict:
    """Manejar reanudación de suscripción."""
    from saberlink.payments.subscription import process_subscription_update
    
    # Reactivar la suscripción
    revenuecat_data = {
        "entitlements": {
            webhook.entitlement_id or "pro": {
                "isActive": True,
                "expiresDate": webhook.expiration_date,
                "productIdentifier": webhook.product_id,
                "periodType": "resumed"
            }
        },
        "originalAppUserId": webhook.app_user_id,
        "latestExpirationDate": webhook.expiration_date
    }
    
    result = process_subscription_update(webhook.app_user_id, revenuecat_data)
    
    return {
        "success": True,
        "event": "subscription_resumed",
        "user_id": webhook.app_user_id,
        "updated_subscription": result
    }


def _handle_non_subscription_purchase(webhook: WebhookPayload) -> Dict:
    """Manejar compra no recurrente (consumable)."""
    return {
        "success": True,
        "event": "non_subscription_purchase",
        "user_id": webhook.app_user_id,
        "message": "Compra no recurrente procesada"
    }


def _handle_test_event(webhook: WebhookPayload) -> Dict:
    """Manejar evento de prueba."""
    return {
        "success": True,
        "event": "test",
        "user_id": webhook.app_user_id,
        "message": "Evento de prueba recibido correctamente"
    }


def sync_customer_info(user_id: str, customer_info: Dict) -> Dict:
    """Sincronizar información del cliente desde el SDK.
    
    Args:
        user_id: ID del usuario
        customer_info: Información del cliente desde RevenueCat SDK
        
    Returns:
        Dict con resultado de la sincronización
    """
    from saberlink.payments.subscription import process_subscription_update
    
    try:
        # Extraer entitlements activos
        entitlements = customer_info.get("entitlements", {}).get("active", {})
        
        # Construir datos de RevenueCat
        revenuecat_data = {
            "entitlements": entitlements,
            "originalAppUserId": customer_info.get("originalAppUserId", user_id),
            "latestExpirationDate": customer_info.get("latestExpirationDate")
        }
        
        # Actualizar suscripción
        result = process_subscription_update(user_id, revenuecat_data)
        
        return {
            "success": True,
            "synced": True,
            "user_id": user_id,
            "updated_subscription": result
        }
    except Exception as e:
        return {
            "success": False,
            "error": "sync_error",
            "message": str(e)
        }


def validate_access_from_server(user_id: str, required_entitlement: str = "pro") -> Dict:
    """Validar acceso desde el servidor (para web backend).
    
    Útil para validar accesos en tu base de datos web sin que el usuario
    tenga la app móvil abierta.
    
    Args:
        user_id: ID del usuario
        required_entitlement: Entitlement requerido (default: "pro")
        
    Returns:
        Dict con resultado de validación
    """
    from saberlink.payments.subscription import validate_subscription
    from saberlink.payments.catalog import get_usage_limits_from_entitlements
    
    try:
        current_sub = validate_subscription(user_id)
        
        # Verificar si tiene el entitlement requerido
        if required_entitlement == "pro" and current_sub["current_tier"] == "pro":
            # Verificar que la suscripción no esté expirada
            if current_sub["subscription_expires"]:
                expiration_date = datetime.fromisoformat(current_sub["subscription_expires"])
                if expiration_date < datetime.now():
                    return {
                        "has_access": False,
                        "reason": "subscription_expired",
                        "subscription": current_sub
                    }
            
            # Tiene acceso válido
            limits = get_usage_limits_from_entitlements({required_entitlement: {"isActive": True}})
            
            return {
                "has_access": True,
                "entitlement": required_entitlement,
                "subscription": current_sub,
                "limits": limits
            }
        
        # No tiene el entitlement requerido
        return {
            "has_access": False,
            "reason": "missing_entitlement",
            "required_entitlement": required_entitlement,
            "subscription": current_sub
        }
        
    except Exception as e:
        return {
            "has_access": False,
            "error": "validation_error",
            "message": str(e)
        }


def get_webhook_history(user_id: str, limit: int = 10) -> List[Dict]:
    """Obtener historial de webhooks para un usuario.
    
    Args:
        user_id: ID del usuario
        limit: Número máximo de eventos a retornar
        
    Returns:
        Lista de eventos de webhook procesados
    """
    from saberlink import config
    from pathlib import Path
    
    webhook_file = config.PROCESSED_DIR / "webhook_history.json"
    
    try:
        if webhook_file.exists():
            data = json.loads(webhook_file.read_text())
            user_events = data.get(user_id, [])
            return user_events[-limit:] if user_events else []
        return []
    except Exception:
        return []


def log_webhook_event(user_id: str, event_data: Dict) -> bool:
    """Registrar un evento de webhook en el historial.
    
    Args:
        user_id: ID del usuario
        event_data: Datos del evento a registrar
        
    Returns:
        True si se registró exitosamente
    """
    from saberlink import config
    from pathlib import Path
    
    webhook_file = config.PROCESSED_DIR / "webhook_history.json"
    
    try:
        if not webhook_file.exists():
            webhook_file.parent.mkdir(parents=True, exist_ok=True)
            webhook_file.write_text("{}")
        
        data = json.loads(webhook_file.read_text())
        
        if user_id not in data:
            data[user_id] = []
        
        event_data["timestamp"] = datetime.now().isoformat()
        data[user_id].append(event_data)
        
        # Mantener solo los últimos 50 eventos por usuario
        if len(data[user_id]) > 50:
            data[user_id] = data[user_id][-50:]
        
        webhook_file.write_text(json.dumps(data, indent=2))
        return True
    except Exception:
        return False