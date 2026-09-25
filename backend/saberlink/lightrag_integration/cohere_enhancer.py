"""Cohere LLM integration for enhanced recommendations [PLUS].

Provides re-ranking and opportunity generation using Cohere API.
"""

from __future__ import annotations

from typing import Any

import cohere

from saberlink import config


class CohereEnhancer:
    """Enhances search results and generates opportunities using Cohere."""
    
    def __init__(self, api_key: str | None = None):
        """Initialize Cohere client.
        
        Args:
            api_key: Cohere API key (default: from config.COHERE_API_KEY)
        """
        self.api_key = api_key or config.COHERE_API_KEY
        if not self.api_key:
            raise ValueError("Cohere API key not configured. Set COHERE_API_KEY environment variable.")
        
        self.client = cohere.Client(self.api_key)
        self.model = config.COHERE_MODEL  # command-r-plus-08-2024
        self.rerank_model = "rerank-english-v3.0"  # Compatible rerank model
        self.embedding_model = config.COHERE_EMBEDDING_MODEL
    
    def rerank_results(
        self,
        query: str,
        results: list[dict[str, Any]],
        top_n: int | None = None,
    ) -> list[dict[str, Any]]:
        """Re-rank search results using Cohere's rerank API.
        
        Args:
            query: Original query text
            results: List of result dicts with 'target' and 'evidence'
            top_n: Number of top results to return (default: all)
        
        Returns:
            Re-ranked list of results
        """
        if not results:
            return results
        
        # Prepare documents for reranking
        documents = []
        for result in results:
            # Combine evidence snippets for reranking
            evidence_text = " ".join(
                [ev.get("snippet", "") for ev in result.get("evidence", [])]
            )
            target_info = result.get("target", {})
            doc_text = f"{target_info.get('id', '')}: {evidence_text}"
            documents.append(doc_text)
        
        # Call Cohere rerank API
        try:
            rerank_response = self.client.rerank(
                model=self.rerank_model,
                query=query,
                documents=documents,
                top_n=top_n or len(results),
            )
            
            # Reorder results based on rerank scores
            reranked_indices = [r.index for r in rerank_response.results]
            reranked_results = [results[i] for i in reranked_indices]
            
            # Add rerank scores to results
            for i, result in enumerate(reranked_results):
                result["cohere_rerank_score"] = rerank_response.results[i].relevance_score
            
            return reranked_results
        
        except Exception as e:
            # Fallback to original order if reranking fails
            print(f"Cohere reranking failed: {e}. Using original order.")
            return results
    
    def generate_opportunities(
        self,
        query: str,
        results: list[dict[str, Any]],
        source_info: dict[str, Any],
        lightrag_context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Generate enhanced opportunities using Cohere LLM.
        
        Args:
            query: Original query text
            results: Ranked search results
            source_info: Source entity information
            lightrag_context: LightRAG graph information for additional context
        
        Returns:
            List of opportunity dicts with enhanced explanations
        """
        if not results:
            return []
        
        # Prepare context for LLM
        top_results = results[:15]  # Use top 15 results for more variety of entity types
        context = self._build_opportunity_context(query, top_results, source_info)
        
        # Add LightRAG graph context if available
        lightrag_section = ""
        if lightrag_context and lightrag_context.get("graph_path"):
            lightrag_section = self._build_lightrag_context(lightrag_context)
        
        prompt = f"""
Basado en el siguiente contexto de conocimiento institucional, genera oportunidades específicas y accionables.

Consulta: {query}

Contexto Institucional:
{context}

{lightrag_section}

Genera 3-5 oportunidades específicas que podrían:
- Identificar posibles temas o líneas para nuevos proyectos de investigación
- Encontrar antecedentes relevantes para una propuesta
- Conectar proyectos institucionales con oportunidades de investigación
- Identificar investigadores, grupos o capacidades complementarias
- Sugerir posibilidades de colaboración entre programas o facultades
- Relacionar conocimiento generado con componentes curriculares

Para cada oportunidad, proporciona:
1. Tipo (RESEARCH_CONTINUITY, COLLABORATION, CAPABILITY_ALIGNMENT, etc.)
2. Descripción específica de la oportunidad (en español)
3. Razón por la que esta oportunidad es relevante (en español)
4. Nivel de prioridad (alta, media, baja)
5. IDs de entidades relacionadas - IMPORTANTE: Usa EXACTAMENTE los IDs de la lista de resultados anteriores (ej. COM-0127, INV-104, etc.)

Responde en español. Formato como lista JSON.
"""
        
        try:
            response = self.client.chat(
                model=self.model,
                message=prompt,
                temperature=0.3,
            )
            
            # Parse JSON response from Cohere
            import json
            import re
            
            opportunities_text = response.text
            print(f"[Cohere Response] {opportunities_text[:1000]}")  # Debug logging
            
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'\[\s*\{.*\}\s*\]', opportunities_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                opportunities = json.loads(json_str)
            else:
                # Try to parse as JSON object with "oportunidades" key
                try:
                    full_json = json.loads(opportunities_text)
                    if isinstance(full_json, dict) and "oportunidades" in full_json:
                        opportunities = full_json["oportunidades"]
                    else:
                        opportunities = []
                except:
                    opportunities = []
            
            # Validate and format opportunities
            formatted_opportunities = []
            for opp in opportunities:
                # Handle both English and Spanish keys from Cohere
                formatted_opportunities.append({
                    "type": opp.get("type") or opp.get("tipo") or "COHERE_ENHANCED",
                    "opportunity": opp.get("opportunity") or opp.get("descripción") or opp.get("description", "Oportunidad generada"),
                    "reason": opp.get("reason") or opp.get("razón") or opp.get("explanation", "Basado en análisis semántico"),
                    "priority": opp.get("priority") or opp.get("prioridad", "media"),
                    "related_entities": opp.get("related_entities") or opp.get("entidades_relacionadas", [r["target"]["id"] for r in top_results]),
                    "generated_by": "cohere",
                })
            
            return formatted_opportunities
        
        except Exception as e:
            print(f"Cohere opportunity generation failed: {e}")
            return []  # Return empty to let institutional opportunities show
    
    def _build_opportunity_context(
        self,
        query: str,
        results: list[dict[str, Any]],
        source_info: dict[str, Any],
    ) -> str:
        """Build context string for opportunity generation."""
        context_parts = [
            f"Source: {source_info.get('id', '')} ({source_info.get('type', '')})",
        ]
        
        for i, result in enumerate(results, 1):
            target = result.get("target", {})
            evidence = result.get("evidence", [])
            
            context_parts.append(
                f"\n{i}. {target.get('id', '')} ({target.get('type', '')}) - "
                f"Score: {result.get('relevance', {}).get('score', 0):.2f}"
            )
            
            for ev in evidence[:2]:  # Top 2 evidence snippets
                context_parts.append(f"   - {ev.get('field', '')}: {ev.get('snippet', '')[:100]}...")
        
        return "\n".join(context_parts)
    
    def _build_lightrag_context(self, lightrag_context: dict[str, Any]) -> str:
        """Build context string from LightRAG graph information."""
        graph_path = lightrag_context.get("graph_path")
        if not graph_path:
            return ""
        
        try:
            import networkx as nx
            from pathlib import Path
            
            graph_file = Path(graph_path)
            if not graph_file.exists():
                return ""
            
            # Load the LightRAG graph
            G = nx.read_graphml(graph_file)
            
            # Extract key information
            num_nodes = G.number_of_nodes()
            num_edges = G.number_of_edges()
            
            # Get some sample entities and relations
            sample_nodes = list(G.nodes(data=True))[:10]
            sample_edges = list(G.edges(data=True))[:5]
            
            context_parts = [
                f"\nGrafo LightRAG del PDF:",
                f"- Nodos extraídos: {num_nodes}",
                f"- Relaciones extraídas: {num_edges}",
            ]
            
            if sample_nodes:
                context_parts.append("\nEntidades clave extraídas:")
                for node_id, node_data in sample_nodes[:5]:
                    entity_type = node_data.get("entity_type", "UNKNOWN")
                    context_parts.append(f"  - {node_id} ({entity_type})")
            
            if sample_edges:
                context_parts.append("\nRelaciones clave:")
                for src, tgt, edge_data in sample_edges:
                    relation = edge_data.get("relation", "relacionado")
                    context_parts.append(f"  - {src} -> {tgt} ({relation})")
            
            return "\n".join(context_parts)
        
        except Exception as e:
            print(f"Failed to build LightRAG context: {e}")
            return ""
