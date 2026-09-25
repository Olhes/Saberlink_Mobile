import axios from "axios";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

const client = axios.create({ baseURL: API_BASE });

export async function runQuery({ entityId, rawTextProfile, topK }) {
  const { data } = await client.post("/query", {
    entity_id: entityId || null,
    raw_text_profile: rawTextProfile || null,
    top_k: topK,
  });
  return data;
}

export async function queryPdf({ file, topK }) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post("/query/pdf", form, {
    params: { top_k: topK },
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function queryPdfEnhanced({ file, topK, useCohere = true }) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post("/query/pdf/enhanced", form, {
    params: { top_k: topK, use_cohere: useCohere },
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

export function apiErrorMessage(err) {
  return err?.response?.data?.detail || err?.message || "Error desconocido";
}

export default client;
