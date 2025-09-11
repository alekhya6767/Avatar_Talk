"""
Machine Translation module with MarianMT (primary) and Argos Translate (fallback).
Now supports dynamic target languages with model caching.
"""
import logging
from typing import Optional, Dict, Tuple
import torch
from transformers import MarianMTModel, MarianTokenizer
import argostranslate.package
import argostranslate.translate


class MTModule:
    """MT with MarianMT primary + Argos fallback, dynamic per-target caching."""

    def __init__(self, source_lang: str = "en", target_lang: str = "es"):
        self.logger = logging.getLogger(__name__)
        self.source_lang = source_lang
        self.target_lang = target_lang

        # Marian cache: (src, tgt) -> (tokenizer, model)
        self._marian_cache: Dict[Tuple[str, str], Tuple[MarianTokenizer, MarianMTModel]] = {}

        # Track which Argos packages we've tried to configure
        self._argos_ready_pairs: Dict[Tuple[str, str], bool] = {}

    # ---------- Marian ----------
    def _marian_model_name(self, src: str, tgt: str) -> str:
        # Helsinki naming is usually opus-mt-en-xx for these languages
        return f"Helsinki-NLP/opus-mt-{src}-{tgt}"

    def _ensure_marian(self, src: str, tgt: str) -> Tuple[MarianTokenizer, MarianMTModel]:
        key = (src, tgt)
        if key in self._marian_cache:
            return self._marian_cache[key]

        model_name = self._marian_model_name(src, tgt)
        self.logger.info(f"Loading MarianMT model: {model_name}")
        tok = MarianTokenizer.from_pretrained(model_name)
        model = MarianMTModel.from_pretrained(model_name)
        if torch.cuda.is_available():
            model = model.cuda()
            self.logger.info("MarianMT model moved to GPU")
        self._marian_cache[key] = (tok, model)
        return tok, model

    def translate_with_marian(self, text: str, src: str, tgt: str) -> str:
        tok, model = self._ensure_marian(src, tgt)
        inputs = tok(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
        if next(model.parameters()).is_cuda:
            inputs = {k: v.cuda() for k, v in inputs.items()}
        with torch.no_grad():
            out = model.generate(**inputs, max_length=512, num_beams=4)
        return tok.decode(out[0], skip_special_tokens=True)

    # ---------- Argos ----------
    def _setup_argos_pair(self, src: str, tgt: str) -> bool:
        key = (src, tgt)
        if key in self._argos_ready_pairs:
            return self._argos_ready_pairs[key]
        try:
            argostranslate.package.update_package_index()
            available = argostranslate.package.get_available_packages()
            pkg = next((p for p in available if p.from_code == src and p.to_code == tgt), None)
            if pkg:
                installed = argostranslate.package.get_installed_packages()
                if not any(p.from_code == src and p.to_code == tgt for p in installed):
                    self.logger.info(f"Installing Argos package: {src}-{tgt}")
                    argostranslate.package.install_from_path(pkg.download())
                self._argos_ready_pairs[key] = True
            else:
                self.logger.warning(f"Argos package not available for {src}-{tgt}")
                self._argos_ready_pairs[key] = False
        except Exception as e:
            self.logger.warning(f"Failed Argos setup for {src}-{tgt}: {e}")
            self._argos_ready_pairs[key] = False
        return self._argos_ready_pairs[key]

    def translate_with_argos(self, text: str, src: str, tgt: str) -> str:
        return argostranslate.translate.translate(text, src, tgt)

    # ---------- Public API ----------
    def translate(self, text: str, target_lang: Optional[str] = None, use_fallback: bool = True) -> str:
        """Translate text from current source_lang to target_lang (dynamic)."""
        if not text.strip():
            return text
        tgt = (target_lang or self.target_lang or "es").lower()
        src = (self.source_lang or "en").lower()

        # Try Marian first
        try:
            self.logger.info(f"MT: Marian en->{tgt}")
            return self.translate_with_marian(text, src, tgt)
        except Exception as e:
            self.logger.warning(f"MarianMT failed for {src}-{tgt}: {e}")

            if use_fallback and self._setup_argos_pair(src, tgt):
                try:
                    self.logger.info("Falling back to Argos Translate")
                    return self.translate_with_argos(text, src, tgt)
                except Exception as e2:
                    self.logger.error(f"Argos fallback failed: {e2}")
                    raise RuntimeError(f"Both Marian and Argos failed for {src}-{tgt}")
            else:
                raise RuntimeError(f"No MT available for {src}-{tgt}")

    def get_status(self) -> dict:
        return {
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "marian_cached_pairs": [f"{s}-{t}" for (s, t) in self._marian_cache.keys()],
            "cuda_available": torch.cuda.is_available(),
            "argos_ready_pairs": [f"{s}-{t}" for (s, t), ok in self._argos_ready_pairs.items() if ok],
        }
