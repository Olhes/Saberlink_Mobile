import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import * as DocumentPicker from "expo-document-picker";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";
import AsyncStorage from "@react-native-async-storage/async-storage";
import axios from "axios";

const API_BASE = process.env.EXPO_PUBLIC_API_BASE || "http://localhost:8000";
const PROJECT_ID = "mi-investigacion";
const REVENUECAT_KEY = process.env.EXPO_PUBLIC_REVENUECAT_ANDROID_KEY;
const colors = {
  ink: "#101513",
  panel: "#18221e",
  panel2: "#202d27",
  paper: "#f5f0e4",
  muted: "#9ea99b",
  gold: "#d5a94d",
  mint: "#8fbe9d",
  copper: "#db8662",
  line: "#334139",
};

const api = axios.create({ baseURL: API_BASE, timeout: 120000 });
const demoResult = {
  source: { id: "NEED-001", type: "NEED", official: true },
  meta: { elapsed_seconds: 0.8, total_candidates_scored: 18 },
  results: [
    {
      target: { id: "PRJ-014", type: "PRJ" },
      relevance: { score: 0.91, label: "alta", breakdown: {} },
      explanation: "Conecta directamente con la necesidad consultada y comparte el dominio de investigación.",
      evidence: [{ file: "projects.csv", id: "PRJ-014", field: "problem_statement", snippet: "Sistemas adaptativos para mejorar el aprendizaje universitario." }],
    },
    {
      target: { id: "INV-032", type: "INV" },
      relevance: { score: 0.76, label: "media", breakdown: {} },
      explanation: "Aporta experiencia metodológica relacionada.",
      evidence: [{ file: "researchers.csv", id: "INV-032", field: "expertise", snippet: "Inteligencia artificial y analítica del aprendizaje." }],
    },
    {
      target: { id: "GRP-009", type: "GRP" },
      relevance: { score: 0.62, label: "media", breakdown: {} },
      explanation: "Grupo con capacidades cercanas al tema.",
      evidence: [],
    },
  ],
  opportunities: [{ type: "COLABORACION", priority: "alta", opportunity: "Explorar una colaboración con el proyecto conectado.", reason: "La evidencia muestra un dominio común.", related_entities: ["PRJ-014"] }],
  graph: {
    source_id: "NEED-001",
    nodes: [
      { id: "NEED-001", label: "IA en educación", type_label: "Necesidad", color: colors.gold, role: "source" },
      { id: "PRJ-014", label: "Aprendizaje adaptativo", type_label: "Proyecto", color: colors.mint, role: "result" },
      { id: "INV-032", label: "Analítica educativa", type_label: "Investigador", color: colors.copper, role: "result" },
      { id: "GRP-009", label: "IA aplicada", type_label: "Grupo", color: "#9ca3af", role: "result" },
    ],
    edges: [],
  },
};

function errorText(error) {
  return error?.response?.data?.detail || error?.message || "No se pudo completar la consulta";
}

async function queryApi(mode, value, topK, userId) {
  if (mode === "library") {
    const { data } = await api.post(`/projects/${PROJECT_ID}/query`, { query: value, top_k: topK, user_id: userId });
    return data;
  }
  if (mode === "pdf") {
    const form = new FormData();
    form.append("file", { uri: value.uri, name: value.name || "document.pdf", type: "application/pdf" });
    const { data } = await api.post("/query/pdf", form, { params: { top_k: topK, user_id: userId } });
    return data;
  }
  const body = mode === "id"
    ? { entity_id: value, top_k: topK, user_id: userId }
    : { raw_text_profile: { title: value.slice(0, 80), description: value }, top_k: topK, user_id: userId };
  const { data } = await api.post("/query", body);
  return data;
}

function Mark() {
  return <View style={styles.mark}><View style={styles.markDot} /><View style={[styles.markDot, styles.markDotTwo]} /><View style={[styles.markDot, styles.markDotThree]} /></View>;
}

function Chip({ children, active, onPress }) {
  return <Pressable onPress={onPress} style={[styles.chip, active && styles.chipActive]}><Text style={[styles.chipText, active && styles.chipTextActive]}>{children}</Text></Pressable>;
}

function Header({ onPaywall, usageData }) {
  return <View style={styles.header}><View style={styles.brand}><Mark /><View><Text style={styles.brandName}>SaberLink</Text><Text style={styles.brandSub}>tu atlas de conocimiento</Text></View></View><View style={styles.headerRight}>{usageData && <View style={styles.usageBadge}><Text style={styles.usageText}>{usageData.pdf_uploads_used}/{usageData.pdf_uploads_limit} PDFs</Text></View>}<Pressable onPress={onPaywall} style={styles.proButton}><Text style={styles.proText}>PRO</Text></Pressable></View></View>;
}

function SearchBox({ onSearch, onLibraryUpload, documents, loading, libraryLoading }) {
  const [mode, setMode] = useState("id");
  const [value, setValue] = useState("NEED-001");
  const [file, setFile] = useState(null);
  const [topK, setTopK] = useState(8);
  const [libraryQuery, setLibraryQuery] = useState("");

  async function chooseFile() {
    const picked = await DocumentPicker.getDocumentAsync({ type: "application/pdf", copyToCacheDirectory: true });
    if (!picked.canceled) { setFile(picked.assets[0]); setValue(picked.assets[0].name); }
  }

  async function chooseLibraryFiles() {
    const picked = await DocumentPicker.getDocumentAsync({ type: "application/pdf", multiple: true, copyToCacheDirectory: true });
    if (!picked.canceled) onLibraryUpload(picked.assets);
  }

  async function submit() {
    if (mode === "pdf" && !file) return Alert.alert("Falta el documento", "Elige un PDF para analizarlo.");
    if (mode === "library") {
      if (!libraryQuery.trim()) return Alert.alert("Falta la pregunta", "Escribe qué quieres encontrar en tus PDFs.");
      onSearch(mode, libraryQuery.trim(), topK);
      return;
    }
    if (!value.trim()) return;
    onSearch(mode, mode === "pdf" ? file : value.trim(), topK);
  }

  return <View style={styles.panel}>
    <Text style={styles.eyebrow}>NUEVA EXPLORACION</Text>
    <View style={styles.chipRow}><Chip active={mode === "id"} onPress={() => setMode("id")}>ID</Chip><Chip active={mode === "text"} onPress={() => setMode("text")}>Texto</Chip><Chip active={mode === "pdf"} onPress={() => setMode("pdf")}>PDF temporal</Chip><Chip active={mode === "library"} onPress={() => setMode("library")}>Biblioteca</Chip></View>
    {mode === "pdf" ? <Pressable onPress={chooseFile} style={styles.fileBox}><Text style={styles.fileTitle}>{file ? file.name : "Elegir un PDF"}</Text><Text style={styles.fileHint}>Consulta temporal, no se guarda</Text></Pressable> : mode === "library" ? <><Pressable onPress={chooseLibraryFiles} style={styles.fileBox}><Text style={styles.fileTitle}>{libraryLoading ? "Indexando..." : "Añadir PDFs a mi biblioteca"}</Text><Text style={styles.fileHint}>Puedes seleccionar varios; se guardan y vectorizan en el backend</Text></Pressable><TextInput value={libraryQuery} onChangeText={setLibraryQuery} multiline numberOfLines={3} placeholder="Ej. ¿Qué dicen mis fuentes sobre aprendizaje adaptativo?" placeholderTextColor="#66756b" style={[styles.input, styles.textArea]} /><Text style={extraStyles.libraryCount}>{documents.length} documentos indexados</Text></> : <TextInput value={value} onChangeText={setValue} multiline={mode === "text"} numberOfLines={mode === "text" ? 4 : 1} placeholder={mode === "id" ? "Ej. NEED-001" : "Describe lo que estás investigando"} placeholderTextColor="#66756b" style={[styles.input, mode === "text" && styles.textArea]} />}
    <View style={styles.sliderRow}><Text style={styles.label}>RESULTADOS</Text><View style={styles.topKRow}>{[5, 8, 12].map((number) => <Chip key={number} active={topK === number} onPress={() => setTopK(number)}>{number}</Chip>)}</View></View>
    <Pressable onPress={submit} disabled={loading} style={[styles.primaryButton, loading && styles.disabled]}><Text style={styles.primaryText}>{loading ? "Procesando..." : "Trazar conexiones"}</Text></Pressable>
  </View>;
}

function Graph({ data, selected, onSelect }) {
  if (!data) return null;
  return <View style={styles.graphPanel}><View style={styles.sectionHead}><Text style={styles.eyebrow}>MAPA DE CONEXIONES</Text><Text style={styles.sectionMeta}>{data.nodes.length} nodos · {data.edges?.length || 0} enlaces</Text></View><ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.graphScroll}>{data.nodes.map((node) => <Pressable key={node.id} onPress={() => onSelect(node.id)} style={[styles.node, node.role === "source" && styles.sourceNode, selected === node.id && styles.selectedNode, { borderColor: node.color || colors.line }]}><View style={[styles.nodeDot, { backgroundColor: node.color || colors.muted }]} /><Text numberOfLines={2} style={styles.nodeLabel}>{node.label || node.id}</Text><Text style={styles.nodeType}>{node.type_label || node.type}</Text></Pressable>)}</ScrollView>{data.edges?.length > 0 && <View style={extraStyles.edgeList}>{data.edges.slice(0, 5).map((edge, index) => <Text key={`${edge.source}-${edge.target}-${index}`} style={extraStyles.edgeText}>{edge.source}  →  {edge.target} · {edge.label || edge.band || "conectado"}</Text>)}</View>}</View>;
}

function ResultList({ results, selected, onSelect }) {
  return <View style={styles.panel}><View style={styles.sectionHead}><Text style={styles.eyebrow}>RANKING</Text><Text style={styles.sectionMeta}>{results.length} resultados</Text></View>{results.map((item, index) => <Pressable key={item.target.id} onPress={() => onSelect(item.target.id)} style={[styles.resultRow, selected === item.target.id && styles.resultSelected]}><Text style={styles.rank}>{String(index + 1).padStart(2, "0")}</Text><View style={[styles.scoreDot, { backgroundColor: item.relevance.label === "alta" ? colors.mint : colors.gold }]} /><View style={styles.resultCopy}><Text style={styles.resultId}>{item.target.id}</Text><Text numberOfLines={1} style={styles.resultExplanation}>{item.explanation}</Text></View><Text style={styles.score}>{item.relevance.score.toFixed(2)}</Text></Pressable>)}</View>;
}

function Detail({ result, source, opportunity }) {
  if (!result && !source) return null;
  return <View style={styles.detail}><Text style={styles.eyebrow}>{source ? "ORIGEN" : "EVIDENCIA"}</Text><Text style={styles.detailTitle}>{source ? source.id : result.target.id}</Text><Text style={styles.detailText}>{source ? "Esta entidad es el centro de la constelación. Selecciona otro nodo para leer su conexión." : result.explanation}</Text>{result?.evidence?.map((evidence, index) => <View key={index} style={styles.evidence}><Text style={styles.evidenceMeta}>{evidence.file} / {evidence.id}</Text><Text style={styles.evidenceText}>{evidence.snippet}</Text></View>)}{opportunity && <View style={styles.opportunity}><Text style={styles.evidenceMeta}>OPORTUNIDAD · {opportunity.priority}</Text><Text style={styles.evidenceText}>{opportunity.opportunity}</Text></View>}</View>;
}

function AnalysisSummary({ result }) {
  const meta = result?.meta || {};
  const isPdf = result?.source?.type === "PDF" || !!meta.pdf_filename;
  return <View style={extraStyles.analysisSummary}><View style={styles.sectionHead}><Text style={styles.eyebrow}>ANALISIS COMPLETADO</Text><Text style={styles.sectionMeta}>{meta.elapsed_seconds ?? "-"}s</Text></View><Text style={extraStyles.analysisTitle}>{isPdf ? meta.pdf_filename || "Documento PDF" : result.source.id}</Text><View style={extraStyles.statusRow}><Text style={extraStyles.statusPill}>{isPdf ? "PDF RECIBIDO" : result.source.type}</Text><Text style={[extraStyles.statusPill, meta.demo_mode && extraStyles.demoPill]}>{meta.demo_mode ? "MODO DEMO" : "BUSQUEDA REAL"}</Text>{isPdf && <Text style={[extraStyles.statusPill, meta.pdf_text_extracted ? extraStyles.successPill : extraStyles.warningPill]}>{meta.pdf_text_extracted ? "TEXTO EXTRAIDO" : "SIN TEXTO"}</Text>}</View><Text style={extraStyles.analysisNote}>{meta.demo_mode ? "Las conexiones visibles son demostrativas; la carga y evidencia del PDF fueron procesadas por la API." : `${meta.total_candidates_scored || 0} candidatos comparados con evidencia trazable.`}</Text></View>;
}

function OpportunityList({ opportunities }) {
  if (!opportunities?.length) return null;
  return <View style={styles.panel}><View style={styles.sectionHead}><Text style={styles.eyebrow}>OPORTUNIDADES</Text><Text style={styles.sectionMeta}>{opportunities.length}</Text></View>{opportunities.map((item, index) => <View key={`${item.type}-${index}`} style={extraStyles.opportunity}><View style={extraStyles.opportunityHead}><Text style={styles.evidenceMeta}>{item.type || "OPORTUNIDAD"}</Text><Text style={extraStyles.priority}>{item.priority || "media"}</Text></View><Text style={styles.evidenceText}>{item.opportunity}</Text>{item.reason && <Text style={extraStyles.reason}>{item.reason}</Text>}</View>)}</View>;
}

function LibraryList({ documents }) {
  if (!documents.length) return null;
  return <View style={styles.panel}><View style={styles.sectionHead}><Text style={styles.eyebrow}>MI BIBLIOTECA</Text><Text style={styles.sectionMeta}>{documents.length} PDFs</Text></View>{documents.map((document) => <View key={document.id} style={extraStyles.documentRow}><Text numberOfLines={1} style={extraStyles.documentName}>{document.filename}</Text><Text style={extraStyles.documentMeta}>{document.pages} páginas · {document.chunks} fragmentos vectorizados</Text></View>)}</View>;
}

function Paywall({ visible, onClose }) {
  const [busy, setBusy] = useState(false);
  const [configured, setConfigured] = useState(false);
  useEffect(() => {
    if (!REVENUECAT_KEY) return;
    import("react-native-purchases").then(({ default: Purchases }) => { Purchases.configure({ apiKey: REVENUECAT_KEY }); setConfigured(true); }).catch(() => {});
  }, []);

  async function purchase() {
    setBusy(true);
    try {
      if (!configured) { Alert.alert("Modo demo", "Configura EXPO_PUBLIC_REVENUECAT_ANDROID_KEY y crea un development build para probar compras reales."); return; }
      const { default: Purchases } = await import("react-native-purchases");
      const offerings = await Purchases.getOfferings();
      const pack = offerings.current?.availablePackages?.[0];
      if (!pack) throw new Error("No hay una oferta configurada en RevenueCat");
      await Purchases.purchasePackage(pack);
      Alert.alert("SaberLink Pro activo", "Tus límites premium están disponibles.");
    } catch (error) {
      if (!error.userCancelled) Alert.alert("No se pudo completar", error.message);
    } finally { setBusy(false); }
  }

  return <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}><View style={styles.modalBackdrop}><View style={styles.paywall}><Pressable onPress={onClose} style={styles.close}><Text style={styles.closeText}>Cerrar</Text></Pressable><Text style={styles.eyebrow}>SABERLINK PRO</Text><Text style={styles.paywallTitle}>Investiga sin perder el hilo.</Text><Text style={styles.paywallText}>Desbloquea más consultas, análisis de documentos y oportunidades de investigación.</Text>{["Consultas ilimitadas", "Análisis PDF avanzado", "Mapa completo de oportunidades"].map((feature) => <Text key={feature} style={styles.feature}>+  {feature}</Text>)}<Pressable onPress={purchase} disabled={busy} style={[styles.primaryButton, busy && styles.disabled]}><Text style={styles.primaryText}>{busy ? "Conectando..." : configured ? "Continuar con RevenueCat" : "Probar flujo de compra"}</Text></Pressable><Text style={styles.legal}>{configured ? "Oferta gestionada por RevenueCat" : "Modo demo: falta configurar la clave Android"}</Text></View></View></Modal>;
}

export default function App() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);
  const [paywall, setPaywall] = useState(false);
  const [demo, setDemo] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [libraryLoading, setLibraryLoading] = useState(false);
  const [userId, setUserId] = useState(null);
  const [usageData, setUsageData] = useState(null);

  useEffect(() => {
    // Get or generate user ID
    let id = null;
    try {
      id = AsyncStorage.getItem("saberlink_user_id");
    } catch (e) {
      // AsyncStorage might not be available in all environments
    }
    if (!id) {
      id = `mobile_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      try {
        AsyncStorage.setItem("saberlink_user_id", id);
      } catch (e) {
        // AsyncStorage might not be available
      }
    }
    setUserId(id);
    
    // Load usage data
    if (id) {
      api.get("/usage/limits", { params: { user_id: id } }).then(({ data }) => setUsageData(data)).catch(() => {});
    }
    
    // Load documents
    api.get(`/projects/${PROJECT_ID}/documents`).then(({ data }) => setDocuments(data)).catch(() => setDocuments([]));
  }, []);

  async function uploadLibrary(files) {
    setLibraryLoading(true); setError(null);
    try {
      for (const file of files) {
        const form = new FormData();
        form.append("file", { uri: file.uri, name: file.name || "document.pdf", type: "application/pdf" });
        await api.post(`/projects/${PROJECT_ID}/documents`, form, { timeout: 180000 });
      }
      const { data } = await api.get(`/projects/${PROJECT_ID}/documents`);
      setDocuments(data);
      Alert.alert("Biblioteca actualizada", `${files.length} PDF${files.length === 1 ? "" : "s"} indexado${files.length === 1 ? "" : "s"}.`);
    } catch (requestError) {
      setError(errorText(requestError));
    } finally { setLibraryLoading(false); }
  }

  async function search(mode, value, topK) {
    setLoading(true); setError(null); setSelected(null); setDemo(false);
    try { 
      const nextResult = await queryApi(mode, value, topK, userId); 
      setResult(nextResult); 
      setSelected(nextResult.results?.[0]?.target?.id || nextResult.source?.id || null);
      // Refresh usage data after successful query
      if (userId) {
        api.get("/usage/limits", { params: { user_id: userId } }).then(({ data }) => setUsageData(data)).catch(() => {});
      }
    }
    catch (requestError) { if (API_BASE.includes("localhost")) { setResult(demoResult); setDemo(true); } else { setError(errorText(requestError)); } }
    finally { setLoading(false); }
  }

  const selectedResult = result?.results?.find((item) => item.target.id === selected);
  const opportunity = result?.opportunities?.find((item) => item.related_entities?.includes(selected));

  return <SafeAreaProvider><SafeAreaView edges={["top", "left", "right"]} style={styles.safe}><StatusBar style="light" /><Header onPaywall={() => setPaywall(true)} usageData={usageData} /><ScrollView contentContainerStyle={styles.content}><View style={styles.hero}><Text style={styles.kicker}>INVESTIGACION, CONECTADA</Text><Text style={styles.title}>Mira lo que tu investigación todavía no te muestra.</Text><Text style={styles.subtitle}>Convierte fuentes y necesidades en conexiones explicables.</Text></View><SearchBox onSearch={search} onLibraryUpload={uploadLibrary} documents={documents} loading={loading} libraryLoading={libraryLoading} /><LibraryList documents={documents} />{demo && <View style={styles.demoBanner}><Text style={styles.demoText}>Vista demo activa. Configura EXPO_PUBLIC_API_BASE para conectar tu backend.</Text></View>}{error && <View style={styles.error}><Text style={styles.errorText}>{error}</Text></View>}{loading && <View style={styles.loading}><ActivityIndicator color={colors.gold} /><Text style={styles.muted}>Analizando conexiones...</Text></View>}{result && !loading && <><AnalysisSummary result={result} /><Graph data={result.graph} selected={selected} onSelect={setSelected} /><ResultList results={result.results || []} selected={selected} onSelect={setSelected} /><Detail result={selectedResult} source={selected === result.source.id ? result.source : null} opportunity={opportunity} /><OpportunityList opportunities={result.opportunities} /></>}</ScrollView><Paywall visible={paywall} onClose={() => setPaywall(false)} /></SafeAreaView></SafeAreaProvider>;
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.ink }, content: { padding: 20, paddingBottom: 42 }, header: { paddingHorizontal: 20, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: colors.line, flexDirection: "row", justifyContent: "space-between", alignItems: "center" }, brand: { flexDirection: "row", alignItems: "center", gap: 10 }, brandName: { color: colors.paper, fontSize: 22, fontWeight: "700" }, brandSub: { color: colors.muted, fontSize: 11, marginTop: 2 }, mark: { width: 30, height: 30, borderWidth: 1, borderColor: colors.gold, borderRadius: 15, justifyContent: "center", alignItems: "center" }, markDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: colors.gold, position: "absolute", top: 5 }, markDotTwo: { top: 18, left: 5, backgroundColor: colors.mint }, markDotThree: { top: 14, right: 4, backgroundColor: colors.copper }, proButton: { borderWidth: 1, borderColor: colors.gold, borderRadius: 6, paddingHorizontal: 10, paddingVertical: 6 }, proText: { color: colors.gold, fontSize: 11, fontWeight: "800", letterSpacing: 1 }, hero: { paddingTop: 22, paddingBottom: 18 }, kicker: { color: colors.gold, fontSize: 11, fontWeight: "800", letterSpacing: 1.7, marginBottom: 9 }, title: { color: colors.paper, fontSize: 29, lineHeight: 34, fontWeight: "700" }, subtitle: { color: colors.muted, fontSize: 15, lineHeight: 22, marginTop: 10 }, panel: { backgroundColor: colors.panel, borderWidth: 1, borderColor: colors.line, borderRadius: 12, padding: 16, marginBottom: 14 }, eyebrow: { color: colors.gold, fontSize: 10, fontWeight: "800", letterSpacing: 1.5 }, chipRow: { flexDirection: "row", gap: 7, marginTop: 12, marginBottom: 12 }, chip: { borderWidth: 1, borderColor: colors.line, borderRadius: 6, paddingHorizontal: 11, paddingVertical: 7 }, chipActive: { backgroundColor: colors.gold, borderColor: colors.gold }, chipText: { color: colors.muted, fontSize: 12, fontWeight: "700" }, chipTextActive: { color: colors.ink }, input: { backgroundColor: colors.ink, borderWidth: 1, borderColor: colors.line, borderRadius: 8, color: colors.paper, paddingHorizontal: 12, paddingVertical: 12, fontSize: 15 }, textArea: { minHeight: 92, textAlignVertical: "top" }, fileBox: { borderWidth: 1, borderStyle: "dashed", borderColor: colors.gold, borderRadius: 8, padding: 22, alignItems: "center" }, fileTitle: { color: colors.paper, fontSize: 15, fontWeight: "700", textAlign: "center" }, fileHint: { color: colors.muted, fontSize: 12, marginTop: 5 }, sliderRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: 15 }, topKRow: { flexDirection: "row", gap: 5 }, label: { color: colors.muted, fontSize: 10, fontWeight: "800" }, primaryButton: { backgroundColor: colors.gold, borderRadius: 8, paddingVertical: 14, alignItems: "center", marginTop: 16 }, primaryText: { color: colors.ink, fontSize: 14, fontWeight: "800" }, disabled: { opacity: 0.55 }, graphPanel: { backgroundColor: colors.panel, borderWidth: 1, borderColor: colors.line, borderRadius: 12, paddingVertical: 16, marginBottom: 14 }, sectionHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingHorizontal: 16, marginBottom: 14 }, sectionMeta: { color: colors.muted, fontSize: 11 }, graphScroll: { paddingHorizontal: 16, gap: 10 }, node: { width: 132, minHeight: 116, backgroundColor: colors.panel2, borderWidth: 1, borderRadius: 9, padding: 12, justifyContent: "space-between" }, sourceNode: { backgroundColor: "#3a3020" }, selectedNode: { borderWidth: 2, transform: [{ scale: 1.03 }] }, nodeDot: { width: 12, height: 12, borderRadius: 6, marginBottom: 10 }, nodeLabel: { color: colors.paper, fontSize: 14, lineHeight: 18, fontWeight: "700" }, nodeType: { color: colors.muted, fontSize: 10, marginTop: 8 }, resultRow: { flexDirection: "row", alignItems: "center", paddingVertical: 13, borderBottomWidth: 1, borderBottomColor: colors.line, gap: 10 }, resultSelected: { backgroundColor: "#2c382f", marginHorizontal: -7, paddingHorizontal: 7, borderRadius: 6 }, rank: { color: colors.muted, width: 22, fontSize: 12, fontWeight: "700" }, scoreDot: { width: 7, height: 7, borderRadius: 4 }, resultCopy: { flex: 1 }, resultId: { color: colors.paper, fontSize: 14, fontWeight: "800" }, resultExplanation: { color: colors.muted, fontSize: 12, marginTop: 3 }, score: { color: colors.gold, fontSize: 13, fontWeight: "800" }, sourceBar: { flexDirection: "row", justifyContent: "space-between", marginBottom: 12, paddingHorizontal: 3 }, sourceId: { color: colors.paper, fontSize: 14, fontWeight: "800" }, sourceMeta: { color: colors.muted, fontSize: 11 }, detail: { backgroundColor: colors.panel2, borderLeftWidth: 3, borderLeftColor: colors.gold, padding: 16, marginTop: 14, borderRadius: 8 }, detailTitle: { color: colors.paper, fontSize: 21, fontWeight: "800", marginTop: 7 }, detailText: { color: colors.paper, opacity: 0.85, fontSize: 14, lineHeight: 21, marginTop: 8 }, evidence: { borderTopWidth: 1, borderTopColor: colors.line, marginTop: 14, paddingTop: 12 }, evidenceMeta: { color: colors.mint, fontSize: 10, fontWeight: "800", letterSpacing: 0.6 }, evidenceText: { color: colors.paper, opacity: 0.78, fontSize: 13, lineHeight: 19, marginTop: 5 }, opportunity: { backgroundColor: "#423525", padding: 12, borderRadius: 7, marginTop: 15 }, loading: { alignItems: "center", padding: 30, gap: 10 }, muted: { color: colors.muted, fontSize: 13 }, error: { backgroundColor: "#482b27", borderRadius: 8, padding: 13, marginBottom: 14 }, errorText: { color: "#ffb49b", fontSize: 13 }, demoBanner: { backgroundColor: "#343023", borderRadius: 8, padding: 11, marginBottom: 14 }, demoText: { color: colors.gold, fontSize: 12, lineHeight: 17 }, modalBackdrop: { flex: 1, justifyContent: "flex-end", backgroundColor: "rgba(0,0,0,0.66)" }, paywall: { backgroundColor: colors.panel, borderTopLeftRadius: 22, borderTopRightRadius: 22, padding: 24, paddingBottom: 32, borderTopWidth: 1, borderColor: colors.gold }, close: { alignSelf: "flex-end", padding: 5, marginBottom: 22 }, closeText: { color: colors.muted, fontSize: 12 }, paywallTitle: { color: colors.paper, fontSize: 29, lineHeight: 34, fontWeight: "800", marginTop: 9 }, paywallText: { color: colors.muted, fontSize: 15, lineHeight: 22, marginTop: 9, marginBottom: 16 }, feature: { color: colors.paper, fontSize: 15, marginVertical: 6 }, legal: { color: colors.muted, fontSize: 10, textAlign: "center", marginTop: 12 }
});

const extraStyles = StyleSheet.create({
  analysisSummary: { backgroundColor: colors.panel, borderWidth: 1, borderColor: colors.gold, borderRadius: 12, padding: 16, marginBottom: 14 },
  analysisTitle: { color: colors.paper, fontSize: 16, fontWeight: "800", marginBottom: 10 },
  statusRow: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  statusPill: { color: colors.ink, backgroundColor: colors.mint, borderRadius: 5, paddingHorizontal: 7, paddingVertical: 5, fontSize: 10, fontWeight: "800" },
  demoPill: { backgroundColor: colors.gold },
  successPill: { backgroundColor: colors.mint },
  warningPill: { backgroundColor: colors.copper },
  analysisNote: { color: colors.muted, fontSize: 12, lineHeight: 18, marginTop: 11 },
  edgeList: { borderTopWidth: 1, borderTopColor: colors.line, marginTop: 14, paddingHorizontal: 16, paddingTop: 10 },
  edgeText: { color: colors.muted, fontSize: 11, marginBottom: 5 },
  opportunity: { backgroundColor: "#423525", padding: 12, borderRadius: 7, marginBottom: 9 },
  opportunityHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  priority: { color: colors.gold, fontSize: 10, fontWeight: "800", textTransform: "uppercase" },
  reason: { color: colors.muted, fontSize: 11, lineHeight: 16, marginTop: 5 },
  libraryCount: { color: colors.mint, fontSize: 12, marginTop: 9 },
  documentRow: { borderTopWidth: 1, borderTopColor: colors.line, paddingVertical: 10 },
  documentName: { color: colors.paper, fontSize: 13, fontWeight: "700" },
  documentMeta: { color: colors.muted, fontSize: 11, marginTop: 4 },
  headerRight: { flexDirection: "row", alignItems: "center", gap: 10 },
  usageBadge: { backgroundColor: colors.panel, borderWidth: 1, borderColor: colors.gold, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 4 },
  usageText: { color: colors.gold, fontSize: 10, fontWeight: "700" },
});
