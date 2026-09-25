"""PDF processing with LightRAG-HKU integration [PLUS].

Converts PDF → Docling → Markdown → LightRAG graph + embeddings using Cohere.
Based on the pattern from grafo_saberlink.ipynb.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cohere
import pymupdf4llm
from lightrag import LightRAG

from saberlink import config


class LightRAGProcessor:
    """LightRAG processor with Cohere integration (singleton pattern)."""
    
    _instance = None
    _rag = None
    
    def __init__(self, working_dir: Path | None = None, api_key: str | None = None):
        """Initialize LightRAG processor (singleton pattern).
        
        Args:
            working_dir: Directory for LightRAG storage (default: config.LIGHTRAG_DIR)
            api_key: Cohere API key (default: from config.COHERE_API_KEY)
        """
        self.working_dir = Path(working_dir) if working_dir else config.LIGHTRAG_DIR
        self.working_dir.mkdir(parents=True, exist_ok=True)
        self.api_key = api_key or config.COHERE_API_KEY
    
    @classmethod
    def get_rag_instance(cls, working_dir: Path, api_key: str):
        """Get or create singleton LightRAG instance."""
        if cls._rag is None:
            working_dir = Path(working_dir)
            api_key = api_key or config.COHERE_API_KEY
            
            # Create simple wrappers that avoid pickle issues
            async def cohere_llm_func(prompt, system_prompt=None, history_messages=[], **kwargs):
                client = cohere.Client(api_key)
                # Filter out LightRAG-specific kwargs that Cohere doesn't accept
                cohere_kwargs = {k: v for k, v in kwargs.items() if k not in ['hashing_kv', 'hashing']}
                
                # Convert LightRAG history format to Cohere format
                chat_history = []
                for msg in history_messages:
                    role = msg.get("role", "").upper()
                    content = msg.get("content", "")
                    if content:  # Only add if there's content
                        if role == "USER":
                            chat_history.append({"role": "USER", "message": content})
                        elif role == "ASSISTANT":
                            chat_history.append({"role": "CHATBOT", "message": content})
                
                response = client.chat(
                    message=prompt,
                    chat_history=chat_history,
                    preamble=system_prompt,
                    **cohere_kwargs
                )
                return response.text
            
            # Use sentence-transformers for embeddings to avoid rate limits
            from sentence_transformers import SentenceTransformer
            embed_model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
            
            async def local_embed_func(texts):
                # sentence-transformers is synchronous, run in thread pool
                import asyncio
                loop = asyncio.get_event_loop()
                embeddings = await loop.run_in_executor(None, embed_model.encode, texts)
                return embeddings.tolist()
            
            @dataclass
            class SimpleLLM:
                func: callable
                max_token_size: int = 32768
                def __call__(self, *args, **kwargs):
                    return self.func(*args, **kwargs)
            
            @dataclass
            class SimpleEmbed:
                func: callable
                max_token_size: int = 512
                embedding_dim: int = 768  # all-mpnet-base-v2 has 768 dimensions
                def __call__(self, *args, **kwargs):
                    return self.func(*args, **kwargs)
            
            cls._rag = LightRAG(
                working_dir=str(working_dir),
                llm_model_func=SimpleLLM(func=cohere_llm_func),
                embedding_func=SimpleEmbed(func=local_embed_func),
            )
        
        return cls._rag
    
    async def initialize_storages(self):
        """Initialize LightRAG storages."""
        rag = self.get_rag_instance(self.working_dir, self.api_key)
        await rag.initialize_storages()
    
    async def insert_text(self, text: str):
        """Insert text into LightRAG."""
        await self.initialize_storages()
        rag = self.get_rag_instance(self.working_dir, self.api_key)
        await rag.ainsert(text)
        return {"status": "success", "text_length": len(text)}


def pdf_to_markdown(pdf_path: str | Path) -> str:
    """Convert PDF to Markdown using Docling first, fallback to pymupdf4llm."""
    pdf_path = Path(pdf_path)
    
    # Try Docling first for better quality
    try:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True
        
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        
        result = converter.convert(str(pdf_path))
        return result.document.export_to_markdown()
        
    except ImportError:
        # Fallback to pymupdf4llm if Docling is not available
        print("⚠️ Docling not available, using pymupdf4llm as fallback")
        doc = pymupdf4llm.to_markdown(str(pdf_path))
        return doc
    except Exception as e:
        # If Docling fails, fallback to pymupdf4llm
        print(f"⚠️ Docling conversion failed: {e}, using pymupdf4llm as fallback")
        doc = pymupdf4llm.to_markdown(str(pdf_path))
        return doc


def process_pdf_with_lightrag(
    pdf_path: str | Path,
    output_dir: Path | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Process PDF with LightRAG to extract entities and build graph.

    Args:
        pdf_path: Path to PDF file
        output_dir: Directory to store LightRAG artifacts (default: config.LIGHTRAG_DIR)
        api_key: Cohere API key (default: from config.COHERE_API_KEY)

    Returns:
        Dict with extracted entities and metadata
    """
    pdf_path = Path(pdf_path)
    if output_dir is None:
        output_dir = config.LIGHTRAG_DIR

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Convert PDF to Markdown
    markdown_text = pdf_to_markdown(pdf_path)

    # 2. Generate hash for caching
    pdf_hash = hashlib.md5(pdf_path.read_bytes()).hexdigest()

    # 3. Store markdown for LightRAG processing
    markdown_path = output_dir / f"{pdf_hash}.md"
    markdown_path.write_text(markdown_text, encoding="utf-8")

    # 4. Initialize LightRAG processor
    processor = LightRAGProcessor(working_dir=output_dir, api_key=api_key)

    # 5. Insert text into LightRAG (async)
    result = asyncio.run(processor.insert_text(markdown_text))

    return {
        "pdf_hash": pdf_hash,
        "markdown_path": str(markdown_path),
        "markdown_length": len(markdown_text),
        "graph_path": str(output_dir / "graph_chunk_entity_relation.graphml"),
        "lightrag_result": result,
    }


async def process_pdf_with_lightrag_async(
    pdf_path: str | Path,
    output_dir: Path | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Async version of process_pdf_with_lightrag for FastAPI endpoints.

    This version avoids pickle errors by being fully async.

    Args:
        pdf_path: Path to PDF file
        output_dir: Directory to store LightRAG artifacts (default: config.LIGHTRAG_DIR)
        api_key: Cohere API key (default: from config.COHERE_API_KEY)

    Returns:
        Dict with extracted entities and metadata
    """
    pdf_path = Path(pdf_path)
    if output_dir is None:
        output_dir = config.LIGHTRAG_DIR

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Convert PDF to Markdown (sync, but fast)
    markdown_text = pdf_to_markdown(pdf_path)

    # 2. Generate hash for caching
    pdf_hash = hashlib.md5(pdf_path.read_bytes()).hexdigest()

    # 3. Store markdown for LightRAG processing
    markdown_path = output_dir / f"{pdf_hash}.md"
    markdown_path.write_text(markdown_text, encoding="utf-8")

    # 4. Initialize LightRAG processor
    processor = LightRAGProcessor(working_dir=output_dir, api_key=api_key)

    # 5. Insert text into LightRAG (async)
    result = await processor.insert_text(markdown_text)

    return {
        "pdf_hash": pdf_hash,
        "markdown_path": str(markdown_path),
        "markdown_length": len(markdown_text),
        "graph_path": str(output_dir / "graph_chunk_entity_relation.graphml"),
        "lightrag_result": result,
    }


def extract_text_profile_from_markdown(markdown_text: str, source_file: str) -> dict[str, str]:
    """Extract a text profile from Markdown for compatibility with existing pipeline.
    
    This creates a NEED-shaped profile that can be used with the existing
    pipeline.run_query() function.
    """
    # Simple extraction: first paragraph as description, rest as context
    lines = markdown_text.split("\n")
    lines = [line.strip() for line in lines if line.strip()]
    
    if not lines:
        return {
            "title": source_file,
            "description": "",
            "context": "",
            "expected_impact": "",
        }
    
    # First non-header line as title
    title = lines[0].lstrip("#").strip()
    
    # First paragraph as description
    description = ""
    context_lines = []
    in_description = True
    
    for line in lines[1:]:
        if line.startswith("#"):
            in_description = False
        if in_description and line:
            description += line + " "
        elif not in_description and line:
            context_lines.append(line)
    
    context = " ".join(context_lines[:500])  # Limit context length
    
    return {
        "title": title or source_file,
        "description": description.strip(),
        "context": context.strip(),
        "expected_impact": "",
        "_source_file_name": source_file,
    }
