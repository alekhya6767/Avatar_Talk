"""
Machine Translation module with MarianMT (primary) and Argos Translate (fallback).
"""
import logging
from typing import Optional
import torch
from transformers import MarianMTModel, MarianTokenizer
import argostranslate.package
import argostranslate.translate


class MTModule:
    """Machine Translation module with MarianMT primary and Argos fallback."""
    
    def __init__(self, source_lang: str = "en", target_lang: str = "es"):
        """
        Initialize the MT module.
        
        Args:
            source_lang: Source language code (default: "en")
            target_lang: Target language code (default: "es")
        """
        self.logger = logging.getLogger(__name__)
        self.source_lang = source_lang
        self.target_lang = target_lang
        
        # MarianMT components
        self.marian_model = None
        self.marian_tokenizer = None
        self.marian_model_name = f"Helsinki-NLP/opus-mt-{source_lang}-{target_lang}"
        
        # Argos components
        self.argos_available = False
        self._setup_argos()
        
    def _setup_argos(self) -> None:
        """Setup Argos Translate as fallback."""
        try:
            # Update package index
            argostranslate.package.update_package_index()
            
            # Check if the language pair is available
            available_packages = argostranslate.package.get_available_packages()
            package_to_install = None
            
            for package in available_packages:
                if (package.from_code == self.source_lang and 
                    package.to_code == self.target_lang):
                    package_to_install = package
                    break
            
            if package_to_install:
                # Check if already installed
                installed_packages = argostranslate.package.get_installed_packages()
                already_installed = any(
                    pkg.from_code == self.source_lang and pkg.to_code == self.target_lang
                    for pkg in installed_packages
                )
                
                if not already_installed:
                    self.logger.info(f"Installing Argos package: {self.source_lang}-{self.target_lang}")
                    argostranslate.package.install_from_path(package_to_install.download())
                
                self.argos_available = True
                self.logger.info("Argos Translate fallback configured successfully")
            else:
                self.logger.warning(f"Argos package not available for {self.source_lang}-{self.target_lang}")
                
        except Exception as e:
            self.logger.warning(f"Failed to setup Argos Translate: {e}")
            self.argos_available = False
    
    def load_marian_model(self) -> None:
        """Load MarianMT model and tokenizer."""
        try:
            self.logger.info(f"Loading MarianMT model: {self.marian_model_name}")
            
            self.marian_tokenizer = MarianTokenizer.from_pretrained(self.marian_model_name)
            self.marian_model = MarianMTModel.from_pretrained(self.marian_model_name)
            
            # Move to GPU if available
            if torch.cuda.is_available():
                self.marian_model = self.marian_model.cuda()
                self.logger.info("MarianMT model moved to GPU")
            
            self.logger.info("MarianMT model loaded successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to load MarianMT model: {e}")
            raise
    
    def translate_with_marian(self, text: str) -> str:
        """
        Translate text using MarianMT.
        
        Args:
            text: Text to translate
            
        Returns:
            Translated text
        """
        if self.marian_model is None or self.marian_tokenizer is None:
            self.load_marian_model()
        
        try:
            # Tokenize input
            inputs = self.marian_tokenizer(text, return_tensors="pt", padding=True, truncation=True)
            
            # Move to GPU if model is on GPU
            if next(self.marian_model.parameters()).is_cuda:
                inputs = {k: v.cuda() for k, v in inputs.items()}
            
            # Generate translation
            with torch.no_grad():
                outputs = self.marian_model.generate(**inputs, max_length=512, num_beams=4)
            
            # Decode output
            translated = self.marian_tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            self.logger.debug(f"MarianMT translation: '{text}' -> '{translated}'")
            return translated
            
        except Exception as e:
            self.logger.error(f"MarianMT translation failed: {e}")
            raise
    
    def translate_with_argos(self, text: str) -> str:
        """
        Translate text using Argos Translate.
        
        Args:
            text: Text to translate
            
        Returns:
            Translated text
        """
        if not self.argos_available:
            raise RuntimeError("Argos Translate is not available")
        
        try:
            translated = argostranslate.translate.translate(
                text, self.source_lang, self.target_lang
            )
            
            self.logger.debug(f"Argos translation: '{text}' -> '{translated}'")
            return translated
            
        except Exception as e:
            self.logger.error(f"Argos translation failed: {e}")
            raise
    
    def translate(self, text: str, use_fallback: bool = True) -> str:
        """
        Translate text using MarianMT with optional Argos fallback.
        
        Args:
            text: Text to translate
            use_fallback: Whether to use Argos as fallback if MarianMT fails
            
        Returns:
            Translated text
        """
        if not text.strip():
            return text
        
        # Try MarianMT first
        try:
            self.logger.info("Attempting translation with MarianMT")
            return self.translate_with_marian(text)
            
        except Exception as e:
            self.logger.warning(f"MarianMT failed: {e}")
            
            if use_fallback and self.argos_available:
                self.logger.info("Falling back to Argos Translate")
                try:
                    return self.translate_with_argos(text)
                except Exception as fallback_e:
                    self.logger.error(f"Argos fallback also failed: {fallback_e}")
                    raise RuntimeError(f"Both translation methods failed. MarianMT: {e}, Argos: {fallback_e}")
            else:
                if not use_fallback:
                    self.logger.error("Fallback disabled, translation failed")
                else:
                    self.logger.error("No fallback available, translation failed")
                raise
    
    def get_status(self) -> dict:
        """Get status of translation components."""
        return {
            "marian_loaded": self.marian_model is not None,
            "marian_model_name": self.marian_model_name,
            "argos_available": self.argos_available,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "cuda_available": torch.cuda.is_available()
        }
