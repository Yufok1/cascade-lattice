"""
CASCADE Color Logging Example
Shows how to integrate beautiful colored logs throughout your system.
"""

from .kleene_logger import get_kleene_logger, LogLevel
from .interpretive_logger import get_interpretive_logger, ImpactLevel

def example_data_processing():
    """Example: Data processing with beautiful logs"""
    kleene = get_kleene_logger("DataProcessor")
    interpretive = get_interpretive_logger("Data Pipeline")
    
    # Start processing
    kleene.log(LogLevel.INFO, "load_dataset_start", 
               state_before={"dataset": "smollm3-blueprint.pdf"})
    
    interpretive.log(ImpactLevel.LOW, "DataLoader", "Loading dataset",
                    context="Reading PDF file for analysis",
                    consequence="Will extract text and metadata",
                    metrics={"file_size": "1.0MB", "type": "PDF"})
    
    # Processing steps
    kleene.log(LogLevel.DEBUG, "extract_text",
               state_before={"page": 1},
               state_after={"pages_processed": 15})
    
    # Fixed point reached
    kleene.log(LogLevel.INFO, "processing_complete",
               state_after={"records": 500, "clean": True},
               fixed_point=True,
               iterations=3)
    
    interpretive.log(ImpactLevel.MEDIUM, "DataProcessor", "Processing complete",
                    context="Successfully extracted and cleaned data",
                    consequence="Ready for forensics analysis",
                    metrics={"records": 500, "pages": 15, "errors": 0})

def example_model_observation():
    """Example: Model observation with beautiful logs"""
    kleene = get_kleene_logger("ModelObserver")
    interpretive = get_interpretive_logger("Model Observatory")
    
    # Model loading
    kleene.log(LogLevel.INFO, "model_load_start",
               state_before={"model": "mistralai/Mixtral-8x22B-Instruct-v0.1"})
    
    interpretive.log(ImpactLevel.MEDIUM, "ModelLoader", "Loading Mixtral",
                    context="Loading 8x22B MoE model for inference",
                    consequence="Will consume significant VRAM",
                    metrics={"params": "141B", "active": "39B", "device": "cuda"})
    
    # Observation
    kleene.log(LogLevel.INFO, "observation_start",
               state_before={"layers": 0, "hash": "initial"})
    
    # Fixed point achieved
    kleene.log(LogLevel.INFO, "observation_fixed_point",
               state_after={"layers": 64, "merkle": "abc123..."},
               fixed_point=True,
               iterations=64)
    
    interpretive.log(ImpactLevel.LOW, "CASCADE", "Model observed",
                    context="Cryptographic proof generated for model execution",
                    consequence="Merkle root provides verifiable audit trail",
                    metrics={"model": "Mixtral", "layers": 64, "merkle": "abc123..."})

def example_error_handling():
    """Example: Error handling with colored logs"""
    kleene = get_kleene_logger("ErrorHandler")
    interpretive = get_interpretive_logger("System Monitor")
    
    # Error detected
    kleene.log(LogLevel.ERROR, "memory_exhaustion",
               state_before={"memory": "15.8/16GB", "operation": "inference"},
               fixed_point=False)
    
    interpretive.log(ImpactLevel.HIGH, "MemoryManager", "Out of memory",
                    context="GPU memory exhausted during model inference",
                    consequence="Inference failed, system degraded",
                    metrics={"used": "15.8GB", "total": "16GB", "available": "200MB"},
                    recommendation="Enable gradient checkpointing or use smaller batch size")
    
    # Recovery
    kleene.log(LogLevel.WARNING, "fallback_activated",
               state_after={"mode": "cpu_fallback", "batch_size": 1})
    
    interpretive.log(ImpactLevel.MEDIUM, "FallbackHandler", "CPU fallback activated",
                    context="Switched to CPU inference due to memory constraints",
                    consequence="Performance degraded but functionality preserved",
                    metrics={"device": "cpu", "batch_size": 1, "slowdown": "10x"})

# Run all examples
if __name__ == "__main__":
    print("\n🎨 CASCADE Color Logging Examples\n")
    print("="*60)
    
    example_data_processing()
    print("\n" + "="*60)
    
    example_model_observation()
    print("\n" + "="*60)
    
    example_error_handling()
    print("\n" + "="*60)
    
    print("\n✨ Beautiful logs are ready for production!")
