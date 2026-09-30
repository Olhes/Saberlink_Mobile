import axios from "axios";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

const client = axios.create({ baseURL: API_BASE });

export async function runQuery({ entityId, rawTextProfile, topK, userId }) {
  const { data } = await client.post("/query", {
    entity_id: entityId || null,
    raw_text_profile: rawTextProfile || null,
    top_k: topK,
    user_id: userId || null,
  });
  return data;
}

export async function queryPdf({ file, topK, userId }) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post("/query/pdf", form, {
    params: { top_k: topK, user_id: userId || null },
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function queryPdfEnhanced({ file, topK, useCohere = true, userId }) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post("/query/pdf/enhanced", form, {
    params: { top_k: topK, use_cohere: useCohere, user_id: userId || null },
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function fetchGraph({ entityId, topK }) {
  const { data } = await client.get("/graph", {
    params: { entity_id: entityId, top_k: topK },
  });
  return data;
}

export async function searchEntities({ type, q, limit = 8 } = {}) {
  const { data } = await client.get("/entities", {
    params: { type, q, limit },
  });
  return data;
}

export async function fetchLegend() {
  const { data } = await client.get("/meta/legend");
  return data;
}

export async function fetchUsageLimits(userId) {
  const { data } = await client.get("/usage/limits", {
    params: { user_id: userId }
  });
  return data;
}

export async function fetchSubscriptionTiers() {
  const { data } = await client.get("/usage/tiers");
  return data;
}

export async function updateSubscription(userId, revenuecatData) {
  const { data } = await client.post("/usage/subscription", {
    user_id: userId,
    revenuecat_data: revenuecatData
  });
  return data;
}

export async function validatePdfUpload(userId) {
  const { data } = await client.post("/usage/validate-pdf", null, {
    params: { user_id: userId }
  });
  return data;
}

export async function validateTextQuery(userId) {
  const { data } = await client.post("/usage/validate-text", null, {
    params: { user_id: userId }
  });
  return data;
}

// Punto 2: Catálogo de productos
export async function getPurchasesOfferings(userId, offeringId = "default") {
  const { data } = await client.get("/purchases/offerings", {
    params: { user_id: userId, offering_id: offeringId }
  });
  return data;
}

export async function validatePurchaseEligibility(userId, packageIdentifier) {
  const { data } = await client.post("/purchases/validate-eligibility", null, {
    params: { user_id: userId, package_identifier: packageIdentifier }
  });
  return data;
}

export async function simulatePurchase(userId, packageIdentifier) {
  const { data } = await client.post("/purchases/simulate", null, {
    params: { user_id: userId, package_identifier: packageIdentifier }
  });
  return data;
}

export async function restorePurchases(userId) {
  const { data } = await client.post("/purchases/restore", null, {
    params: { user_id: userId }
  });
  return data;
}

export async function checkEntitlement(userId, entitlement = "pro") {
  const { data } = await client.get("/purchases/entitlement", {
    params: { user_id: userId, entitlement }
  });
  return data;
}

export async function getCustomerInfo(userId) {
  const { data } = await client.get("/purchases/customer-info", {
    params: { user_id: userId }
  });
  return data;
}

// Punto 4: Webhooks y sincronización
export async function syncCustomerInfo(userId, customerInfo) {
  const { data } = await client.post("/sync/customer-info", customerInfo, {
    params: { user_id: userId }
  });
  return data;
}

export async function validateAccessServer(userId, requiredEntitlement = "pro") {
  const { data } = await client.get("/server/validate-access", {
    params: { user_id: userId, required_entitlement }
  });
  return data;
}

export function apiErrorMessage(err) {
  return err?.response?.data?.detail || err?.message || "Error desconocido";
}

export default client;
