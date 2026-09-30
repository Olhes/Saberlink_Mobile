import { useState, useEffect } from "react";
import { Purchases } from '@revenuecat/purchases-js';
import { apiErrorMessage, updateSubscription, getPurchasesOfferings, validatePurchaseEligibility, simulatePurchase, restorePurchases, syncCustomerInfo } from "../api/client";

function PricingCard({ package: pkg, isSelected, onSelect, currentUsage, purchasing }) {
  const { identifier, product, price_display, description } = pkg;
  const { pdf_uploads_per_month, text_queries_per_month } = product;
  
  return (
    <div 
      className={`rounded-xl border p-6 transition-all ${
        isSelected 
          ? "border-gold-500 bg-gold-500/10 shadow-lg shadow-gold-500/20" 
          : "border-gold-500/20 bg-ink-900/50 hover:border-gold-500/40"
      }`}
    >
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-xl font-semibold text-parchment-200">{description}</h3>
          <span className="text-lg font-bold text-gold-400">{price_display}</span>
        </div>
        <p className="text-sm text-parchment-200/60">Paquete: {identifier}</p>
      </div>
      
      <div className="space-y-3">
        <div className="flex items-center justify-between text-sm">
          <span className="text-parchment-200/70">Subidas de PDF/mes</span>
          <span className="font-mono text-gold-400">{pdf_uploads_per_month}</span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-parchment-200/70">Consultas de texto/mes</span>
          <span className="font-mono text-gold-400">{text_queries_per_month}</span>
        </div>
        
        {currentUsage && isSelected && (
          <div className="mt-4 pt-4 border-t border-gold-500/20">
            <div className="text-xs text-parchment-200/50 mb-2">Uso actual</div>
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-parchment-200/60">PDFs</span>
                <span className="text-parchment-200/80">
                  {currentUsage.pdf_uploads_used}/{currentUsage.pdf_uploads_limit}
                </span>
              </div>
              <div className="h-1.5 bg-ink-800 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-gold-500 transition-all"
                  style={{ 
                    width: `${(currentUsage.pdf_uploads_used / currentUsage.pdf_uploads_limit) * 100}%` 
                  }}
                />
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-parchment-200/60">Consultas</span>
                <span className="text-parchment-200/80">
                  {currentUsage.text_queries_used}/{currentUsage.text_queries_limit}
                </span>
              </div>
              <div className="h-1.5 bg-ink-800 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-gold-500 transition-all"
                  style={{ 
                    width: `${(currentUsage.text_queries_used / currentUsage.text_queries_limit) * 100}%` 
                  }}
                />
              </div>
            </div>
          </div>
        )}
      </div>
      
      <button
        onClick={() => onSelect(identifier)}
        disabled={purchasing}
        className={`mt-6 w-full rounded-lg px-4 py-2.5 text-sm font-medium transition-all ${
          isSelected
            ? "bg-gold-500 text-ink-950"
            : "bg-gold-500/20 text-gold-400 hover:bg-gold-500/30"
        } ${purchasing ? "opacity-50 cursor-not-allowed" : ""}`}
      >
        {purchasing ? "Procesando..." : isSelected ? "Plan actual" : "Seleccionar"}
      </button>
    </div>
  );
}

export default function PricingPage({ onClose, onPlanSelect }) {
  const [offerings, setOfferings] = useState(null);
  const [currentUsage, setCurrentUsage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedPackage, setSelectedPackage] = useState(null);
  const [purchasing, setPurchasing] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [revenueCatConfigured, setRevenueCatConfigured] = useState(false);

  const getUserId = () => {
    let userId = localStorage.getItem("saberlink_user_id");
    if (!userId) {
      userId = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      localStorage.setItem("saberlink_user_id", userId);
    }
    return userId;
  };

  useEffect(() => {
    const initializeRevenueCat = async () => {
      try {
        const apiKey = import.meta.env.VITE_REVENUECAT_PUBLIC_KEY;
        if (apiKey && apiKey !== "") {
          // Considerar configurado si la API key existe (incluso si es demo)
          setRevenueCatConfigured(true);
          
          try {
            await Purchases.configure(apiKey);
            const offeringsData = await Purchases.getOfferings();
            setOfferings(offeringsData);
            
            // Punto 4: Sincronización de estado en tiempo real
            // Listener para cambios en CustomerInfo
            Purchases.addCustomerInfoUpdateListener((customerInfo) => {
              const userId = getUserId();
              syncCustomerInfo(userId, customerInfo).then(result => {
                if (result.success) {
                  setCurrentUsage(result.updated_subscription);
                  // Determinar el paquete actual basado en entitlements
                  const activeEntitlements = customerInfo.entitlements.active;
                  if (activeEntitlements.pro && activeEntitlements.pro.isActive) {
                    const packageType = activeEntitlements.pro.periodType;
                    setSelectedPackage(packageType === "annual" ? "$rc_annual" : "$rc_monthly");
                  } else {
                    setSelectedPackage("free");
                  }
                }
              }).catch(err => {
                console.error("Error syncing customer info:", err);
              });
            });
          } catch (err) {
            console.warn("RevenueCat SDK initialization failed (using demo mode):", err);
            // SDK falló pero API key existe - usar modo demo pero con configuración activa
          }
        }
      } catch (err) {
        console.warn("RevenueCat not configured:", err);
        setRevenueCatConfigured(false);
      }
    };

    const loadData = async () => {
      try {
        const userId = getUserId();
        await initializeRevenueCat();
        
        const [offeringsResponse, usageResponse] = await Promise.all([
          getPurchasesOfferings(userId, "default"),
          fetch(`http://localhost:8000/usage/limits?user_id=${userId}`)
        ]);
        
        // Set offerings incluso si falla, para usar fallback
        if (offeringsResponse && offeringsResponse.success) {
          setOfferings(offeringsResponse);
        }
        
        if (usageResponse.ok) {
          const usageData = await usageResponse.json();
          setCurrentUsage(usageData);
          setSelectedPackage(usageData.tier || "free");
        } else {
          // Fallback usage si falla
          setCurrentUsage({
            tier: "free",
            pdf_uploads_used: 0,
            pdf_uploads_limit: 5,
            text_queries_used: 0,
            text_queries_limit: 20
          });
          setSelectedPackage("free");
        }
      } catch (err) {
        console.error("Error loading pricing data:", err);
        // No setear error para permitir fallback UI
        setError(null);
        setCurrentUsage({
          tier: "free",
          pdf_uploads_used: 0,
          pdf_uploads_limit: 5,
          text_queries_used: 0,
          text_queries_limit: 20
        });
        setSelectedPackage("free");
      } finally {
        setLoading(false);
      }
    };
    
    loadData();
    
    // Cleanup listener on unmount
    return () => {
      if (revenueCatConfigured) {
        Purchases.removeCustomerInfoUpdateListener();
      }
    };
  }, []);

  const handlePackageSelect = async (packageIdentifier) => {
    setPurchasing(true);
    try {
      const userId = getUserId();
      
      const eligibility = await validatePurchaseEligibility(userId, packageIdentifier);
      if (!eligibility.eligible) {
        setError(eligibility.message || "No puedes comprar este paquete");
        setPurchasing(false);
        return;
      }
      
      if (revenueCatConfigured && offerings) {
        // El SDK de JavaScript web no tiene logIn - se usa configure una vez
        // await Purchases.logIn(userId); // Eliminado - no existe en web SDK
        
        const currentOffering = offerings.current;
        if (!currentOffering) {
          // Si no hay ofertas reales, usar modo demo
          console.warn("No hay ofertas reales en RevenueCat, usando modo demo");
          if (window.confirm(`¿Quieres suscribirte al paquete ${packageIdentifier}? (Modo demo - SDK configurado pero sin ofertas)`)) {
            const result = await simulatePurchase(userId, packageIdentifier);
            
            if (result.success) {
              setCurrentUsage(result.updated_subscription);
              setSelectedPackage(packageIdentifier);
              
              if (onPlanSelect) onPlanSelect(packageIdentifier);
            } else {
              setError(result.message || "Error en la compra simulada");
            }
          }
          setPurchasing(false);
          return;
        }
        
        const packageToPurchase = currentOffering.availablePackages.find(
          pkg => pkg.identifier === packageIdentifier
        );
        
        if (!packageToPurchase) {
          throw new Error("No se encontró el paquete de suscripción");
        }
        
        const { customerInfo } = await Purchases.purchasePackage(packageToPurchase);
        
        const revenueCatData = {
          entitlements: customerInfo.entitlements,
          originalAppUserId: customerInfo.originalAppUserId,
          latestExpirationDate: customerInfo.latestExpirationDate
        };
        
        const response = await updateSubscription(userId, revenueCatData);
        setCurrentUsage(response);
        setSelectedPackage(packageIdentifier);
        
        if (onPlanSelect) onPlanSelect(packageIdentifier);
      } else {
        if (window.confirm(`¿Quieres suscribirte al paquete ${packageIdentifier}? (Modo demo - SDK no configurado)`)) {
          const result = await simulatePurchase(userId, packageIdentifier);
          
          if (result.success) {
            setCurrentUsage(result.updated_subscription);
            setSelectedPackage(packageIdentifier);
            
            if (onPlanSelect) onPlanSelect(packageIdentifier);
          } else {
            setError(result.message || "Error en la compra simulada");
          }
        }
      }
    } catch (err) {
      if (!err.userCancelled) {
        setError(apiErrorMessage(err));
      }
    } finally {
      setPurchasing(false);
    }
  };

  const handleRestorePurchases = async () => {
    setRestoring(true);
    try {
      const userId = getUserId();
      const result = await restorePurchases(userId);
      
      if (result.success && result.restored) {
        setCurrentUsage(result.subscription);
        setError(null);
      } else {
        setError(result.message || "No se encontraron compras para restaurar");
      }
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setRestoring(false);
    }
  };

  const handleDowngradeToFree = async () => {
    try {
      const userId = getUserId();
      const response = await fetch("http://localhost:8000/usage/subscription", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          revenuecat_data: { entitlements: {} }
        })
      });
      
      if (!response.ok) throw new Error("Error actualizando suscripción");
      
      const updatedUsage = await response.json();
      setCurrentUsage(updatedUsage);
      setSelectedPackage("free");
      
      if (onPlanSelect) onPlanSelect("free");
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-gold-500/25 border-t-gold-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-copper-500/30 bg-copper-500/10 px-4 py-3 text-sm text-copper-400">
        {error}
      </div>
    );
  }

  const packages = offerings?.packages || [];
  const currentPackage = packages.find(pkg => pkg.identifier === selectedPackage) || null;

  // Fallback paquetes demo si no hay offerings del backend
  const demoPackages = [
    {
      identifier: "$rc_monthly",
      product: {
        pdf_uploads_per_month: 10,
        text_queries_per_month: 50
      },
      price_display: "$9.99/mes",
      description: "Plan Mensual"
    },
    {
      identifier: "$rc_annual",
      product: {
        pdf_uploads_per_month: 25,
        text_queries_per_month: 150
      },
      price_display: "$89.99/año",
      description: "Plan Anual"
    }
  ];

  // Determinar qué paquetes mostrar
  const displayPackages = packages.length > 0 ? packages : demoPackages;

  // Asegurar que los paquetes tengan la estructura correcta
  const safePackages = displayPackages.map(pkg => ({
    identifier: pkg.identifier,
    product: pkg.product || {
      pdf_uploads_per_month: 10,
      text_queries_per_month: 50
    },
    price_display: pkg.price_display || "$9.99/mes",
    description: pkg.description || "Plan Standard"
  }));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-parchment-200">Planes y Precios</h2>
          <p className="mt-1 text-sm text-parchment-200/60">
            Elige el plan que mejor se adapte a tus necesidades de investigación
          </p>
        </div>
        <button
          onClick={onClose}
          className="rounded-lg px-3 py-1.5 text-sm text-parchment-200/60 hover:text-parchment-200 hover:bg-gold-500/10"
        >
          ✕
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {safePackages.map((pkg) => (
          <PricingCard
            key={pkg.identifier}
            package={pkg}
            isSelected={selectedPackage === pkg.identifier}
            onSelect={handlePackageSelect}
            currentUsage={currentUsage}
            purchasing={purchasing}
          />
        ))}
      </div>

      <div className="flex gap-3">
        <button
          onClick={handleRestorePurchases}
          disabled={restoring}
          className="rounded-lg border border-gold-500/30 bg-gold-500/10 px-4 py-2 text-sm text-gold-400 hover:bg-gold-500/20 transition-all disabled:opacity-50"
        >
          {restoring ? "Restaurando..." : "Restaurar Compras"}
        </button>
        
        {selectedPackage !== "free" && (
          <button
            onClick={handleDowngradeToFree}
            className="rounded-lg border border-copper-500/30 bg-copper-500/10 px-4 py-2 text-sm text-copper-400 hover:bg-copper-500/20 transition-all"
          >
            Cancelar Suscripción
          </button>
        )}
      </div>

      {purchasing && (
        <div className="flex items-center justify-center gap-3 py-4">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-gold-500/25 border-t-gold-400" />
          <span className="text-sm text-parchment-200/60">Procesando suscripción...</span>
        </div>
      )}

      <div className="rounded-lg border border-gold-500/10 bg-ink-900/30 px-4 py-3 text-xs text-parchment-200/40">
        <p>💡 Los límites se reinician cada mes. Puedes cambiar de plan en cualquier momento.</p>
        <p className="mt-1">
          🔒 Estado RevenueCat:{" "}
          <span className={revenueCatConfigured ? "text-verdigris-400" : "text-copper-400"}>
            {revenueCatConfigured ? "✅ SDK configurado (producción)" : "⚠️ Modo demo (falta API key)"}
          </span>
        </p>
        {!revenueCatConfigured && (
          <p className="mt-1 text-copper-400/70">
            💡 Para usar compras reales, configura VITE_REVENUECAT_PUBLIC_KEY en frontend/.env
          </p>
        )}
      </div>
    </div>
  );
}