import { useState, useEffect } from "react";
import { apiErrorMessage } from "../api/client";

function PricingCard({ tier, isSelected, onSelect, currentUsage }) {
  const { name, description, pdf_uploads_per_month, text_queries_per_month } = tier;
  const tierKey = name.toLowerCase().replace(" ", "_").replace("pro_", "");
  
  return (
    <div 
      className={`rounded-xl border p-6 transition-all ${
        isSelected 
          ? "border-gold-500 bg-gold-500/10 shadow-lg shadow-gold-500/20" 
          : "border-gold-500/20 bg-ink-900/50 hover:border-gold-500/40"
      }`}
    >
      <div className="mb-4">
        <h3 className="text-xl font-semibold text-parchment-200">{name}</h3>
        <p className="mt-1 text-sm text-parchment-200/60">{description}</p>
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
        
        {currentUsage && tierKey === currentUsage.tier && (
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
        onClick={() => onSelect(tierKey)}
        className={`mt-6 w-full rounded-lg px-4 py-2.5 text-sm font-medium transition-all ${
          isSelected
            ? "bg-gold-500 text-ink-900"
            : "bg-gold-500/20 text-gold-400 hover:bg-gold-500/30"
        }`}
      >
        {isSelected ? "Plan actual" : "Seleccionar plan"}
      </button>
    </div>
  );
}

export default function PricingPage({ onClose, onPlanSelect }) {
  const [tiers, setTiers] = useState(null);
  const [currentUsage, setCurrentUsage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedTier, setSelectedTier] = useState(null);
  const [purchasing, setPurchasing] = useState(false);

  // Get user ID from localStorage or generate one
  const getUserId = () => {
    let userId = localStorage.getItem("saberlink_user_id");
    if (!userId) {
      userId = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      localStorage.setItem("saberlink_user_id", userId);
    }
    return userId;
  };

  useEffect(() => {
    const loadData = async () => {
      try {
        const userId = getUserId();
        
        // Fetch tiers and current usage in parallel
        const [tiersResponse, usageResponse] = await Promise.all([
          fetch("http://localhost:8000/usage/tiers"),
          fetch(`http://localhost:8000/usage/limits?user_id=${userId}`)
        ]);
        
        if (!tiersResponse.ok || !usageResponse.ok) {
          throw new Error("Error loading pricing data");
        }
        
        const tiersData = await tiersResponse.json();
        const usageData = await usageResponse.json();
        
        setTiers(tiersData);
        setCurrentUsage(usageData);
        setSelectedTier(usageData.tier);
      } catch (err) {
        setError(apiErrorMessage(err));
      } finally {
        setLoading(false);
      }
    };
    
    loadData();
  }, []);

  const handleTierSelect = async (tierKey) => {
    if (tierKey === "free") {
      // Downgrade to free is immediate
      try {
        const userId = getUserId();
        const response = await fetch("http://localhost:8000/usage/subscription", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: userId,
            revenuecat_data: { entitlements: {} } // Empty entitlements = free tier
          })
        });
        
        if (!response.ok) throw new Error("Error updating subscription");
        
        const updatedUsage = await response.json();
        setCurrentUsage(updatedUsage);
        setSelectedTier("free");
        
        if (onPlanSelect) onPlanSelect("free");
      } catch (err) {
        setError(apiErrorMessage(err));
      }
      return;
    }
    
    // For paid tiers, trigger RevenueCat purchase flow
    setPurchasing(true);
    try {
      // This would trigger the RevenueCat purchase flow
      // For now, we'll simulate it with a confirmation
      if (window.confirm(`¿Quieres suscribirte al plan ${tierKey}? (Simulación - en producción esto abriría RevenueCat)`)) {
        const userId = getUserId();
        
        // Simulate successful purchase
        const mockRevenueCatData = {
          entitlements: {
            pro: {
              isActive: true,
              expiresDate: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(), // 30 days
              productIdentifier: tierKey === "pro_yearly" ? "com.saberlink.pro.yearly" : "com.saberlink.pro.monthly"
            }
          }
        };
        
        const response = await fetch("http://localhost:8000/usage/subscription", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: userId,
            revenuecat_data: mockRevenueCatData
          })
        });
        
        if (!response.ok) throw new Error("Error processing subscription");
        
        const updatedUsage = await response.json();
        setCurrentUsage(updatedUsage);
        setSelectedTier(tierKey);
        
        if (onPlanSelect) onPlanSelect(tierKey);
      }
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setPurchasing(false);
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

  const tierArray = Object.entries(tiers || {}).map(([key, value]) => ({
    key,
    ...value
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
        {tierArray.map((tier) => (
          <PricingCard
            key={tier.key}
            tier={tier}
            isSelected={selectedTier === tier.key}
            onSelect={handleTierSelect}
            currentUsage={currentUsage}
          />
        ))}
      </div>

      {purchasing && (
        <div className="flex items-center justify-center gap-3 py-4">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-gold-500/25 border-t-gold-400" />
          <span className="text-sm text-parchment-200/60">Procesando suscripción...</span>
        </div>
      )}

      <div className="rounded-lg border border-gold-500/10 bg-ink-900/30 px-4 py-3 text-xs text-parchment-200/40">
        <p>💡 Los límites se reinician cada mes. Puedes cambiar de plan en cualquier momento.</p>
      </div>
    </div>
  );
}